"""Tests for LLMProvider ABC, OpenRouterProvider, and provider wiring."""

import os
import json
import time
from unittest.mock import patch, MagicMock

import pytest

from research_viz.providers.llm_provider import LLMProvider, LLMResponse
from research_viz.providers.openrouter_provider import OpenRouterProvider
from research_viz.config.pipeline_config import (
    PipelineConfig,
    get_config,
    get_provider,
    reset_config,
    reset_provider,
)


@pytest.fixture(autouse=True)
def clean_state(tmp_path):
    """Reset singletons and env vars between tests."""
    reset_config()
    env_keys = [k for k in os.environ if k.startswith("ANVAYA_")]
    saved = {k: os.environ.pop(k) for k in env_keys}
    os.environ["ANVAYA_CONFIG_PATH"] = str(tmp_path / "config.yaml")
    yield
    reset_config()
    for k in list(os.environ):
        if k.startswith("ANVAYA_"):
            del os.environ[k]
    os.environ.update(saved)


# --- LLMResponse dataclass ---

class TestLLMResponse:
    def test_fields(self):
        r = LLMResponse(content="hello", model="m1", tokens_used=42, latency_ms=100.5)
        assert r.content == "hello"
        assert r.model == "m1"
        assert r.tokens_used == 42
        assert r.latency_ms == 100.5
        assert r.raw is None

    def test_defaults(self):
        r = LLMResponse(content="x", model="m")
        assert r.tokens_used == 0
        assert r.latency_ms == 0.0

    def test_raw_field(self):
        raw = {"choices": []}
        r = LLMResponse(content="", model="m", raw=raw)
        assert r.raw is raw


# --- LLMProvider ABC ---

class TestLLMProviderABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_subclass_must_implement_generate(self):
        class Incomplete(LLMProvider):
            pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_works(self):
        class Dummy(LLMProvider):
            def generate(self, messages, model, **kwargs):
                return LLMResponse(content="ok", model=model)
        d = Dummy()
        r = d.generate([], "test-model")
        assert r.content == "ok"


# --- OpenRouterProvider ---

def _mock_response(content="result", prompt_tokens=10, completion_tokens=20):
    """Build a mock requests.Response matching OpenRouter's format."""
    body = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }
    mock = MagicMock()
    mock.json.return_value = body
    return mock


class TestOpenRouterProvider:
    def test_is_llm_provider(self):
        assert issubclass(OpenRouterProvider, LLMProvider)

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_generate_basic(self, mock_post):
        mock_post.return_value = _mock_response("hello world")
        provider = OpenRouterProvider(api_key="test-key")
        resp = provider.generate(
            messages=[{"role": "user", "content": "hi"}],
            model="openai/gpt-5",
        )
        assert resp.content == "hello world"
        assert resp.model == "openai/gpt-5"
        assert resp.tokens_used == 30
        assert resp.latency_ms > 0

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["model"] == "openai/gpt-5"
        assert "Bearer test-key" in call_kwargs[1]["headers"]["Authorization"]

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_generate_with_response_format(self, mock_post):
        mock_post.return_value = _mock_response('{"a":1}')
        provider = OpenRouterProvider(api_key="k")
        rf = {"type": "json_schema", "json_schema": {"name": "T", "schema": {}, "strict": False}}
        provider.generate([], "m", response_format=rf)
        payload = mock_post.call_args[1]["json"]
        assert payload["response_format"] == rf

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_generate_with_plugins(self, mock_post):
        mock_post.return_value = _mock_response()
        provider = OpenRouterProvider(api_key="k")
        provider.generate([], "m", plugins=["pdf"])
        payload = mock_post.call_args[1]["json"]
        assert payload["plugins"] == ["pdf"]

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_handles_missing_usage(self, mock_post):
        mock = MagicMock()
        mock.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_post.return_value = mock
        provider = OpenRouterProvider(api_key="k")
        resp = provider.generate([], "m")
        assert resp.tokens_used == 0

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_handles_empty_choices(self, mock_post):
        mock = MagicMock()
        mock.json.return_value = {"choices": [], "usage": {}}
        mock_post.return_value = mock
        provider = OpenRouterProvider(api_key="k")
        resp = provider.generate([], "m")
        assert resp.content == ""

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key"}):
            provider = OpenRouterProvider()
            assert provider.api_key == "env-key"

    def test_api_key_explicit_overrides_env(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "env-key"}):
            provider = OpenRouterProvider(api_key="explicit")
            assert provider.api_key == "explicit"


# --- Provider wiring from config ---

class TestGetProvider:
    def test_returns_openrouter_by_default(self):
        provider = get_provider()
        assert isinstance(provider, OpenRouterProvider)

    def test_singleton(self):
        p1 = get_provider()
        p2 = get_provider()
        assert p1 is p2

    def test_reset_clears_singleton(self):
        p1 = get_provider()
        reset_provider()
        p2 = get_provider()
        assert p1 is not p2

    def test_reset_config_also_resets_provider(self):
        p1 = get_provider()
        reset_config()
        p2 = get_provider()
        assert p1 is not p2

    def test_unknown_provider_raises(self):
        cfg = get_config()
        cfg.llm.provider = "unknown"
        reset_provider()
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_provider()

    def test_provider_field_default(self):
        cfg = PipelineConfig()
        assert cfg.llm.provider == "openrouter"
