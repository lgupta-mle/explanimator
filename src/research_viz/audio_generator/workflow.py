"""
Beat-Sync Audio + Manim Workflow

Complete workflow: Explanation → Beats → TTS → Allocations → Synced Manim Code
"""

import json
from pathlib import Path
from typing import Optional
import argparse

from .beat_sync_tts import generate_beat_timeline, OPENAI_VOICES
from .beat_duration_allocator import build_beat_allocations, save_allocations
from .beat_synced_manim_generator import generate_all_beat_synced_scenes


def run_complete_workflow(
    explanation_path: str,
    output_base_dir: str = "src/research_viz/manim_generator/output",
    voice: str = "nova",
    min_words: int = 8,
    max_words: int = 25
):
    """
    Run complete beat-sync workflow.
    
    Workflow:
        1. Split narration into beats
        2. Generate TTS audio per beat
        3. Build duration allocations
        4. Generate beat-synced Manim code
    
    Args:
        explanation_path: Path to educational explanation JSON
        output_base_dir: Base output directory
        voice: TTS voice
        min_words: Min words per beat
        max_words: Max words per beat
    """
    output_base = Path(output_base_dir)
    output_base.mkdir(parents=True, exist_ok=True)
    
    audio_dir = output_base / "audio_beats"
    scenes_dir = output_base / "beat_synced_scenes"
    
    print("="*70)
    print("BEAT-SYNC WORKFLOW")
    print("="*70)
    print(f"Input: {explanation_path}")
    print(f"Output: {output_base}")
    print(f"Voice: {voice}")
    print(f"Beat length: {min_words}-{max_words} words")
    print("="*70)
    
    # Step 1: Generate beat timeline with TTS
    print("\n" + "="*70)
    print("STEP 1: Generate Beat Timeline & TTS Audio")
    print("="*70)
    
    timeline = generate_beat_timeline(
        explanation_path=explanation_path,
        output_dir=str(audio_dir),
        voice=voice,
        min_words=min_words,
        max_words=max_words
    )
    
    timeline_path = audio_dir / "beat_timeline.json"
    
    # Step 2: Build duration allocations
    print("\n" + "="*70)
    print("STEP 2: Build Beat Duration Allocations")
    print("="*70)
    
    allocations = build_beat_allocations(str(timeline_path))
    allocations_path = audio_dir / "beat_allocations.json"
    save_allocations(allocations, str(allocations_path))
    
    # Step 3: Generate beat-synced Manim scenes
    print("\n" + "="*70)
    print("STEP 3: Generate Beat-Synced Manim Code")
    print("="*70)
    
    scene_files = generate_all_beat_synced_scenes(
        explanation_path=explanation_path,
        beat_timeline_path=str(timeline_path),
        output_dir=str(scenes_dir)
    )
    
    # Final summary
    print("\n" + "="*70)
    print("WORKFLOW COMPLETE!")
    print("="*70)
    
    total_beats = sum(len(beats) for beats in timeline.values())
    total_duration = sum(
        sum(b.duration for b in beats)
        for beats in timeline.values()
    )
    
    print(f"\nGenerated:")
    print(f"  ✓ {total_beats} audio beats ({total_duration:.1f}s total)")
    print(f"  ✓ {len(scene_files)} Manim scenes")
    
    print(f"\nOutput locations:")
    print(f"  Audio: {audio_dir}")
    print(f"  Timeline: {timeline_path}")
    print(f"  Allocations: {allocations_path}")
    print(f"  Scenes: {scenes_dir}")
    
    print(f"\nNext steps:")
    print(f"  1. Review generated scenes in: {scenes_dir}")
    print(f"  2. Render a scene:")
    print(f"     manim -pqh {scenes_dir}/<scene_file>.py <ClassName>")
    print(f"  3. The audio will play automatically during rendering!")
    
    print("\n" + "="*70)
    
    return {
        'timeline_path': str(timeline_path),
        'allocations_path': str(allocations_path),
        'scene_files': scene_files,
        'audio_dir': str(audio_dir),
        'scenes_dir': str(scenes_dir)
    }


def main():
    """CLI for complete workflow."""
    parser = argparse.ArgumentParser(
        description="Run complete beat-sync audio + Manim workflow"
    )
    parser.add_argument(
        "--explanation-path",
        required=True,
        help="Path to educational explanation JSON"
    )
    parser.add_argument(
        "--output-dir",
        default="src/research_viz/manim_generator/output",
        help="Base output directory"
    )
    parser.add_argument(
        "--voice",
        default="nova",
        choices=OPENAI_VOICES,
        help="TTS voice"
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=8,
        help="Minimum words per beat"
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=25,
        help="Maximum words per beat"
    )
    
    args = parser.parse_args()
    
    run_complete_workflow(
        explanation_path=args.explanation_path,
        output_base_dir=args.output_dir,
        voice=args.voice,
        min_words=args.min_words,
        max_words=args.max_words
    )


if __name__ == "__main__":
    main()
