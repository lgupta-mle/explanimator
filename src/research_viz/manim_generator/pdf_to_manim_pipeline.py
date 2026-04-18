"""
PDF to Manim Pipeline

Complete pipeline: PDF → 3B1B Explanation → Manim Code with execution feedback.
Uses RAG only when execution errors occur.
"""

import logging
import os
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
import tyro
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from research_viz.manim_generator.pdf_explanation_generator import (
    create_pdf_llm_response,
    call_llm_provider,
    _build_response_format,
    load_prompt,
    encode_pdf_to_base64,
)
from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B, Segment3B1B
from research_viz.config.pipeline_config import get_config, get_provider
from research_viz.pipeline.checkpoint import read_checkpoints, validate_checkpoint, write_checkpoint

load_dotenv()


class ManimSceneCode(BaseModel):
    """Generated Manim scene code."""
    scene_id: str = Field(..., description="Scene identifier")
    class_name: str = Field(..., description="PascalCase class name")
    code: str = Field(..., description="Complete Scene class code with imports")


def load_code_gen_prompt() -> str:
    """Load the Manim code generation prompt."""
    prompt_path = Path(__file__).parent / "prompts" / "manim_code_generation_prompt.txt"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def execute_manim_scene(code: str, class_name: str) -> tuple[bool, str]:
    """
    Execute Manim code and return success status and output/errors.

    Returns:
        (success, output_or_error)
    """
    cfg = get_config()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['manim', 'render', '-ql', '--disable_caching', temp_path, class_name],
            capture_output=True,
            text=True,
            timeout=cfg.manim.timeout
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            error_output = result.stderr or result.stdout
            return False, error_output

    except subprocess.TimeoutExpired:
        return False, f"Timeout: Manim render took too long (>{cfg.manim.timeout}s)"
    except Exception as e:
        return False, f"Exception: {str(e)}"
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


def fetch_rag_context_for_error(error_message: str, chroma_path: str = "data/manim_docs/vector_db/chroma_db") -> str:
    """Fetch RAG context to help fix an error."""
    if not os.path.exists(chroma_path):
        return ""

    try:
        from research_viz.preprocessing.manim_db import ManimDocRetriever
        retriever = ManimDocRetriever(chroma_path=chroma_path)

        # Extract key terms from error
        import re
        search_terms = []

        # Extract quoted terms
        quoted = re.findall(r"'([^']+)'", error_message)
        search_terms.extend(quoted[:5])

        # Extract class names (PascalCase)
        classes = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', error_message)
        search_terms.extend(classes[:3])

        # Build query
        if search_terms:
            query = "Manim " + " ".join(search_terms[:5])
        else:
            query = "Manim Scene animation error fix"

        # Query RAG
        query_embedding = retriever._get_embedding(query)
        results = retriever.collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )

        if results and results['documents'] and results['documents'][0]:
            docs = [doc[:800] for doc in results['documents'][0][:3]]
            return "\n\n---\n\n".join(docs)

    except Exception as e:
        logger.error(f"    RAG error: {e}")

    return ""


def generate_scene_code(
    segment: dict,
    running_example: str,
    difficulty: str,
    model_name: Optional[str] = None,
    max_retries: Optional[int] = None,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db",
    beat_timeline: Optional[List[dict]] = None
) -> Optional[ManimSceneCode]:
    """
    Generate Manim code for a segment with execution-based feedback loop.

    Process:
    1. Generate code without RAG
    2. Execute with Manim
    3. If error, fetch RAG context and retry
    """
    cfg = get_config()
    if model_name is None:
        model_name = cfg.llm.get_model("code_gen_model", difficulty)
    if max_retries is None:
        max_retries = cfg.manim.max_retries
    system_prompt = load_code_gen_prompt()

    segment_id = segment.get('segment_id', 'scene')
    title = segment.get('title', 'Untitled')
    narration = segment.get('narration_script', '')
    intuition = segment.get('intuition', {})
    technical = segment.get('technical', {})

    # Calculate expected narration duration
    word_count = len(narration.split())
    # Average speech rate: ~150 words per minute = ~2.5 words per second
    estimated_narration_duration = word_count / 2.5
    # Add 20% buffer for pacing and pauses
    target_animation_duration = estimated_narration_duration * 1.2
    
    # Build beat timing information if available
    beat_timing_section = ""
    if beat_timeline:
        beat_timing_section = "\n### BEAT-LEVEL TIMING (CRITICAL FOR SYNC):\n"
        beat_timing_section += "The narration has been split into beats with precise timing. Your animation MUST sync with these beats:\n\n"
        total_audio_duration = sum(beat.get('duration', 0) for beat in beat_timeline)
        
        for i, beat in enumerate(beat_timeline, 1):
            beat_text = beat.get('text', '')[:80]
            beat_duration = beat.get('duration', 0)
            beat_start = beat.get('start_time', 0)
            beat_timing_section += f"**Beat {i}** (starts at {beat_start:.1f}s, duration {beat_duration:.1f}s):\n"
            beat_timing_section += f"  Text: \"{beat_text}{'...' if len(beat.get('text', '')) > 80 else ''}\"\n"
            beat_timing_section += f"  → Animation for this beat should take ~{beat_duration:.1f} seconds\n\n"
        
        beat_timing_section += f"\n**TOTAL AUDIO DURATION: {total_audio_duration:.1f} seconds**\n"
        beat_timing_section += "**SYNCHRONIZATION STRATEGY**:\n"
        beat_timing_section += "- Structure your animation into phases matching the beats above\n"
        beat_timing_section += "- Use comments like '# Beat 1: ...' to mark each beat's animation\n"
        beat_timing_section += "- Ensure each beat's animation duration matches its audio duration\n"
        beat_timing_section += "- Use self.wait() to pad if needed to match exact timing\n"
        beat_timing_section += "- Example: If Beat 1 is 8.5s, your animations + waits for Beat 1 should total 8.5s\n"
    
    base_prompt = f"""
Generate a Manim animation scene for this segment of a 3Blue1Brown-style educational video.

## Segment: {title}
## Running Example: {running_example}

### Intuition Section:
- Core Insight: {intuition.get('core_insight', '')}
- Visual Metaphor: {intuition.get('visual_metaphor', '')}
- Key Visuals to Show: {json.dumps(intuition.get('key_visuals', []), indent=2)}
- Transformations to Animate: {json.dumps(intuition.get('transformations_to_show', []), indent=2)}

### Technical Section:
- Math Bridge: {technical.get('intuition_to_math_bridge', '')}
- Key Equations: {json.dumps(technical.get('key_equations', []), indent=2)}

### Narration (FULL TEXT - {word_count} words):
{narration}
{beat_timing_section}
### CRITICAL DURATION REQUIREMENT:
- Narration word count: {word_count} words
- Estimated narration duration: {estimated_narration_duration:.1f} seconds
- **Your animation MUST run for at least {target_animation_duration:.1f} seconds**
- Strategy: Use longer run_time values, add extended self.wait() periods, and include a long final hold
- The final frame should remain visible while the narration completes

## Requirements:
1. Create a complete, executable Manim Scene class
2. Visualize the key visuals and transformations described
3. Include any relevant equations using MathTex (not Tex for math symbols)
4. Use smooth animations and 3Blue1Brown style (dark background, clear colors)
5. **CRITICAL**: The total scene duration MUST be at least {target_animation_duration:.1f} seconds to match the narration length
6. Add a comment at the top of your construct() method showing your duration planning breakdown
7. **IF BEAT TIMING PROVIDED**: Structure animations to match each beat's duration exactly

Output a JSON object with:
- scene_id: "{segment_id}"
- class_name: A descriptive PascalCase name
- code: Complete Python code with imports (from manim import *)
"""

    previous_error = None

    for attempt in range(max_retries):
        logger.info(f"    Attempt {attempt + 1}/{max_retries}")

        # Build prompt with error feedback if retry
        if previous_error:
            rag_context = fetch_rag_context_for_error(previous_error, chroma_path)
            prompt = f"""{base_prompt}

## PREVIOUS ATTEMPT FAILED - FIX THESE ERRORS:

Error output:
```
{previous_error[:2000]}
```

{f"## Relevant Manim Documentation:{chr(10)}{rag_context}" if rag_context else ""}

Fix the errors and regenerate the complete scene code.
"""
        else:
            prompt = base_prompt

        # Generate code
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        llm_response = call_llm_provider(messages, model_name, ManimSceneCode)
        content = llm_response.content

        if not content:
            logger.warning(f"      Empty response from LLM")
            continue

        try:
            scene_code = ManimSceneCode.model_validate_json(content)
        except Exception as e:
            # Try to extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*"code"[\s\S]*\}', content)
            if json_match:
                try:
                    scene_code = ManimSceneCode.model_validate_json(json_match.group())
                except:
                    logger.error(f"      Parse error: {e}")
                    continue
            else:
                logger.error(f"      Parse error: {e}")
                continue

        # Execute the code
        logger.info(f"      Executing Manim...")
        success, output = execute_manim_scene(scene_code.code, scene_code.class_name)

        if success:
            logger.info(f"      SUCCESS!")
            return scene_code
        else:
            logger.warning(f"      Execution failed")
            previous_error = output

    logger.error(f"    Failed after {max_retries} attempts")
    return None


def generate_all_scenes(
    explanation: dict,
    difficulty: str,
    model_name: Optional[str] = None,
    max_retries: Optional[int] = None,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db",
    audio_timeline_path: Optional[str] = None
) -> List[ManimSceneCode]:
    """Generate Manim code for all segments in the explanation."""
    running_example = explanation.get('running_example', '')
    segments = explanation.get('segments', [])

    # Load beat timeline if available
    beat_timeline_by_segment = {}
    if audio_timeline_path and os.path.exists(audio_timeline_path):
        logger.info(f"Loading beat timeline from {audio_timeline_path}")
        with open(audio_timeline_path, 'r') as f:
            audio_timeline = json.load(f)
            beat_timeline_by_segment = audio_timeline.get('segments', {})
        logger.info(f"  Loaded timing for {len(beat_timeline_by_segment)} segments")

    logger.info(f"Generating Manim code for {len(segments)} segments")
    logger.info(f"Running example: {running_example[:100]}...")

    scene_codes = []
    for i, segment in enumerate(segments):
        segment_id = segment.get('segment_id', f'seg_{i+1:02d}')
        logger.info(f"[{i+1}/{len(segments)}] Segment: {segment.get('title', 'Untitled')}")
        
        # Get beat timeline for this segment
        segment_beats = None
        if segment_id in beat_timeline_by_segment:
            segment_beats = beat_timeline_by_segment[segment_id].get('beats', [])
            logger.info(f"  Using beat timing: {len(segment_beats)} beats")
        
        scene_code = generate_scene_code(
            segment=segment,
            running_example=running_example,
            difficulty=difficulty,
            model_name=model_name,
            max_retries=max_retries,
            chroma_path=chroma_path,
            beat_timeline=segment_beats
        )
        if scene_code:
            scene_codes.append(scene_code)

    return scene_codes


def assemble_complete_code(scene_codes: List[ManimSceneCode], paper_title: str) -> str:
    """Assemble all scene codes into a single executable file."""
    header = f'''"""
Generated Manim Animation: {paper_title}

3Blue1Brown-style educational video animation.
Generated from PDF using pdf_to_manim_pipeline.

To render a scene:
    manim -pql generated_animation.py <ClassName>

To render all:
    manim -pql generated_animation.py -a
"""

from manim import *
import numpy as np

'''

    parts = [header]
    for scene_code in scene_codes:
        parts.append(f"\n# {'='*70}")
        parts.append(f"# Scene: {scene_code.scene_id}")
        parts.append(f"# {'='*70}\n")
        parts.append(scene_code.code)
        parts.append("\n")

    return "\n".join(parts)


def _is_stage_cached(checkpoints: dict, stage_name: str) -> bool:
    """Check if a stage has a valid checkpoint (artifacts exist and hashes match)."""
    if stage_name not in checkpoints:
        return False
    return validate_checkpoint(checkpoints[stage_name])


def run_pipeline(
    pdf_path: str,
    difficulty: str = "medium",
    output_dir: str = "src/research_viz/manim_generator/output",
    model_name: Optional[str] = None,
    max_retries: Optional[int] = None,
    skip_explanation: bool = False,
    explanation_path: Optional[str] = None,
    force_restart: bool = False,
) -> Optional[str]:
    """
    Run the complete PDF to Manim pipeline.

    Args:
        pdf_path: Path to the research paper PDF
        difficulty: Required. Selects model tier (hard, medium, easy).
        output_dir: Directory for output files
        model_name: Optional model override for code gen
        max_retries: Max retries for code generation per segment
        skip_explanation: If True, use existing explanation file
        explanation_path: Path to existing explanation JSON (if skip_explanation=True)
        force_restart: If True, ignore all checkpoints and re-run from scratch

    Returns:
        Path to generated Manim code file, or None on failure
    """
    from research_viz.pipeline.run_metrics import RunMetricsCollector

    cfg = get_config()
    if model_name is None:
        model_name = cfg.llm.get_model("code_gen_model", difficulty)
    if max_retries is None:
        max_retries = cfg.manim.max_retries
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pdf_stem = Path(pdf_path).stem

    collector = RunMetricsCollector()
    provider = get_provider()

    try:
        # Load checkpoints for resume support
        checkpoints = {} if force_restart else read_checkpoints(output_dir)

        # Step 1: Generate or load explanation
        explanation_output = f"{output_dir}/{pdf_stem}_explanation.json"
        with collector.time_stage("explanation", provider):
            if skip_explanation and explanation_path:
                logger.info(f"Loading existing explanation: {explanation_path}")
                with open(explanation_path, 'r') as f:
                    explanation = json.load(f)
            elif _is_stage_cached(checkpoints, "explanation"):
                logger.info(f"Resuming: explanation stage cached, loading from checkpoint")
                with open(explanation_output, 'r') as f:
                    explanation = json.load(f)
            else:
                logger.info(f"Generating explanation from PDF: {pdf_path}")
                from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
                explanation = generate_explanation_from_pdf(
                    pdf_path=pdf_path,
                    output_path=explanation_output,
                    difficulty=difficulty,
                    model_name=None,
                    max_judge_attempts=3,
                )
                if not explanation:
                    logger.error("Failed to generate explanation")
                    return None
                write_checkpoint(output_dir, "explanation", [explanation_output])

        # Step 2: Run TTS and code generation in parallel
        # Both only depend on the explanation, not on each other.
        audio_dir = f"{output_dir}/audio_beats"
        audio_timeline_path = f"{audio_dir}/beat_timeline.json"

        tts_cached = _is_stage_cached(checkpoints, "tts")
        codegen_cached = _is_stage_cached(checkpoints, "codegen")

        def _run_tts():
            from research_viz.audio_generator.beat_sync_tts import generate_beat_timeline
            explanation_json_path = f"{output_dir}/{pdf_stem}_explanation.json"
            Path(explanation_json_path).parent.mkdir(parents=True, exist_ok=True)
            with open(explanation_json_path, 'w') as ef:
                json.dump(explanation, ef, indent=2)
            return generate_beat_timeline(
                explanation_path=explanation_json_path,
                output_dir=audio_dir,
            )

        def _run_code_gen():
            return generate_all_scenes(
                explanation=explanation,
                difficulty=difficulty,
                model_name=model_name,
                max_retries=max_retries,
                audio_timeline_path=audio_timeline_path,
            )

        with collector.time_stage("tts_and_codegen", provider):
            if tts_cached and codegen_cached:
                logger.info("Resuming: TTS and codegen stages cached")
            else:
                logger.info(f"Launching TTS and code generation in parallel...")

                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = {}
                    if not tts_cached:
                        futures[executor.submit(_run_tts)] = "TTS"
                    else:
                        logger.info("  TTS cached, skipping")
                    if not codegen_cached:
                        futures[executor.submit(_run_code_gen)] = "Code generation"
                    else:
                        logger.info("  Code generation cached, skipping")

                    results = {}
                    error = None
                    for future in as_completed(futures):
                        stage_name = futures[future]
                        try:
                            results[stage_name] = future.result()
                        except Exception as exc:
                            error = (stage_name, exc)
                            for f in futures:
                                if f is not future:
                                    f.cancel()
                            break

                    if error:
                        stage_name, exc = error
                        logger.error(f"{stage_name} failed: {exc}")
                        collector.record_error("tts_and_codegen", exc, stage_name, recoverable=False)
                        return None

                    if "TTS" in results:
                        write_checkpoint(output_dir, "tts", [audio_timeline_path])
                    if "Code generation" in results:
                        pass  # Code gen artifacts are in-memory, checkpointed at assembly

        # Step 3: Assemble and save
        output_path = f"{output_dir}/{pdf_stem}_animation.py"

        with collector.time_stage("assembly", provider):
            if _is_stage_cached(checkpoints, "assembly"):
                logger.info(f"Resuming: assembly stage cached")
            else:
                if codegen_cached:
                    scene_codes = _run_code_gen()
                else:
                    scene_codes = results.get("Code generation")

                if not scene_codes:
                    logger.error("No scenes generated successfully")
                    return None

                paper_title = explanation.get('paper_title', pdf_stem)
                complete_code = assemble_complete_code(scene_codes, paper_title)

                with open(output_path, 'w') as f:
                    f.write(complete_code)
                write_checkpoint(output_dir, "assembly", [output_path])

        logger.info(f"Generated pipeline output: {output_path}")
        return output_path

    finally:
        collector.write(provider, output_dir)


def get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return 0.0


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration using ffprobe."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Error getting audio duration: {e}")
        return 0.0


def extend_video_to_duration(video_path: str, target_duration: float, output_path: str) -> bool:
    """
    Extend video to target duration by freezing the last frame.

    Args:
        video_path: Input video path
        target_duration: Target duration in seconds
        output_path: Output video path

    Returns:
        True if successful
    """
    try:
        # Get current duration
        current_duration = get_video_duration(video_path)
        extension_duration = target_duration - current_duration

        if extension_duration <= 0:
            # No extension needed, just copy
            subprocess.run(['cp', video_path, output_path], check=True)
            return True

        # Extract last frame - seek to end and extract one frame
        last_frame_path = output_path.replace('.mp4', '_lastframe.png')
        subprocess.run([
            'ffmpeg', '-y',
            '-sseof', '-1',
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            last_frame_path
        ], capture_output=True, check=True)

        # Create video from last frame with extension duration
        extended_part_path = output_path.replace('.mp4', '_extended.mp4')
        subprocess.run([
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', last_frame_path,
            '-c:v', 'libx264',
            '-t', str(extension_duration),
            '-pix_fmt', 'yuv420p',
            '-r', '15',
            extended_part_path
        ], capture_output=True, check=True)

        # Concatenate original + extended using filter_complex for reliable merging
        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-i', extended_part_path,
            '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[outv]',
            '-map', '[outv]',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            output_path
        ], capture_output=True, check=True)

        # Cleanup
        for temp_file in [last_frame_path, extended_part_path]:
            try:
                os.unlink(temp_file)
            except:
                pass

        return True
    except Exception as e:
        logger.error(f"Error extending video: {e}")
        return False


def adjust_video_speed(video_path: str, target_duration: float, output_path: str) -> bool:
    """
    Adjust video playback speed to match target duration.
    
    Args:
        video_path: Input video path
        target_duration: Target duration in seconds
        output_path: Output video path
    
    Returns:
        True if successful
    """
    try:
        current_duration = get_video_duration(video_path)
        
        if current_duration == 0:
            logger.error(f"Could not get video duration")
            return False
        
        # Calculate speed factor (PTS multiplier)
        # To slow down: setpts=PTS*2 (makes 10s video → 20s)
        # To speed up: setpts=PTS/2 (makes 10s video → 5s)
        speed_factor = current_duration / target_duration
        
        # If very close, just extend or copy
        if abs(current_duration - target_duration) < 0.1:
            if current_duration < target_duration:
                return extend_video_to_duration(video_path, target_duration, output_path)
            else:
                subprocess.run(['cp', video_path, output_path], check=True)
                return True
        
        logger.info(f"    Adjusting speed: {current_duration:.2f}s -> {target_duration:.2f}s (factor: {speed_factor:.3f}x)")
        
        # Apply speed adjustment
        # Note: setpts changes playback speed without re-encoding frames
        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_path,
            '-filter:v', f'setpts=PTS/{speed_factor}',
            '-an',  # Remove audio (we'll add it separately)
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            output_path
        ], capture_output=True, check=True)
        
        # Verify final duration
        final_duration = get_video_duration(output_path)
        logger.info(f"    Result: {final_duration:.2f}s (target: {target_duration:.2f}s)")
        
        return True
    except Exception as e:
        logger.error(f"Error adjusting video speed: {e}")
        return False


def sync_video_audio_single_pass(
    video_path: str,
    audio_path: str,
    output_path: str,
    max_speed_change: float = 0.3
) -> bool:
    """
    Single-pass ffmpeg: speed-adjust, pad, and merge audio in one command.

    Combines what was previously adjust_video_to_audio_duration + sync_audio_with_video
    into a single ffmpeg invocation, eliminating double re-encode.

    Strategy based on video vs audio duration:
    - Within max_speed_change: setpts speed adjustment + tpad + audio merge
    - Video too short: tpad freeze last frame + audio merge
    - Video too long: trim + audio merge

    Args:
        video_path: Input video path
        audio_path: Input audio path
        output_path: Output synced video with audio
        max_speed_change: Maximum allowed speed change (0.3 = 30%)

    Returns:
        True if successful
    """
    try:
        video_duration = get_video_duration(video_path)
        audio_duration = get_audio_duration(audio_path)

        if video_duration == 0 or audio_duration == 0:
            logger.error(f"Could not get duration (video={video_duration}, audio={audio_duration})")
            return False

        # Target duration includes 0.5s buffer so video fully covers audio
        target_duration = audio_duration + 0.5
        speed_ratio = abs(video_duration - audio_duration) / audio_duration

        # Build the video filter chain
        vfilters = []

        if speed_ratio <= max_speed_change and abs(video_duration - audio_duration) >= 0.1:
            # Speed adjustment needed and within limits
            speed_factor = video_duration / audio_duration
            vfilters.append(f'setpts=PTS/{speed_factor}')
            effective_duration = audio_duration  # after speed adjust
        else:
            effective_duration = video_duration

        # Pad with last frame if video (after speed adjust) is shorter than target
        pad_duration = target_duration - effective_duration
        if pad_duration > 0.05:
            vfilters.append(f'tpad=stop_mode=clone:stop_duration={pad_duration:.3f}')

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y', '-i', video_path, '-i', audio_path]

        if vfilters:
            cmd += ['-filter:v', ','.join(vfilters)]
            cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p']
        else:
            # No video filter needed — copy video stream
            cmd += ['-c:v', 'copy']

        # Trim if video is too long and speed change exceeds limit
        if speed_ratio > max_speed_change and video_duration > audio_duration:
            cmd += ['-t', f'{target_duration:.3f}']

        cmd += [
            '-c:a', 'aac', '-b:a', '192k',
            '-map', '0:v:0', '-map', '1:a:0',
            output_path
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return True

    except Exception as e:
        logger.error(f"Error in single-pass video/audio sync: {e}")
        return False


# Keep legacy functions as thin wrappers for any external callers
def adjust_video_to_audio_duration(
    video_path: str,
    audio_duration: float,
    output_path: str,
    max_speed_change: float = 0.3
) -> bool:
    """Legacy wrapper — prefer sync_video_audio_single_pass for combined operations."""
    try:
        video_duration = get_video_duration(video_path)
        speed_ratio = abs(video_duration - audio_duration) / audio_duration

        if speed_ratio <= max_speed_change:
            return adjust_video_speed(video_path, audio_duration, output_path)
        elif video_duration < audio_duration:
            return extend_video_to_duration(video_path, audio_duration, output_path)
        else:
            subprocess.run([
                'ffmpeg', '-y', '-i', video_path,
                '-t', str(audio_duration),
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                output_path
            ], capture_output=True, check=True)
            return True
    except Exception as e:
        logger.error(f"Error adjusting video to audio duration: {e}")
        return False


def sync_audio_with_video(video_path: str, audio_path: str, output_path: str) -> bool:
    """Legacy wrapper — prefer sync_video_audio_single_pass for combined operations."""
    try:
        video_duration = get_video_duration(video_path)
        audio_duration = get_audio_duration(audio_path)
        target_duration = audio_duration + 0.5

        if target_duration > video_duration:
            extended_video = output_path.replace('.mp4', '_tmp_extended.mp4')
            if not extend_video_to_duration(video_path, target_duration, extended_video):
                return False
            video_to_use = extended_video
        else:
            video_to_use = video_path

        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_to_use, '-i', audio_path,
            '-c:v', 'libx264', '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-map', '0:v:0', '-map', '1:a:0',
            output_path
        ], capture_output=True, check=True)

        if target_duration > video_duration:
            try:
                os.unlink(extended_video)
            except:
                pass

        return True
    except Exception as e:
        logger.error(f"Error syncing audio with video: {e}")
        return False


def _render_scene(
    i: int,
    scene_code: ManimSceneCode,
    output_dir: str,
    quality: str,
) -> Optional[str]:
    """Render a single Manim scene and return the video path, or None on failure."""
    quality_dirs = {'l': '480p15', 'm': '720p30', 'h': '1080p60', 'k': '2160p60'}
    quality_dir = quality_dirs.get(quality, '480p15')
    video_path = f"media/videos/temp_scene_{i+1}/{quality_dir}/{scene_code.class_name}.mp4"

    if os.path.exists(video_path):
        logger.info(f"  [{i+1}] Video already exists: {video_path}")
        return video_path

    temp_scene_path = f"{output_dir}/temp_scene_{i+1}.py"
    with open(temp_scene_path, 'w') as f:
        f.write("from manim import *\nimport numpy as np\n\n")
        f.write(scene_code.code)

    logger.info(f"  [{i+1}] Rendering Manim scene {scene_code.scene_id}...")
    try:
        result = subprocess.run(
            ['manim', f'-q{quality}', '--disable_caching', temp_scene_path, scene_code.class_name],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            logger.error(f"  [{i+1}] Manim render failed")
            logger.error(result.stderr)
            return None
    except Exception as e:
        logger.error(f"  [{i+1}] {e}")
        return None

    if not os.path.exists(video_path):
        logger.error(f"  [{i+1}] Rendered video not found at {video_path}")
        return None

    return video_path


def _sync_scene(
    i: int,
    video_path: str,
    segment_id: str,
    audio_timeline: dict,
    output_dir: str,
    max_speed_change: float,
    sync_mode: str,
) -> str:
    """Sync a rendered scene with its audio. Returns the synced (or fallback) video path."""
    synced_video_path = f"{output_dir}/synced_scene_{i+1}.mp4"
    if os.path.exists(synced_video_path):
        logger.info(f"  [{i+1}] Synced video already exists: {synced_video_path}")
        return synced_video_path

    segment_audio_data = audio_timeline.get('segments', {}).get(segment_id)
    if not segment_audio_data:
        logger.warning(f"  [{i+1}] No audio for segment {segment_id}, skipping sync")
        return video_path

    beats = segment_audio_data.get('beats', [])
    if not beats:
        logger.warning(f"  [{i+1}] No beats for segment {segment_id}")
        return video_path

    # Combine beat audio files
    segment_audio_path = f"{output_dir}/segment_{i+1}_audio.wav"
    if len(beats) == 1:
        subprocess.run(['cp', beats[0]['audio_file'], segment_audio_path])
    else:
        concat_list = f"{output_dir}/segment_{i+1}_audio_concat.txt"
        with open(concat_list, 'w') as f:
            for beat in beats:
                f.write(f"file '{os.path.abspath(beat['audio_file'])}'\n")
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_list, '-c', 'copy', segment_audio_path
        ], capture_output=True)
        os.unlink(concat_list)

    logger.info(f"  [{i+1}] Syncing audio with video (single-pass, mode: {sync_mode})...")
    if sync_video_audio_single_pass(video_path, segment_audio_path, synced_video_path, max_speed_change):
        logger.info(f"  [{i+1}] SUCCESS: {synced_video_path}")
        return synced_video_path
    else:
        logger.warning(f"  [{i+1}] Single-pass sync failed, using raw video")
        return video_path


def render_and_sync_all_scenes(
    scene_codes: List[ManimSceneCode],
    explanation: dict,
    audio_timeline_path: str,
    output_dir: str,
    quality: str = "l",
    sync_mode: str = "segment",
    max_speed_change: float = 0.3
) -> Optional[str]:
    """
    Render all Manim scenes, sync with audio, and stitch together.

    Uses a producer-consumer pattern: render pool produces completed scenes
    and sync pool processes them as they finish, overlapping render and sync work.

    Args:
        scene_codes: List of generated scene codes
        explanation: Explanation dict with segments
        audio_timeline_path: Path to beat timeline JSON
        output_dir: Output directory
        quality: Manim quality (-ql, -qm, -qh)
        sync_mode: Sync granularity - "segment" (default) or "beat"
        max_speed_change: Maximum allowed speed adjustment (0.3 = 30%)

    Returns:
        Path to final stitched video, or None on failure
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    with open(audio_timeline_path, 'r') as f:
        audio_timeline = json.load(f)

    segments = explanation.get('segments', [])
    cfg = get_config()

    logger.info("=" * 70)
    logger.info("RENDERING AND SYNCING SCENES (pipeline-parallel)")
    logger.info("=" * 70)
    logger.info(f"Scenes: {len(scene_codes)} | Quality: {quality} | Sync: {sync_mode}")
    logger.info(f"Render workers: {cfg.video.render_workers} | Sync workers: {cfg.video.sync_workers}")

    # Result slots — preserve scene ordering
    synced_videos: list[Optional[str]] = [None] * len(scene_codes)

    # Producer-consumer: render pool feeds sync pool
    render_pool = ThreadPoolExecutor(max_workers=cfg.video.render_workers)
    sync_pool = ThreadPoolExecutor(max_workers=cfg.video.sync_workers)

    def _render_then_sync(i: int, scene_code: ManimSceneCode) -> tuple[int, Optional[str]]:
        segment = segments[i] if i < len(segments) else {}
        segment_id = segment.get('segment_id', f'seg_{i+1:02d}')

        video_path = _render_scene(i, scene_code, output_dir, quality)
        if video_path is None:
            return (i, None)

        # Submit sync to the sync pool and wait for it
        sync_future = sync_pool.submit(
            _sync_scene, i, video_path, segment_id,
            audio_timeline, output_dir, max_speed_change, sync_mode,
        )
        return (i, sync_future.result())

    # Submit all render tasks
    render_futures = {
        render_pool.submit(_render_then_sync, i, sc): i
        for i, sc in enumerate(scene_codes)
    }

    for future in as_completed(render_futures):
        idx, result_path = future.result()
        synced_videos[idx] = result_path

    render_pool.shutdown(wait=True)
    sync_pool.shutdown(wait=True)

    # Filter out failed scenes (None entries)
    final_videos = [v for v in synced_videos if v is not None]

    if not final_videos:
        logger.error("No videos to stitch")
        return None

    # Stitch all videos together
    logger.info("=" * 70)
    logger.info("STITCHING VIDEOS")
    logger.info("=" * 70)
    logger.info(f"Videos to stitch: {len(final_videos)}")

    concat_list_path = f"{output_dir}/final_concat.txt"
    with open(concat_list_path, 'w') as f:
        for video in final_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")

    final_output = f"{output_dir}/final_video.mp4"
    try:
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_list_path,
            '-c:v', 'libx264', '-c:a', 'aac',
            '-b:a', '192k', '-pix_fmt', 'yuv420p',
            final_output
        ], capture_output=True, check=True)

        logger.info(f"SUCCESS! Final video: {final_output}")
        final_duration = get_video_duration(final_output)
        logger.info(f"Duration: {final_duration:.1f}s ({final_duration/60:.1f} min)")

        return final_output
    except Exception as e:
        logger.error(f"Error stitching videos: {e}")
        return None


def main(
    pdf_path: Optional[str] = None,
    explanation_path: Optional[str] = None,
    difficulty: str = "medium",
    output_dir: str = "src/research_viz/manim_generator/output",
    model_name: Optional[str] = None,
    max_retries: Optional[int] = None,
    generate_audio: bool = False,
    tts_voice: Optional[str] = None,
    render_video: bool = False,
    video_quality: Optional[str] = None,
    sync_mode: Optional[str] = None,
    max_speed_change: Optional[float] = None,
    force_restart: bool = False,
):
    """
    Generate Manim animation from a PDF research paper.

    Args:
        pdf_path: Path to PDF (generates new explanation)
        explanation_path: Path to existing explanation JSON (skips PDF processing)
        output_dir: Output directory
        model_name: LLM model to use
        max_retries: Max retries per segment
        generate_audio: Generate TTS audio for narrations
        tts_voice: Voice to use for TTS
        render_video: Render scenes and create final video
        video_quality: Manim quality (l=low, m=medium, h=high)
        sync_mode: Audio-video sync mode - "segment" (default) or "beat"
        max_speed_change: Maximum video speed adjustment (0.3 = 30%)
        force_restart: Ignore all checkpoints and re-run from scratch

    Sync Modes:
        - "segment": Adjust entire segment video to match audio (smoother, simpler)
        - "beat": Adjust each beat separately (more precise, experimental)

    Examples:
        # Generate code only
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --explanation-path output/attention_explanation.json

        # Generate with segment-level sync (default, recommended)
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --explanation-path output/attention_explanation.json \\
            --generate-audio --render-video \\
            --sync-mode segment --max-speed-change 0.3

        # Try beat-level sync (experimental)
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --explanation-path output/attention_explanation.json \\
            --generate-audio --render-video \\
            --sync-mode beat --max-speed-change 0.2
    """
    from research_viz.pipeline.run_metrics import RunMetricsCollector

    cfg = get_config()
    if model_name is None:
        model_name = cfg.llm.get_model("code_gen_model", difficulty)
    if max_retries is None:
        max_retries = cfg.manim.max_retries
    if tts_voice is None:
        tts_voice = cfg.audio.voice
    if video_quality is None:
        video_quality = cfg.video.quality
    if sync_mode is None:
        sync_mode = cfg.video.sync_mode
    if max_speed_change is None:
        max_speed_change = cfg.video.max_speed_change

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    collector = RunMetricsCollector()
    provider = get_provider()

    try:
        # Step 1: Load or generate explanation
        with collector.time_stage("explanation", provider):
            if explanation_path and os.path.exists(explanation_path):
                logger.info(f"Loading existing explanation: {explanation_path}")
                with open(explanation_path, 'r') as f:
                    explanation = json.load(f)
                used_explanation_path = explanation_path
                pdf_stem = Path(explanation_path).stem.replace('_explanation', '')
            elif pdf_path and os.path.exists(pdf_path):
                pdf_stem = Path(pdf_path).stem
                explanation_output = f"{output_dir}/{pdf_stem}_explanation.json"
                if os.path.exists(explanation_output):
                    logger.info(f"Explanation already exists, loading: {explanation_output}")
                    with open(explanation_output, 'r') as f:
                        explanation = json.load(f)
                else:
                    logger.info(f"Generating explanation from PDF: {pdf_path}")
                    from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
                    explanation = generate_explanation_from_pdf(
                        pdf_path=pdf_path,
                        output_path=explanation_output,
                        difficulty=difficulty,
                        model_name=None,
                        max_judge_attempts=3,
                    )
                    if not explanation:
                        logger.error("Failed to generate explanation")
                        return
                used_explanation_path = explanation_output
            else:
                logger.error("Provide either --pdf-path or --explanation-path")
                return

        # Step 2: Generate audio if requested
        audio_timeline_path = None
        if generate_audio or render_video:
            audio_dir = f"{output_dir}/audio_beats"
            audio_timeline_path = f"{audio_dir}/beat_timeline.json"

            with collector.time_stage("tts", provider):
                if os.path.exists(audio_timeline_path):
                    logger.info(f"Audio already exists, skipping: {audio_timeline_path}")
                else:
                    logger.info("Generating TTS audio...")
                    from research_viz.audio_generator.beat_sync_tts import generate_beat_timeline
                    generate_beat_timeline(
                        explanation_path=used_explanation_path,
                        output_dir=audio_dir,
                        voice=tts_voice
                    )
                    logger.info(f"Audio generation complete: {audio_timeline_path}")

        # Step 3: Generate Manim code
        code_output_path = f"{output_dir}/{pdf_stem}_animation.py"
        scene_metadata_path = f"{output_dir}/{pdf_stem}_scene_metadata.json"

        with collector.time_stage("codegen", provider):
            if os.path.exists(code_output_path) and os.path.exists(scene_metadata_path):
                logger.info(f"Manim code already exists, skipping: {code_output_path}")
                with open(scene_metadata_path, 'r') as f:
                    scene_data = json.load(f)
                scene_codes = [ManimSceneCode(**scene) for scene in scene_data]
            else:
                logger.info("Generating Manim code...")
                scene_codes = generate_all_scenes(
                    explanation=explanation,
                    difficulty=difficulty,
                    model_name=model_name,
                    max_retries=max_retries,
                    audio_timeline_path=audio_timeline_path,
                )

                if not scene_codes:
                    logger.error("No scenes generated successfully")
                    return

                paper_title = explanation.get('paper_title', pdf_stem)
                complete_code = assemble_complete_code(scene_codes, paper_title)
                with open(code_output_path, 'w') as f:
                    f.write(complete_code)
                with open(scene_metadata_path, 'w') as f:
                    json.dump([scene.model_dump() for scene in scene_codes], f, indent=2)

                logger.info(f"Code generation complete: {len(scene_codes)} scenes -> {code_output_path}")

        # Step 4: Render video if requested
        if render_video:
            if not audio_timeline_path:
                logger.error("Cannot render video without audio. Enable --generate-audio")
                return

            with collector.time_stage("render", provider):
                final_video = render_and_sync_all_scenes(
                    scene_codes=scene_codes,
                    explanation=explanation,
                    audio_timeline_path=audio_timeline_path,
                    output_dir=output_dir,
                    quality=video_quality,
                    sync_mode=sync_mode,
                    max_speed_change=max_speed_change
                )

            if final_video:
                logger.info(f"Pipeline complete! Final video: {final_video}")
            else:
                logger.error(f"Video rendering failed")

    finally:
        collector.write(provider, output_dir)


if __name__ == "__main__":
    tyro.cli(main)
