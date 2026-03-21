"""Tests for config migration: verify modules read from PipelineConfig instead of hardcoded values."""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
import yaml

from research_viz.config.pipeline_config import get_config, reset_config


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
def custom_config(tmp_path):
    """Create a config with non-default values to verify config reads."""
    yaml_data = {
        "llm": {
            "explanation_model": "test/explanation-model",
            "judge_model": "test/judge-model",
            "prereq_model": "test/prereq-model",
            "code_gen_model": "test/codegen-model",
            "default_model": "test/default-model",
        },
        "audio": {
            "tts_model": "tts-test",
            "voice": "echo",
            "max_workers": 2,
            "sample_rate": 16000,
            "min_words_per_beat": 5,
            "max_words_per_beat": 15,
        },
        "video": {
            "quality": "m",
            "sync_mode": "beat",
            "max_speed_change": 0.5,
        },
        "manim": {
            "timeout": 60,
            "max_workers": 2,
            "max_retries": 5,
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(yaml_data))
    os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
    reset_config()
    return get_config()


class TestPdfExplanationGeneratorConfig:
    def test_call_llm_provider_uses_config_default(self, custom_config):
        from research_viz.manim_generator.pdf_explanation_generator import call_llm_provider
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(content="ok", model="m")
        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            call_llm_provider([{"role": "user", "content": "test"}])
            model_arg = mock_provider.generate.call_args[0][1]
            assert model_arg == "test/default-model"

    def test_call_llm_provider_explicit_model_overrides(self, custom_config):
        from research_viz.manim_generator.pdf_explanation_generator import call_llm_provider
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(content="ok", model="m")
        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            call_llm_provider([{"role": "user", "content": "test"}], model_name="explicit/model")
            model_arg = mock_provider.generate.call_args[0][1]
            assert model_arg == "explicit/model"

    def test_judge_explanation_uses_judge_model(self, custom_config):
        from research_viz.manim_generator.pdf_explanation_generator import judge_explanation
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(
            content='{"score": 1, "criteria_scores": {}, "feedback": null}', model="m"
        )
        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            judge_explanation('{"test": true}')
            model_arg = mock_provider.generate.call_args[0][1]
            assert model_arg == "test/judge-model"

    def test_generate_with_feedback_loop_uses_explanation_model(self, custom_config):
        from research_viz.manim_generator.pdf_explanation_generator import generate_with_feedback_loop
        from research_viz.providers.llm_provider import LLMResponse

        with patch("research_viz.manim_generator.pdf_explanation_generator.create_pdf_llm_response") as mock_create:
            mock_create.return_value = LLMResponse(content='{"paper_title": "test"}', model="m")
            with patch("research_viz.manim_generator.pdf_explanation_generator.judge_explanation") as mock_judge:
                from research_viz.manim_generator.pdf_explanation_generator import JudgeResult
                mock_judge.return_value = JudgeResult(score=1)
                generate_with_feedback_loop("/fake/path.pdf")
                assert mock_create.call_args[1]["model_name"] == "test/explanation-model"


class TestPdfToManimPipelineConfig:
    def test_execute_manim_scene_uses_config_timeout(self, custom_config):
        from research_viz.manim_generator.pdf_to_manim_pipeline import execute_manim_scene

        with patch("research_viz.manim_generator.pdf_to_manim_pipeline.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok")
            execute_manim_scene("from manim import *\nclass T(Scene): pass", "T")
            assert mock_run.call_args[1]["timeout"] == 60

    def test_generate_scene_code_uses_config_model(self, custom_config):
        from research_viz.manim_generator.pdf_to_manim_pipeline import generate_scene_code
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(content="", model="m")
        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            generate_scene_code(
                segment={"segment_id": "s1", "title": "T"},
                running_example="example",
            )
            model_arg = mock_provider.generate.call_args[0][1]
            assert model_arg == "test/codegen-model"

    def test_generate_scene_code_uses_config_retries(self, custom_config):
        from research_viz.manim_generator.pdf_to_manim_pipeline import generate_scene_code
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(content="", model="m")
        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            generate_scene_code(
                segment={"segment_id": "s1", "title": "T"},
                running_example="example",
            )
            assert mock_provider.generate.call_count == 5  # max_retries from config


class TestBeatSyncTTSConfig:
    def test_beat_sync_tts_uses_config_voice(self, custom_config):
        from research_viz.audio_generator.beat_sync_tts import BeatSyncTTS

        tts = BeatSyncTTS()
        assert tts.voice == "echo"
        assert tts.tts_model == "tts-test"
        assert tts.sample_rate == 16000

    def test_beat_sync_tts_explicit_override(self, custom_config):
        from research_viz.audio_generator.beat_sync_tts import BeatSyncTTS

        tts = BeatSyncTTS(voice="nova", sample_rate=44100)
        assert tts.voice == "nova"
        assert tts.sample_rate == 44100


class TestLLMUtilsConfig:
    def test_create_llm_response_uses_config_default(self, custom_config):
        from research_viz.utils.llm_utils import create_llm_response
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(content="test", model="m")
        with patch("research_viz.utils.llm_utils.get_provider", return_value=mock_provider):
            create_llm_response("prompt", "system")
            model_arg = mock_provider.generate.call_args[0][1]
            assert model_arg == "test/default-model"

    def test_create_llm_response_explicit_override(self, custom_config):
        from research_viz.utils.llm_utils import create_llm_response
        from research_viz.providers.llm_provider import LLMResponse

        mock_provider = MagicMock()
        mock_provider.generate.return_value = LLMResponse(content="test", model="m")
        with patch("research_viz.utils.llm_utils.get_provider", return_value=mock_provider):
            create_llm_response("prompt", "system", model_name="override/model")
            model_arg = mock_provider.generate.call_args[0][1]
            assert model_arg == "override/model"
