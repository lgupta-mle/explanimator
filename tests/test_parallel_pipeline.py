"""Tests for US-008: Parallel TTS and code generation in run_pipeline."""

import os
import json
import tempfile
import threading
import time
from unittest.mock import patch, MagicMock
from concurrent.futures import Future

import pytest

from research_viz.config.pipeline_config import reset_config


@pytest.fixture(autouse=True)
def clean_config():
    """Reset singleton and env vars between tests."""
    reset_config()
    env_keys = [k for k in os.environ if k.startswith("ANVAYA_")]
    for k in env_keys:
        del os.environ[k]
    yield
    reset_config()
    for k in env_keys:
        os.environ.pop(k, None)


@pytest.fixture
def tmp_output(tmp_path):
    return str(tmp_path / "output")


@pytest.fixture
def sample_explanation():
    return {
        "paper_title": "Test Paper",
        "running_example": "An example",
        "segments": [
            {
                "segment_id": "seg_01",
                "title": "Intro",
                "narration_script": "This is a test narration for the first segment.",
                "intuition": {"core_insight": "test"},
                "technical": {},
            }
        ],
    }


@pytest.fixture
def explanation_file(tmp_path, sample_explanation):
    path = tmp_path / "explanation.json"
    path.write_text(json.dumps(sample_explanation))
    return str(path)


def _make_mock_scene():
    from research_viz.manim_generator.pdf_to_manim_pipeline import ManimSceneCode
    return ManimSceneCode(scene_id="seg_01", class_name="IntroScene", code="from manim import *\nclass IntroScene(Scene):\n    def construct(self): pass")


class TestParallelPipeline:
    """Test that TTS and code gen run concurrently."""

    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline")
    def test_both_stages_called(self, mock_tts, mock_code_gen, explanation_file, tmp_output, sample_explanation):
        """Both TTS and code gen are invoked."""
        mock_tts.return_value = {"seg_01": []}
        mock_code_gen.return_value = [_make_mock_scene()]

        cfg_path = os.path.join(os.path.dirname(explanation_file), "config.yaml")
        with open(cfg_path, "w") as f:
            f.write("{}")
        os.environ["ANVAYA_CONFIG_PATH"] = cfg_path

        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline
        result = run_pipeline(
            pdf_path="dummy.pdf",
            output_dir=tmp_output,
            skip_explanation=True,
            explanation_path=explanation_file,
        )

        assert result is not None
        mock_tts.assert_called_once()
        mock_code_gen.assert_called_once()

    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline")
    def test_parallel_execution_overlap(self, mock_tts, mock_code_gen, explanation_file, tmp_output):
        """Verify both stages run concurrently (wall-clock ~ max, not sum)."""
        tts_start = threading.Event()
        code_start = threading.Event()

        def slow_tts(*args, **kwargs):
            tts_start.set()
            code_start.wait(timeout=5)
            time.sleep(0.1)
            return {"seg_01": []}

        def slow_code_gen(*args, **kwargs):
            code_start.set()
            tts_start.wait(timeout=5)
            time.sleep(0.1)
            return [_make_mock_scene()]

        mock_tts.side_effect = slow_tts
        mock_code_gen.side_effect = slow_code_gen

        cfg_path = os.path.join(os.path.dirname(explanation_file), "config.yaml")
        with open(cfg_path, "w") as f:
            f.write("{}")
        os.environ["ANVAYA_CONFIG_PATH"] = cfg_path

        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline
        start = time.monotonic()
        result = run_pipeline(
            pdf_path="dummy.pdf",
            output_dir=tmp_output,
            skip_explanation=True,
            explanation_path=explanation_file,
        )
        elapsed = time.monotonic() - start

        assert result is not None
        # Both should have started (events were set by each thread)
        assert tts_start.is_set()
        assert code_start.is_set()
        # Wall-clock should be closer to max(0.1, 0.1) than sum(0.1, 0.1)
        # Allow generous margin but confirm overlap happened
        assert elapsed < 2.0

    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline")
    def test_tts_failure_propagates(self, mock_tts, mock_code_gen, explanation_file, tmp_output):
        """If TTS fails, pipeline returns None."""
        mock_tts.side_effect = RuntimeError("TTS service unavailable")
        mock_code_gen.return_value = [_make_mock_scene()]

        cfg_path = os.path.join(os.path.dirname(explanation_file), "config.yaml")
        with open(cfg_path, "w") as f:
            f.write("{}")
        os.environ["ANVAYA_CONFIG_PATH"] = cfg_path

        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline
        result = run_pipeline(
            pdf_path="dummy.pdf",
            output_dir=tmp_output,
            skip_explanation=True,
            explanation_path=explanation_file,
        )
        assert result is None

    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline")
    def test_code_gen_failure_propagates(self, mock_tts, mock_code_gen, explanation_file, tmp_output):
        """If code gen fails, pipeline returns None."""
        mock_tts.return_value = {"seg_01": []}
        mock_code_gen.side_effect = RuntimeError("LLM error")

        cfg_path = os.path.join(os.path.dirname(explanation_file), "config.yaml")
        with open(cfg_path, "w") as f:
            f.write("{}")
        os.environ["ANVAYA_CONFIG_PATH"] = cfg_path

        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline
        result = run_pipeline(
            pdf_path="dummy.pdf",
            output_dir=tmp_output,
            skip_explanation=True,
            explanation_path=explanation_file,
        )
        assert result is None

    @patch("research_viz.manim_generator.pdf_to_manim_pipeline.generate_all_scenes")
    @patch("research_viz.audio_generator.beat_sync_tts.generate_beat_timeline")
    def test_empty_code_gen_returns_none(self, mock_tts, mock_code_gen, explanation_file, tmp_output):
        """If code gen returns empty list, pipeline returns None."""
        mock_tts.return_value = {"seg_01": []}
        mock_code_gen.return_value = []

        cfg_path = os.path.join(os.path.dirname(explanation_file), "config.yaml")
        with open(cfg_path, "w") as f:
            f.write("{}")
        os.environ["ANVAYA_CONFIG_PATH"] = cfg_path

        from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline
        result = run_pipeline(
            pdf_path="dummy.pdf",
            output_dir=tmp_output,
            skip_explanation=True,
            explanation_path=explanation_file,
        )
        assert result is None
