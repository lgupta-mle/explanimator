"""Tests for PipelineConfig."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from research_viz.config.pipeline_config import (
    PipelineConfig,
    LLMConfig,
    AudioConfig,
    VideoConfig,
    ManimConfig,
    TranslationConfig,
    get_config,
    reset_config,
)


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


class TestDefaults:
    def test_default_llm_config(self):
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "openai/gpt-5"
        assert cfg.llm.code_gen_model == "anthropic/claude-sonnet-4.5"

    def test_default_audio_config(self):
        cfg = PipelineConfig()
        assert cfg.audio.tts_model == "tts-1"
        assert cfg.audio.voice == "nova"
        assert cfg.audio.max_workers == 4

    def test_default_video_config(self):
        cfg = PipelineConfig()
        assert cfg.video.quality == "l"
        assert cfg.video.sync_mode == "segment"
        assert cfg.video.max_speed_change == 0.3

    def test_default_manim_config(self):
        cfg = PipelineConfig()
        assert cfg.manim.timeout == 120
        assert cfg.manim.max_retries == 3

    def test_default_translation_config(self):
        cfg = PipelineConfig()
        assert cfg.translation.max_workers == 10


class TestYamlLoading:
    def test_loads_from_yaml(self, tmp_path):
        yaml_data = {
            "llm": {"explanation_model": "test/model-yaml"},
            "audio": {"voice": "echo", "max_workers": 8},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(yaml_data))

        os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "test/model-yaml"
        assert cfg.audio.voice == "echo"
        assert cfg.audio.max_workers == 8
        # Unset values keep defaults
        assert cfg.llm.code_gen_model == "anthropic/claude-sonnet-4.5"

    def test_empty_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "openai/gpt-5"

    def test_missing_yaml_uses_defaults(self):
        os.environ["ANVAYA_CONFIG_PATH"] = "/nonexistent/config.yaml"
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "openai/gpt-5"


class TestEnvOverrides:
    def test_env_overrides_nested(self, tmp_path):
        yaml_data = {"llm": {"explanation_model": "yaml/model"}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(yaml_data))
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)

        os.environ["ANVAYA_LLM__EXPLANATION_MODEL"] = "env/override-model"
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "env/override-model"

    def test_env_overrides_audio(self):
        os.environ["ANVAYA_AUDIO__MAX_WORKERS"] = "16"
        cfg = PipelineConfig()
        assert cfg.audio.max_workers == 16


class TestValidation:
    def test_invalid_type_raises(self, tmp_path):
        yaml_data = {"manim": {"timeout": "not_a_number"}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(yaml_data))
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
        with pytest.raises(Exception):
            PipelineConfig()


class TestSingleton:
    def test_get_config_returns_same_instance(self):
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reset_clears_singleton(self):
        c1 = get_config()
        reset_config()
        c2 = get_config()
        assert c1 is not c2
