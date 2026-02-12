"""
Audio Generation Module

Beat-synchronized TTS generation for Manim animations.

Level 2 Synchronization:
- Splits narration into beats (sentences/phrases)
- Generates TTS audio per beat
- Allocates animation durations to match audio
- Generates beat-synced Manim code

Quick Start:
    from research_viz.audio_generator import run_complete_workflow
    
    run_complete_workflow(
        explanation_path="output/explanation.json",
        voice="dan"
    )
"""

from .beat_sync_tts import (
    BeatSyncTTS,
    NarrationBeat,
    split_into_beats,
    generate_beat_timeline,
    OPENAI_VOICES
)

from .beat_duration_allocator import (
    BeatAllocation,
    AnimationAllocation,
    allocate_beat_duration,
    build_beat_allocations,
    ANIMATION_WEIGHTS
)

from .beat_synced_manim_generator import (
    generate_beat_synced_scene,
    generate_all_beat_synced_scenes
)

from .workflow import run_complete_workflow

__all__ = [
    # TTS Generation
    'BeatSyncTTS',
    'NarrationBeat',
    'split_into_beats',
    'generate_beat_timeline',
    'OPENAI_VOICES',
    
    # Duration Allocation
    'BeatAllocation',
    'AnimationAllocation',
    'allocate_beat_duration',
    'build_beat_allocations',
    'ANIMATION_WEIGHTS',
    
    # Manim Code Generation
    'generate_beat_synced_scene',
    'generate_all_beat_synced_scenes',
    
    # Complete Workflow
    'run_complete_workflow'
]
