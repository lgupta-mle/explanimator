"""
PDF to Manim Pipeline

Complete pipeline: PDF → 3B1B Explanation → Manim Code with execution feedback.
Uses RAG only when execution errors occur.
"""

import copy
import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
import tyro
from dotenv import load_dotenv

from research_viz.manim_generator.pdf_explanation_generator import (
    create_pdf_llm_response,
    load_prompt,
    encode_pdf_to_base64
)
from research_viz.utils.llm_utils import call_openrouter
from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B, Segment3B1B
from research_viz.config.difficulty import DifficultyConfig, DIFFICULTY_CONFIGS
from research_viz.schemas.language_schemas import LanguageConfig, SUPPORTED_LANGUAGES

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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['manim', 'render', '-ql', '--disable_caching', temp_path, class_name],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            error_output = result.stderr or result.stdout
            return False, error_output

    except subprocess.TimeoutExpired:
        return False, "Timeout: Manim render took too long (>120s)"
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
        print(f"    RAG error: {e}")

    return ""


def generate_scene_code(
    segment: dict,
    running_example: str,
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
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
        print(f"    Attempt {attempt + 1}/{max_retries}")

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

        response = call_openrouter(messages, model_name, ManimSceneCode)

        if "error" in response:
            print(f"      API error: {response['error']}")
            continue

        if "choices" not in response or len(response["choices"]) == 0:
            print(f"      Invalid response")
            continue

        content = response["choices"][0]["message"]["content"]

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
                    print(f"      Parse error: {e}")
                    continue
            else:
                print(f"      Parse error: {e}")
                continue

        # Execute the code
        print(f"      Executing Manim...")
        success, output = execute_manim_scene(scene_code.code, scene_code.class_name)

        if success:
            print(f"      SUCCESS!")
            return scene_code
        else:
            print(f"      Execution failed")
            previous_error = output

    print(f"    Failed after {max_retries} attempts")
    return None


def generate_all_scenes(
    explanation: dict,
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db",
    audio_timeline_path: Optional[str] = None
) -> List[ManimSceneCode]:
    """Generate Manim code for all segments in the explanation."""
    running_example = explanation.get('running_example', '')
    segments = explanation.get('segments', [])

    # Load beat timeline if available
    beat_timeline_by_segment = {}
    if audio_timeline_path and os.path.exists(audio_timeline_path):
        print(f"\nLoading beat timeline from {audio_timeline_path}")
        with open(audio_timeline_path, 'r') as f:
            audio_timeline = json.load(f)
            beat_timeline_by_segment = audio_timeline.get('segments', {})
        print(f"  Loaded timing for {len(beat_timeline_by_segment)} segments")

    print(f"\nGenerating Manim code for {len(segments)} segments")
    print(f"Running example: {running_example[:100]}...")

    scene_codes = []
    for i, segment in enumerate(segments):
        segment_id = segment.get('segment_id', f'seg_{i+1:02d}')
        print(f"\n[{i+1}/{len(segments)}] Segment: {segment.get('title', 'Untitled')}")
        
        # Get beat timeline for this segment
        segment_beats = None
        if segment_id in beat_timeline_by_segment:
            segment_beats = beat_timeline_by_segment[segment_id].get('beats', [])
            print(f"  Using beat timing: {len(segment_beats)} beats")
        
        scene_code = generate_scene_code(
            segment=segment,
            running_example=running_example,
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


def run_pipeline(
    pdf_path: str,
    output_dir: str = "src/research_viz/manim_generator/output",
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
    skip_explanation: bool = False,
    explanation_path: Optional[str] = None
) -> Optional[str]:
    """
    Run the complete PDF to Manim pipeline.

    Args:
        pdf_path: Path to the research paper PDF
        output_dir: Directory for output files
        model_name: LLM model to use
        max_retries: Max retries for code generation per segment
        skip_explanation: If True, use existing explanation file
        explanation_path: Path to existing explanation JSON (if skip_explanation=True)

    Returns:
        Path to generated Manim code file, or None on failure
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pdf_stem = Path(pdf_path).stem

    # Step 1: Generate or load explanation
    if skip_explanation and explanation_path:
        print(f"Loading existing explanation: {explanation_path}")
        with open(explanation_path, 'r') as f:
            explanation = json.load(f)
    else:
        print(f"Generating explanation from PDF: {pdf_path}")
        from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
        explanation_output = f"{output_dir}/{pdf_stem}_explanation.json"
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_output,
            model_name=model_name,
            max_judge_attempts=3
        )
        if not explanation:
            print("Failed to generate explanation")
            return None

    # Step 2: Generate Manim code for all segments
    scene_codes = generate_all_scenes(
        explanation=explanation,
        model_name=model_name,
        max_retries=max_retries
    )

    if not scene_codes:
        print("No scenes generated successfully")
        return None

    # Step 3: Assemble and save
    paper_title = explanation.get('paper_title', pdf_stem)
    complete_code = assemble_complete_code(scene_codes, paper_title)

    output_path = f"{output_dir}/{pdf_stem}_animation.py"
    with open(output_path, 'w') as f:
        f.write(complete_code)

    print(f"\n{'='*70}")
    print(f"SUCCESS!")
    print(f"{'='*70}")
    print(f"Generated {len(scene_codes)} scenes")
    print(f"Output: {output_path}")
    print(f"\nTo render:")
    print(f"  manim -pql {output_path} <ClassName>")

    return output_path


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
        print(f"Error getting video duration: {e}")
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
        print(f"Error getting audio duration: {e}")
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
        print(f"Error extending video: {e}")
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
            print(f"Error: Could not get video duration")
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
        
        print(f"    Adjusting speed: {current_duration:.2f}s → {target_duration:.2f}s (factor: {speed_factor:.3f}x)")
        
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
        print(f"    Result: {final_duration:.2f}s (target: {target_duration:.2f}s)")
        
        return True
    except Exception as e:
        print(f"Error adjusting video speed: {e}")
        return False


def adjust_video_to_audio_duration(
    video_path: str,
    audio_duration: float,
    output_path: str,
    max_speed_change: float = 0.3
) -> bool:
    """
    Adjust video to match audio duration with configurable speed limits.
    
    Args:
        video_path: Input video path
        audio_duration: Target audio duration
        output_path: Output adjusted video
        max_speed_change: Maximum allowed speed change (0.3 = 30%)
    
    Returns:
        True if successful
    """
    try:
        video_duration = get_video_duration(video_path)
        
        # Calculate required speed change
        speed_ratio = abs(video_duration - audio_duration) / audio_duration
        
        print(f"    Video: {video_duration:.2f}s, Audio: {audio_duration:.2f}s")
        print(f"    Speed change required: {speed_ratio*100:.1f}%")
        
        # If speed change is within limits, adjust speed
        if speed_ratio <= max_speed_change:
            print(f"    Using speed adjustment (within {max_speed_change*100:.0f}% limit)")
            return adjust_video_speed(video_path, audio_duration, output_path)
        else:
            # Speed change too large, use extend/trim approach
            print(f"    Speed change too large, using extend/trim approach")
            if video_duration < audio_duration:
                # Extend by freezing last frame
                return extend_video_to_duration(video_path, audio_duration, output_path)
            else:
                # Trim to target duration (lose some content at end)
                print(f"    WARNING: Video too long, trimming from {video_duration:.2f}s to {audio_duration:.2f}s")
                subprocess.run([
                    'ffmpeg', '-y',
                    '-i', video_path,
                    '-t', str(audio_duration),
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    output_path
                ], capture_output=True, check=True)
                return True
        
    except Exception as e:
        print(f"Error adjusting video to audio duration: {e}")
        return False


def sync_audio_with_video(video_path: str, audio_path: str, output_path: str) -> bool:
    """
    Sync audio with video, extending video if needed.

    Args:
        video_path: Input video path
        audio_path: Input audio path
        output_path: Output synced video path

    Returns:
        True if successful
    """
    try:
        video_duration = get_video_duration(video_path)
        audio_duration = get_audio_duration(audio_path)

        print(f"    Video: {video_duration:.2f}s, Audio: {audio_duration:.2f}s")

        # Add a small buffer (0.5s) to ensure video fully covers audio
        # This prevents black screen issues from minor timing discrepancies
        target_duration = audio_duration + 0.5
        
        if target_duration > video_duration:
            print(f"    Extending video by {target_duration - video_duration:.2f}s (includes 0.5s buffer)")
            extended_video = output_path.replace('.mp4', '_tmp_extended.mp4')
            if not extend_video_to_duration(video_path, target_duration, extended_video):
                return False
            video_to_use = extended_video
        else:
            video_to_use = video_path

        # Merge audio with video (re-encode to ensure compatibility)
        # IMPORTANT: Removed -shortest flag to prevent premature video cutoff
        # Using explicit stream mapping to ensure video plays for full audio duration
        subprocess.run([
            'ffmpeg', '-y',
            '-i', video_to_use,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-map', '0:v:0',  # Map video from first input
            '-map', '1:a:0',  # Map audio from second input
            output_path
        ], capture_output=True, check=True)

        # Cleanup temp extended video
        if target_duration > video_duration:
            try:
                os.unlink(extended_video)
            except:
                pass

        return True
    except Exception as e:
        print(f"Error syncing audio with video: {e}")
        return False


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
        
    Sync Modes:
        - "segment": Adjust entire segment video to match segment audio (simpler, smoother)
        - "beat": Adjust each beat separately for frame-perfect sync (more precise)
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Load audio timeline
    with open(audio_timeline_path, 'r') as f:
        audio_timeline = json.load(f)

    segments = explanation.get('segments', [])

    print(f"\n{'='*70}")
    print("RENDERING AND SYNCING SCENES")
    print(f"{'='*70}")
    print(f"Scenes to render: {len(scene_codes)}")
    print(f"Quality: {quality}")
    print(f"Sync mode: {sync_mode}")
    print(f"Max speed change: {max_speed_change*100:.0f}%")

    synced_videos = []

    for i, scene_code in enumerate(scene_codes):
        segment = segments[i] if i < len(segments) else {}
        segment_id = segment.get('segment_id', f'seg_{i+1:02d}')

        print(f"\n[{i+1}/{len(scene_codes)}] Scene: {scene_code.scene_id}")

        # Find rendered video - Manim quality mapping
        quality_dirs = {
            'l': '480p15',
            'm': '720p30',
            'h': '1080p60',
            'k': '2160p60'
        }
        quality_dir = quality_dirs.get(quality, '480p15')
        video_pattern = f"media/videos/temp_scene_{i+1}/{quality_dir}/{scene_code.class_name}.mp4"

        # Check if video already exists
        if os.path.exists(video_pattern):
            print(f"  Video already exists: {video_pattern}")
        else:
            # Write scene to temp file
            temp_scene_path = f"{output_dir}/temp_scene_{i+1}.py"
            with open(temp_scene_path, 'w') as f:
                f.write("from manim import *\nimport numpy as np\n\n")
                f.write(scene_code.code)

            # Render scene
            print(f"  Rendering Manim scene...")
            try:
                result = subprocess.run(
                    ['manim', f'-q{quality}', '--disable_caching', temp_scene_path, scene_code.class_name],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode != 0:
                    print(f"  ERROR: Manim render failed")
                    print(result.stderr)
                    continue
            except Exception as e:
                print(f"  ERROR: {e}")
                continue

            if not os.path.exists(video_pattern):
                print(f"  ERROR: Rendered video not found at {video_pattern}")
                continue

        # Check if synced video already exists
        synced_video_path = f"{output_dir}/synced_scene_{i+1}.mp4"
        if os.path.exists(synced_video_path):
            print(f"  Synced video already exists: {synced_video_path}")
            synced_videos.append(synced_video_path)
            continue

        # Get audio for this segment
        segment_audio_data = audio_timeline.get('segments', {}).get(segment_id)
        if not segment_audio_data:
            print(f"  WARNING: No audio found for segment {segment_id}, skipping sync")
            synced_videos.append(video_pattern)
            continue

        # Concatenate all beat audio files for this segment
        beats = segment_audio_data.get('beats', [])
        if not beats:
            print(f"  WARNING: No beats found for segment {segment_id}")
            synced_videos.append(video_pattern)
            continue

        # Combine beat audio files
        segment_audio_path = f"{output_dir}/segment_{i+1}_audio.wav"
        if len(beats) == 1:
            # Single beat, just copy
            subprocess.run(['cp', beats[0]['audio_file'], segment_audio_path])
        else:
            # Multiple beats, concatenate
            concat_list = f"{output_dir}/segment_{i+1}_audio_concat.txt"
            with open(concat_list, 'w') as f:
                for beat in beats:
                    f.write(f"file '{os.path.abspath(beat['audio_file'])}'\n")
            subprocess.run([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_list,
                '-c', 'copy',
                segment_audio_path
            ], capture_output=True)
            os.unlink(concat_list)

        # Sync audio with video based on mode
        print(f"  Syncing audio with video (mode: {sync_mode})...")
        
        if sync_mode == "segment":
            # SEGMENT-LEVEL SYNC: Adjust entire video to match total audio duration
            segment_audio_duration = get_audio_duration(segment_audio_path)
            
            # First adjust video duration to match audio
            adjusted_video_path = f"{output_dir}/adjusted_scene_{i+1}.mp4"
            if adjust_video_to_audio_duration(
                video_pattern,
                segment_audio_duration,
                adjusted_video_path,
                max_speed_change
            ):
                # Then merge audio with adjusted video
                if sync_audio_with_video(adjusted_video_path, segment_audio_path, synced_video_path):
                    print(f"  SUCCESS: {synced_video_path}")
                    synced_videos.append(synced_video_path)
                    # Cleanup temp file
                    try:
                        os.unlink(adjusted_video_path)
                    except:
                        pass
                else:
                    print(f"  WARNING: Audio merge failed, using adjusted video")
                    synced_videos.append(adjusted_video_path)
            else:
                print(f"  WARNING: Duration adjustment failed, using original sync")
                if sync_audio_with_video(video_pattern, segment_audio_path, synced_video_path):
                    synced_videos.append(synced_video_path)
                else:
                    synced_videos.append(video_pattern)
        
        elif sync_mode == "beat":
            # BEAT-LEVEL SYNC: Process each beat separately
            # TODO: This requires splitting the video into beats, which is complex
            # For now, fall back to segment sync with a warning
            print(f"  WARNING: Beat-level sync requires per-beat video rendering")
            print(f"  Falling back to segment-level sync")
            
            segment_audio_duration = get_audio_duration(segment_audio_path)
            adjusted_video_path = f"{output_dir}/adjusted_scene_{i+1}.mp4"
            
            if adjust_video_to_audio_duration(
                video_pattern,
                segment_audio_duration,
                adjusted_video_path,
                max_speed_change
            ):
                if sync_audio_with_video(adjusted_video_path, segment_audio_path, synced_video_path):
                    synced_videos.append(synced_video_path)
                    try:
                        os.unlink(adjusted_video_path)
                    except:
                        pass
                else:
                    synced_videos.append(adjusted_video_path)
            else:
                if sync_audio_with_video(video_pattern, segment_audio_path, synced_video_path):
                    synced_videos.append(synced_video_path)
                else:
                    synced_videos.append(video_pattern)
        
        else:
            # Unknown mode, use old method
            print(f"  WARNING: Unknown sync mode '{sync_mode}', using default")
            if sync_audio_with_video(video_pattern, segment_audio_path, synced_video_path):
                synced_videos.append(synced_video_path)
            else:
                synced_videos.append(video_pattern)

    if not synced_videos:
        print("\nERROR: No videos to stitch")
        return None

    # Stitch all videos together
    print(f"\n{'='*70}")
    print("STITCHING VIDEOS")
    print(f"{'='*70}")
    print(f"Videos to stitch: {len(synced_videos)}")

    concat_list_path = f"{output_dir}/final_concat.txt"
    with open(concat_list_path, 'w') as f:
        for video in synced_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")

    final_output = f"{output_dir}/final_video.mp4"
    try:
        # Re-encode to ensure audio/video consistency across all clips
        subprocess.run([
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            final_output
        ], capture_output=True, check=True)

        print(f"\n{'='*70}")
        print("SUCCESS!")
        print(f"{'='*70}")
        print(f"Final video: {final_output}")

        final_duration = get_video_duration(final_output)
        print(f"Duration: {final_duration:.1f}s ({final_duration/60:.1f} min)")

        return final_output
    except Exception as e:
        print(f"ERROR stitching videos: {e}")
        return None


def main(
    pdf_path: Optional[str] = None,
    explanation_path: Optional[str] = None,
    output_dir: str = "src/research_viz/manim_generator/output",
    model_name: str = "google/gemini-3.1-pro-preview",
    max_retries: int = 3,
    generate_audio: bool = True,
    tts_voice: str = "nova",
    render_video: bool = True,
    video_quality: str = "m",
    sync_mode: str = "segment",
    max_speed_change: float = 0.3,
    difficulty: str = "medium",
    language: str = "en"
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
        difficulty: Difficulty level - easy, medium, or hard (default: medium)
        language: ISO 639-1 language code (default: en). Supported: en, es, fr, de, ja, zh, ko, hi, ar, ru, pt

    Examples:
        # Generate in Spanish with easy difficulty
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --pdf-path papers/attention.pdf --difficulty easy --language es --generate-audio --render-video

        # Generate in Japanese
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --pdf-path papers/attention.pdf --language ja --generate-audio --render-video
    """
    if difficulty not in DIFFICULTY_CONFIGS:
        print(f"ERROR: Invalid difficulty '{difficulty}'. Choose from: easy, medium, hard")
        return

    if language not in SUPPORTED_LANGUAGES:
        print(f"ERROR: Unsupported language '{language}'. Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}")
        return

    difficulty_config = DIFFICULTY_CONFIGS[difficulty]
    lang_config = SUPPORTED_LANGUAGES[language]
    print(f"Difficulty: {difficulty} (segments: {difficulty_config.min_segments}-{difficulty_config.max_segments})")
    print(f"Language: {lang_config.name} ({language})")

    # Font availability check for non-Latin scripts
    if lang_config.font:
        try:
            result = subprocess.run(
                ['fc-list', f':family={lang_config.font}'],
                capture_output=True, text=True, timeout=5
            )
            if not result.stdout.strip():
                print(f"WARNING: Font '{lang_config.font}' not found. Install it for proper {lang_config.name} rendering.")
                print(f"  On macOS: brew install --cask font-noto-sans-{lang_config.name.lower()}")
                print(f"  On Ubuntu: sudo apt install fonts-noto-{lang_config.script}")
        except Exception:
            pass  # fc-list not available, skip check

    # Determine pdf_stem early so we can build the run-specific output dir
    if explanation_path and os.path.exists(explanation_path):
        pdf_stem = Path(explanation_path).stem.replace('_explanation', '').split('_explanation_')[0]
    elif pdf_path and os.path.exists(pdf_path):
        pdf_stem = Path(pdf_path).stem
    else:
        print("ERROR: Provide either --pdf-path or --explanation-path")
        return

    # Create run-specific subdirectory so different difficulty/language combos don't collide
    run_dir = f"{output_dir}/{pdf_stem}_{difficulty}_{language}"
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {run_dir}")

    # Step 1: Load or generate explanation
    if explanation_path and os.path.exists(explanation_path):
        print(f"Loading existing explanation: {explanation_path}")
        with open(explanation_path, 'r') as f:
            explanation = json.load(f)
        used_explanation_path = explanation_path
    elif pdf_path:
        print(f"Generating explanation from PDF: {pdf_path}")
        from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
        explanation_output = f"{run_dir}/{pdf_stem}_explanation.json"
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_output,
            model_name=model_name,
            max_judge_attempts=3,
            difficulty_config=difficulty_config
        )
        if not explanation:
            print("Failed to generate explanation")
            return
        used_explanation_path = explanation_output

    # Step 1b: Translate narration if non-English
    # Use a deep copy so the original English explanation stays intact for Manim code gen
    translated_explanation = None
    translator = None
    if language != "en":
        print(f"\n{'='*70}")
        print(f"TRANSLATING NARRATION TO {lang_config.name.upper()}")
        print(f"{'='*70}")
        from research_viz.translation.translator import NarrationTranslator
        translator = NarrationTranslator()
        translated_explanation = copy.deepcopy(explanation)
        for segment in translated_explanation.get("segments", []):
            segment["narration_script_original"] = segment["narration_script"]
            segment["narration_script"] = translator.translate_narration(
                segment["narration_script"], lang_config
            )
            print(f"  Translated segment: {segment.get('segment_id', '?')}")

        # Save translated explanation
        translated_path = f"{run_dir}/{pdf_stem}_explanation_{language}.json"
        with open(translated_path, 'w', encoding='utf-8') as f:
            json.dump(translated_explanation, f, indent=2, ensure_ascii=False)
        print(f"  Saved translated explanation: {translated_path}")

    # Step 2: Generate audio FIRST if requested (needed for beat-sync code generation)
    audio_timeline_path = None
    if generate_audio or render_video:
        audio_dir = f"{run_dir}/audio_beats"
        audio_timeline_path = f"{audio_dir}/beat_timeline.json"

        if os.path.exists(audio_timeline_path):
            print(f"\n{'='*70}")
            print("AUDIO ALREADY EXISTS - SKIPPING GENERATION")
            print(f"{'='*70}")
            print(f"Using existing: {audio_timeline_path}")
        else:
            print(f"\n{'='*70}")
            print("GENERATING TTS AUDIO")
            print(f"{'='*70}")

            from research_viz.audio_generator.beat_sync_tts import generate_beat_timeline

            # Use translated explanation path if available
            timeline_explanation_path = used_explanation_path
            if language != "en":
                translated_path = f"{run_dir}/{pdf_stem}_explanation_{language}.json"
                if os.path.exists(translated_path):
                    timeline_explanation_path = translated_path

            generate_beat_timeline(
                explanation_path=timeline_explanation_path,
                output_dir=audio_dir,
                voice=tts_voice,
                min_words=difficulty_config.beat_min_words,
                max_words=difficulty_config.beat_max_words,
                language=language
            )

            print(f"\n✓ Audio generation complete!")
            print(f"  Timeline: {audio_timeline_path}")

    # Step 3: Generate Manim code (skip if already exists)
    # Now with beat timing information if audio was generated
    code_output_path = f"{run_dir}/{pdf_stem}_animation.py"
    scene_metadata_path = f"{run_dir}/{pdf_stem}_scene_metadata.json"

    if os.path.exists(code_output_path) and os.path.exists(scene_metadata_path):
        print(f"\n{'='*70}")
        print("MANIM CODE ALREADY EXISTS - SKIPPING GENERATION")
        print(f"{'='*70}")
        print(f"Using existing: {code_output_path}")

        # Load scene metadata
        with open(scene_metadata_path, 'r') as f:
            scene_data = json.load(f)
        scene_codes = [ManimSceneCode(**scene) for scene in scene_data]
    else:
        print(f"\n{'='*70}")
        print("GENERATING MANIM CODE")
        print(f"{'='*70}")
        scene_codes = generate_all_scenes(
            explanation=explanation,
            model_name=model_name,
            max_retries=max_retries,
            audio_timeline_path=audio_timeline_path  # Pass beat timing!
        )

        if not scene_codes:
            print("No scenes generated successfully")
            return

        # Translate Manim Text() strings if non-English
        if language != "en":
            print(f"\n{'='*70}")
            print(f"TRANSLATING MANIM TEXT TO {lang_config.name.upper()}")
            print(f"{'='*70}")
            from research_viz.translation.manim_text_processor import ManimTextProcessor
            if translator is None:
                from research_viz.translation.translator import NarrationTranslator
                translator = NarrationTranslator()
            processor = ManimTextProcessor()
            for sc in scene_codes:
                texts = processor.extract_text_strings(sc.code)
                if texts:
                    translations = translator.translate_display_texts(texts, lang_config)
                    sc.code = processor.translate_code_texts(sc.code, translations, lang_config)
                    print(f"  Translated {len(texts)} text strings in {sc.scene_id}")

        # Save assembled code
        paper_title = explanation.get('paper_title', pdf_stem)
        complete_code = assemble_complete_code(scene_codes, paper_title)
        with open(code_output_path, 'w') as f:
            f.write(complete_code)

        # Save scene metadata for future reuse
        with open(scene_metadata_path, 'w') as f:
            json.dump([scene.model_dump() for scene in scene_codes], f, indent=2)

        print(f"\n{'='*70}")
        print(f"CODE GENERATION COMPLETE")
        print(f"{'='*70}")
        print(f"Generated {len(scene_codes)} scenes")
        print(f"Output: {code_output_path}")

    # Step 4: Render video if requested
    if render_video:
        if not audio_timeline_path:
            print("\nERROR: Cannot render video without audio. Enable --generate-audio")
            return

        final_video = render_and_sync_all_scenes(
            scene_codes=scene_codes,
            explanation=explanation,
            audio_timeline_path=audio_timeline_path,
            output_dir=run_dir,
            quality=video_quality,
            sync_mode=sync_mode,
            max_speed_change=max_speed_change
        )

        if final_video:
            print(f"\n✓ Pipeline complete!")
            print(f"  Final video: {final_video}")
        else:
            print(f"\n✗ Video rendering failed")


if __name__ == "__main__":
    tyro.cli(main)
