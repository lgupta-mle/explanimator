"""
Centralized pipeline configuration using Pydantic models.
Loads from config.yaml with ANVAYA_* env var overrides.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    explanation_model: str = "openai/gpt-5"
    judge_model: str = "openai/gpt-5"
    prereq_model: str = "openai/gpt-5"
    code_gen_model: str = "anthropic/claude-sonnet-4.5"
    default_model: str = "openai/gpt-5"
    provider: str = "openrouter"
    max_retries: int = 3
    retry_base_delay: float = 1.0


class AudioConfig(BaseModel):
    tts_model: str = "tts-1"
    voice: str = "nova"
    max_workers: int = 4
    sample_rate: int = 24000
    min_words_per_beat: int = 8
    max_words_per_beat: int = 25


class VideoConfig(BaseModel):
    quality: str = "l"
    sync_mode: str = "segment"
    max_speed_change: float = 0.3
    render_timeout: int = 300


class ManimConfig(BaseModel):
    timeout: int = 120
    max_workers: int = 4
    max_retries: int = 3


class TranslationConfig(BaseModel):
    model: str = "openai/gpt-5"
    max_workers: int = 10


class PipelineConfig(BaseSettings):
    """Central configuration for the Anvaya pipeline.

    Resolution order:
    1. ANVAYA_* environment variables (highest priority)
    2. config.yaml values
    3. Field defaults (lowest priority)
    """

    model_config = {
        "env_prefix": "ANVAYA_",
        "env_nested_delimiter": "__",
    }

    llm: LLMConfig = LLMConfig()
    audio: AudioConfig = AudioConfig()
    video: VideoConfig = VideoConfig()
    manim: ManimConfig = ManimConfig()
    translation: TranslationConfig = TranslationConfig()

    @model_validator(mode="before")
    @classmethod
    def load_yaml_defaults(cls, values):
        """Load config.yaml as defaults, overlay profile, then provided values.

        Resolution order (highest priority first):
        1. ANVAYA_* environment variables
        2. Profile-specific YAML (config/{profile}.yaml)
        3. Base config.yaml
        4. Field defaults
        """
        yaml_path = _find_config_yaml()
        base = {}
        if yaml_path and yaml_path.exists():
            with open(yaml_path) as f:
                base = yaml.safe_load(f) or {}

        profile_data = _load_profile_yaml(yaml_path)
        if profile_data:
            base = _deep_merge(base, profile_data)

        merged = _deep_merge(base, values)
        return merged


def _load_profile_yaml(base_yaml_path: Optional[Path]) -> Optional[dict]:
    """Load profile-specific YAML config based on ANVAYA_PROFILE env var."""
    profile = os.environ.get("ANVAYA_PROFILE", "dev")
    if not base_yaml_path:
        return None

    profile_dir = base_yaml_path.parent / "config"
    profile_path = profile_dir / f"{profile}.yaml"
    if profile_path.exists():
        with open(profile_path) as f:
            return yaml.safe_load(f) or {}
    return None


def _find_config_yaml() -> Optional[Path]:
    """Find config.yaml by checking env var, then project root."""
    explicit = os.environ.get("ANVAYA_CONFIG_PATH")
    if explicit:
        return Path(explicit)

    # Walk up from this file to find project root (where pyproject.toml lives)
    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "config.yaml"
        if candidate.exists():
            return candidate
        if (current / "pyproject.toml").exists():
            return current / "config.yaml"
        current = current.parent
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


_config: Optional[PipelineConfig] = None


def get_config() -> PipelineConfig:
    """Get or create the singleton PipelineConfig instance."""
    global _config
    if _config is None:
        _config = PipelineConfig()
    return _config


def reset_config() -> None:
    """Reset the singleton (for testing)."""
    global _config
    _config = None
    reset_provider()


def _create_provider():
    """Instantiate an LLMProvider from config."""
    from research_viz.providers.openrouter_provider import OpenRouterProvider

    cfg = get_config()
    provider_name = cfg.llm.provider
    if provider_name == "openrouter":
        return OpenRouterProvider(
            max_retries=cfg.llm.max_retries,
            retry_base_delay=cfg.llm.retry_base_delay,
        )
    raise ValueError(f"Unknown LLM provider: {provider_name}")


_provider = None


def get_provider():
    """Get or create the singleton LLMProvider instance."""
    global _provider
    if _provider is None:
        _provider = _create_provider()
    return _provider


def reset_provider() -> None:
    """Reset the provider singleton (for testing)."""
    global _provider
    _provider = None
