"""
Audio Generation Module

Beat-synchronized TTS generation for Manim animations using OpenAI TTS API.

Features:
- Splits narration into beats (sentences/phrases)
- Generates TTS audio per beat using OpenAI
- Tracks exact duration for video syncing
- Integrates with pdf_to_manim_pipeline for full video generation

Quick Start:
    from research_viz.audio_generator import generate_beat_timeline, OPENAI_VOICES

    timeline = generate_beat_timeline(
        explanation_path="output/explanation.json",
        output_dir="output/audio_beats",
        voice="nova"
    )
"""

from .beat_sync_tts import (
    BeatSyncTTS,
    NarrationBeat,
    split_into_beats,
    generate_beat_timeline,
    OPENAI_VOICES
)

__all__ = [
    'BeatSyncTTS',
    'NarrationBeat',
    'split_into_beats',
    'generate_beat_timeline',
    'OPENAI_VOICES',
]
