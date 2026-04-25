"""Tests for config profile support (US-003)."""

import os
from pathlib import Path

import pytest
import yaml

from research_viz.config.pipeline_config import (
    PipelineConfig,
    get_config,
    reset_config,
)


@pytest.fixture(autouse=True)
def clean_config():
    reset_config()
    saved = {}
    for k in list(os.environ):
        if k.startswith("ANVAYA_"):
            saved[k] = os.environ.pop(k)
    yield
    reset_config()
    for k in list(os.environ):
        if k.startswith("ANVAYA_"):
            del os.environ[k]
    os.environ.update(saved)


def _setup_config_with_profile(tmp_path, base_yaml, profile_name, profile_yaml):
    """Helper to create base config.yaml and a profile YAML."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(base_yaml))

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    profile_file = config_dir / f"{profile_name}.yaml"
    profile_file.write_text(yaml.dump(profile_yaml))

    os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
    os.environ["ANVAYA_PROFILE"] = profile_name


class TestProfileLoading:
    def test_dev_profile_is_default(self, tmp_path):
        base = {"llm": {"explanation_model": "base/model"}}
        dev = {"llm": {"explanation_model": "dev/cheap-model"}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(base))
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "dev.yaml").write_text(yaml.dump(dev))
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
        # No ANVAYA_PROFILE set — should default to dev
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "dev/cheap-model"

    def test_prod_profile_overrides_base(self, tmp_path):
        base = {"llm": {"explanation_model": "base/model"}, "manim": {"timeout": 60}}
        prod = {"llm": {"explanation_model": "prod/quality-model"}}
        _setup_config_with_profile(tmp_path, base, "prod", prod)
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "prod/quality-model"
        assert cfg.manim.timeout == 60  # base value preserved

    def test_staging_profile(self, tmp_path):
        base = {"audio": {"max_workers": 2}}
        staging = {"audio": {"max_workers": 8}}
        _setup_config_with_profile(tmp_path, base, "staging", staging)
        cfg = PipelineConfig()
        assert cfg.audio.max_workers == 8

    def test_env_var_overrides_profile(self, tmp_path):
        base = {"llm": {"explanation_model": "base/model"}}
        prod = {"llm": {"explanation_model": "prod/model"}}
        _setup_config_with_profile(tmp_path, base, "prod", prod)
        os.environ["ANVAYA_LLM__EXPLANATION_MODEL"] = "env/override"
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "env/override"

    def test_missing_profile_falls_back_to_base(self, tmp_path):
        base = {"llm": {"explanation_model": "base/model"}}
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(base))
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_file)
        os.environ["ANVAYA_PROFILE"] = "nonexistent"
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "base/model"

    def test_profile_partial_override(self, tmp_path):
        base = {
            "llm": {"explanation_model": "base/explain", "judge_model": "base/judge"},
            "audio": {"max_workers": 4},
        }
        dev = {"llm": {"explanation_model": "dev/cheap"}}
        _setup_config_with_profile(tmp_path, base, "dev", dev)
        cfg = PipelineConfig()
        assert cfg.llm.explanation_model == "dev/cheap"
        assert cfg.llm.judge_model == "base/judge"
        assert cfg.audio.max_workers == 4

    def test_get_config_uses_profile(self, tmp_path):
        base = {"llm": {"explanation_model": "base/model"}}
        prod = {"llm": {"explanation_model": "prod/model"}}
        _setup_config_with_profile(tmp_path, base, "prod", prod)
        cfg = get_config()
        assert cfg.llm.explanation_model == "prod/model"
