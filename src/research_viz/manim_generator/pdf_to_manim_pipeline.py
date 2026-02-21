"""
PDF to Manim Pipeline

Complete pipeline: PDF → 3B1B Explanation → Manim Code with execution feedback.
Uses RAG only when execution errors occur.
"""

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
    call_openrouter,
    load_prompt,
    encode_pdf_to_base64
)
from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B, Segment3B1B

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
    chroma_path: str = "data/manim_docs/vector_db/chroma_db"
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
    chroma_path: str = "data/manim_docs/vector_db/chroma_db"
) -> List[ManimSceneCode]:
    """Generate Manim code for all segments in the explanation."""
    running_example = explanation.get('running_example', '')
    segments = explanation.get('segments', [])

    print(f"\nGenerating Manim code for {len(segments)} segments")
    print(f"Running example: {running_example[:100]}...")

    scene_codes = []
    for i, segment in enumerate(segments):
        print(f"\n[{i+1}/{len(segments)}] Segment: {segment.get('title', 'Untitled')}")
        scene_code = generate_scene_code(
            segment=segment,
            running_example=running_example,
            model_name=model_name,
            max_retries=max_retries,
            chroma_path=chroma_path
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
    quality: str = "l"
) -> Optional[str]:
    """
    Render all Manim scenes, sync with audio, and stitch together.

    Args:
        scene_codes: List of generated scene codes
        explanation: Explanation dict with segments
        audio_timeline_path: Path to beat timeline JSON
        output_dir: Output directory
        quality: Manim quality (-ql, -qm, -qh)

    Returns:
        Path to final stitched video, or None on failure
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

        # Sync audio with video
        print(f"  Syncing audio with video...")
        if sync_audio_with_video(video_pattern, segment_audio_path, synced_video_path):
            print(f"  SUCCESS: {synced_video_path}")
            synced_videos.append(synced_video_path)
        else:
            print(f"  WARNING: Sync failed, using video without audio")
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
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
    generate_audio: bool = False,
    tts_voice: str = "nova",
    render_video: bool = False,
    video_quality: str = "l"
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

    Examples:
        # Generate code only
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --explanation-path output/attention_explanation.json

        # Generate code + audio + video
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --explanation-path output/attention_explanation.json \\
            --generate-audio --render-video
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Step 1: Load or generate explanation
    if explanation_path and os.path.exists(explanation_path):
        print(f"Loading existing explanation: {explanation_path}")
        with open(explanation_path, 'r') as f:
            explanation = json.load(f)
        used_explanation_path = explanation_path
        pdf_stem = Path(explanation_path).stem.replace('_explanation', '')
    elif pdf_path and os.path.exists(pdf_path):
        print(f"Generating explanation from PDF: {pdf_path}")
        from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
        pdf_stem = Path(pdf_path).stem
        explanation_output = f"{output_dir}/{pdf_stem}_explanation.json"
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_output,
            model_name=model_name,
            max_judge_attempts=3
        )
        if not explanation:
            print("Failed to generate explanation")
            return
        used_explanation_path = explanation_output
    else:
        print("ERROR: Provide either --pdf-path or --explanation-path")
        print("  --pdf-path: Path to research paper PDF")
        print("  --explanation-path: Path to existing explanation JSON")
        return

    # Step 2: Generate Manim code (skip if already exists)
    code_output_path = f"{output_dir}/{pdf_stem}_animation.py"
    scene_metadata_path = f"{output_dir}/{pdf_stem}_scene_metadata.json"

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
            max_retries=max_retries
        )

        if not scene_codes:
            print("No scenes generated successfully")
            return

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

    # Step 3: Generate audio if requested (skip if already exists)
    audio_timeline_path = None
    if generate_audio or render_video:
        audio_dir = f"{output_dir}/audio_beats"
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

            generate_beat_timeline(
                explanation_path=used_explanation_path,
                output_dir=audio_dir,
                voice=tts_voice
            )

            print(f"\n✓ Audio generation complete!")
            print(f"  Timeline: {audio_timeline_path}")

    # Step 4: Render video if requested
    if render_video:
        if not audio_timeline_path:
            print("\nERROR: Cannot render video without audio. Enable --generate-audio")
            return

        final_video = render_and_sync_all_scenes(
            scene_codes=scene_codes,
            explanation=explanation,
            audio_timeline_path=audio_timeline_path,
            output_dir=output_dir,
            quality=video_quality
        )

        if final_video:
            print(f"\n✓ Pipeline complete!")
            print(f"  Final video: {final_video}")
        else:
            print(f"\n✗ Video rendering failed")


if __name__ == "__main__":
    tyro.cli(main)
