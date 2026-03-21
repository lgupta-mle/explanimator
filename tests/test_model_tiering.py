"""Tests for US-012: Model tiering config per difficulty."""
import os
import pytest
import yaml

from research_viz.config.pipeline_config import (
    LLMConfig,
    PipelineConfig,
    TierConfig,
    reset_config,
)


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVAYA_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("ANVAYA_PROFILE", raising=False)
    reset_config()
    yield
    reset_config()


class TestTierConfig:
    def test_tier_defaults_all_none(self):
        tier = TierConfig()
        assert tier.explanation_model is None
        assert tier.judge_model is None
        assert tier.skip_judge is False

    def test_tier_partial_override(self):
        tier = TierConfig(explanation_model="fast/model")
        assert tier.explanation_model == "fast/model"
        assert tier.judge_model is None


class TestLLMConfigGetModel:
    def test_no_difficulty_returns_base(self):
        cfg = LLMConfig()
        assert cfg.get_model("explanation_model") == "openai/gpt-5"

    def test_unknown_difficulty_returns_base(self):
        cfg = LLMConfig()
        assert cfg.get_model("explanation_model", "unknown") == "openai/gpt-5"

    def test_tier_override_returns_tier_model(self):
        cfg = LLMConfig(tiers={"hard": TierConfig(explanation_model="fast/model")})
        assert cfg.get_model("explanation_model", "hard") == "fast/model"

    def test_tier_without_stage_falls_back_to_base(self):
        cfg = LLMConfig(tiers={"hard": TierConfig(explanation_model="fast/model")})
        assert cfg.get_model("judge_model", "hard") == "openai/gpt-5"

    def test_multiple_tiers(self):
        cfg = LLMConfig(tiers={
            "hard": TierConfig(explanation_model="fast/model"),
            "medium": TierConfig(explanation_model="mid/model"),
        })
        assert cfg.get_model("explanation_model", "hard") == "fast/model"
        assert cfg.get_model("explanation_model", "medium") == "mid/model"
        assert cfg.get_model("explanation_model") == "openai/gpt-5"

    def test_unknown_stage_returns_default_model(self):
        cfg = LLMConfig()
        assert cfg.get_model("nonexistent_stage") == "openai/gpt-5"


class TestGetTier:
    def test_returns_none_no_difficulty(self):
        cfg = LLMConfig()
        assert cfg.get_tier() is None

    def test_returns_none_unknown_difficulty(self):
        cfg = LLMConfig(tiers={"hard": TierConfig()})
        assert cfg.get_tier("easy") is None

    def test_returns_tier_config(self):
        tier = TierConfig(skip_judge=True)
        cfg = LLMConfig(tiers={"hard": tier})
        assert cfg.get_tier("hard") is tier


class TestTiersFromYaml:
    def test_tiers_loaded_from_yaml(self, tmp_path):
        yaml_data = {
            "llm": {
                "tiers": {
                    "hard": {
                        "explanation_model": "fast/model",
                        "skip_judge": True,
                    },
                    "medium": {
                        "explanation_model": "mid/model",
                    },
                }
            }
        }
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(yaml_data, f)
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_path)
        reset_config()

        cfg = PipelineConfig()
        assert cfg.llm.get_model("explanation_model", "hard") == "fast/model"
        assert cfg.llm.get_tier("hard").skip_judge is True
        assert cfg.llm.get_model("explanation_model", "medium") == "mid/model"
        assert cfg.llm.get_model("explanation_model") == "openai/gpt-5"

    def test_no_tiers_in_yaml_defaults_empty(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"llm": {"explanation_model": "test/model"}}, f)
        os.environ["ANVAYA_CONFIG_PATH"] = str(config_path)
        reset_config()

        cfg = PipelineConfig()
        assert cfg.llm.tiers == {}
        assert cfg.llm.get_model("explanation_model") == "test/model"
