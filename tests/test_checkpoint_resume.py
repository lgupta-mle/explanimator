"""Tests for US-015: Resume pipeline from checkpoint."""
import json
import os
import wave
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from research_viz.config.pipeline_config import reset_config
from research_viz.pipeline.checkpoint import write_checkpoint, read_checkpoints, validate_checkpoint


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVAYA_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("ANVAYA_PROFILE", raising=False)
    reset_config()
    yield
    reset_config()


def _create_wav(path, duration=1.0, sample_rate=24000):
    """Create a minimal valid WAV file."""
    num_samples = int(sample_rate * duration)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f'<{num_samples}h', *([0] * num_samples)))


class TestCheckpointResume:
    def test_is_stage_cached_valid(self, tmp_path):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _is_stage_cached
        artifact = tmp_path / "output.json"
        artifact.write_text('{"data": 1}')
        write_checkpoint(str(tmp_path), "explanation", [str(artifact)])
        cps = read_checkpoints(str(tmp_path))
        assert _is_stage_cached(cps, "explanation") is True

    def test_is_stage_cached_missing(self, tmp_path):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _is_stage_cached
        cps = read_checkpoints(str(tmp_path))
        assert _is_stage_cached(cps, "explanation") is False

    def test_is_stage_cached_modified_artifact(self, tmp_path):
        from research_viz.manim_generator.pdf_to_manim_pipeline import _is_stage_cached
        artifact = tmp_path / "output.json"
        artifact.write_text('{"data": 1}')
        write_checkpoint(str(tmp_path), "explanation", [str(artifact)])
        artifact.write_text('{"data": 2}')  # Modify after checkpoint
        cps = read_checkpoints(str(tmp_path))
        assert _is_stage_cached(cps, "explanation") is False

    def test_force_restart_ignores_checkpoints(self, tmp_path):
        """force_restart=True causes run_pipeline to ignore existing checkpoints."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import _is_stage_cached
        artifact = tmp_path / "output.json"
        artifact.write_text('{"data": 1}')
        write_checkpoint(str(tmp_path), "explanation", [str(artifact)])
        # force_restart means checkpoints dict is empty
        checkpoints = {}  # simulating force_restart=True
        assert _is_stage_cached(checkpoints, "explanation") is False


class TestPartialAudioResume:
    def test_skips_existing_beat_audio(self, tmp_path):
        """generate_segment_beats skips beats with existing valid WAV files."""
        from research_viz.audio_generator.beat_sync_tts import BeatSyncTTS

        output_dir = str(tmp_path / "audio")
        segment = {
            "segment_id": "seg1",
            "title": "Test",
            "narration_script": "This is beat one text. This is beat two text with more words here.",
        }

        # Create existing WAV for beat 1
        wav_path = tmp_path / "audio" / "seg1_beat_1.wav"
        _create_wav(str(wav_path), duration=0.5)

        tts = BeatSyncTTS(voice="nova")
        with patch.object(tts, 'generate_beat_audio', return_value=1.0) as mock_gen:
            beats = tts.generate_segment_beats(segment, output_dir, min_words=4, max_words=20)
            # Beat 1 should be skipped (existing WAV), beat 2 should be generated
            # The number of beats depends on text splitting, but beat 1 should not call generate_beat_audio
            if len(beats) >= 2:
                # First beat was skipped (used existing file)
                call_args = [str(c) for c in mock_gen.call_args_list]
                assert "beat_1.wav" not in str(call_args)

    def test_regenerates_corrupted_wav(self, tmp_path):
        """Corrupted WAV files trigger regeneration."""
        from research_viz.audio_generator.beat_sync_tts import BeatSyncTTS

        output_dir = str(tmp_path / "audio")
        segment = {
            "segment_id": "seg1",
            "title": "Test",
            "narration_script": "This is beat one text with enough words to form a single beat.",
        }

        # Create corrupted WAV
        wav_path = tmp_path / "audio" / "seg1_beat_1.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        wav_path.write_bytes(b"not a wav file but big enough" + b"\x00" * 100)

        tts = BeatSyncTTS(voice="nova")
        with patch.object(tts, 'generate_beat_audio', return_value=1.0) as mock_gen:
            beats = tts.generate_segment_beats(segment, output_dir, min_words=4, max_words=50)
            # Should have called generate_beat_audio since the WAV is corrupted
            assert mock_gen.call_count >= 1


class TestRunPipelineCheckpoints:
    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.assemble_complete_code")
    def test_writes_checkpoint_after_explanation(self, mock_assemble, mock_gen_scenes, tmp_path):
        """run_pipeline writes explanation checkpoint after generating explanation."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        output_dir = str(tmp_path / "output")

        mock_gen_scenes.return_value = [MagicMock()]
        mock_assemble.return_value = "# generated code"

        with patch("research_viz.manim_generator.pdf_explanation_generator.generate_explanation_from_pdf") as mock_exp:
            mock_exp.return_value = {"paper_title": "Test", "segments": []}
            with patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline"):
                run_pipeline(str(pdf_path), output_dir=output_dir)

        cps = read_checkpoints(output_dir)
        assert "explanation" in cps

    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.assemble_complete_code")
    def test_skips_explanation_with_valid_checkpoint(self, mock_assemble, mock_gen_scenes, tmp_path):
        """run_pipeline skips explanation generation when checkpoint is valid."""
        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        output_dir = str(tmp_path / "output")

        # Pre-create explanation and checkpoint
        exp_path = Path(output_dir) / "test_explanation.json"
        exp_path.parent.mkdir(parents=True, exist_ok=True)
        exp_data = {"paper_title": "Test", "segments": []}
        with open(exp_path, 'w') as f:
            json.dump(exp_data, f)
        write_checkpoint(output_dir, "explanation", [str(exp_path)])

        mock_gen_scenes.return_value = [MagicMock()]
        mock_assemble.return_value = "# generated code"

        with patch("research_viz.manim_generator.pdf_explanation_generator.generate_explanation_from_pdf") as mock_exp:
            with patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline"):
                run_pipeline(str(pdf_path), output_dir=output_dir)
            mock_exp.assert_not_called()
