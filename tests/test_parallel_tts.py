"""Tests for parallel TTS beat generation in beat_sync_tts.py."""

from research_viz.audio_generator.beat_sync_tts import (
    _BeatJob,
    split_into_beats,
    NarrationBeat,
    MAX_TTS_WORKERS,
)


def test_beat_job_dataclass():
    """_BeatJob should store segment_id, beat_id, text, audio_file."""
    job = _BeatJob(
        segment_id="seg_01",
        beat_id=1,
        text="Hello world.",
        audio_file="/tmp/seg_01_beat_1.wav"
    )
    assert job.segment_id == "seg_01"
    assert job.beat_id == 1
    assert job.text == "Hello world."


def test_max_tts_workers_default():
    """Default parallel workers should be a reasonable number."""
    assert MAX_TTS_WORKERS >= 1
    assert MAX_TTS_WORKERS <= 20


def test_split_into_beats_unchanged():
    """Core beat splitting logic should be unaffected by refactoring."""
    text = "First sentence. Second sentence. Third sentence."
    beats = split_into_beats(text, min_words=2, max_words=5, language="en")
    assert len(beats) > 0
    # All original content should be present
    combined = " ".join(beats)
    assert "First sentence" in combined
    assert "Third sentence" in combined


def test_narration_beat_start_time_default():
    """NarrationBeat should default start_time to 0.0."""
    beat = NarrationBeat(beat_id=1, text="test")
    assert beat.start_time == 0.0
    assert beat.duration is None
    assert beat.audio_file is None
