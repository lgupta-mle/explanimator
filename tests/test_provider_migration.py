"""Tests for US-006: pipeline stages migrated to use LLMProvider."""

import os
import json
from unittest.mock import patch, MagicMock

import pytest

from research_viz.providers.llm_provider import LLMProvider, LLMResponse, CallStat
from research_viz.providers.openrouter_provider import OpenRouterProvider
from research_viz.config.pipeline_config import (
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


def _make_mock_response(content="test", tokens=100, status=200):
    """Build a mock requests.Response for OpenRouterProvider."""
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": tokens // 2, "completion_tokens": tokens // 2},
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# --- Token accumulation ---

class TestTokenAccumulation:
    def test_call_stats_recorded(self):
        provider = OpenRouterProvider(api_key="test-key")
        with patch("requests.post", return_value=_make_mock_response("a", 100)):
            provider.generate([{"role": "user", "content": "hi"}], "m1")
        with patch("requests.post", return_value=_make_mock_response("b", 200)):
            provider.generate([{"role": "user", "content": "hi"}], "m2")

        assert provider.total_calls == 2
        assert provider.total_tokens == 300
        assert provider.call_stats[0].model == "m1"
        assert provider.call_stats[1].model == "m2"

    def test_stats_empty_initially(self):
        provider = OpenRouterProvider(api_key="test-key")
        assert provider.total_tokens == 0
        assert provider.total_calls == 0
        assert provider.call_stats == []


# --- pdf_explanation_generator uses provider ---

class TestExplanationGeneratorMigration:
    def test_call_llm_provider_uses_provider(self):
        """call_llm_provider() should route through get_provider().generate()."""
        from research_viz.manim_generator.pdf_explanation_generator import call_llm_provider

        mock_response = LLMResponse(content="result", model="m", tokens_used=50, latency_ms=10)
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = mock_response

        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            result = call_llm_provider(
                [{"role": "user", "content": "test"}],
                model_name="test/model",
            )

        assert result.content == "result"
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][1] == "test/model"

    def test_call_llm_provider_with_schema(self):
        """Schema should be converted to response_format kwarg."""
        from research_viz.manim_generator.pdf_explanation_generator import call_llm_provider
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            value: str

        mock_response = LLMResponse(content='{"value": "x"}', model="m")
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = mock_response

        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            call_llm_provider(
                [{"role": "user", "content": "test"}],
                model_name="m",
                schema=TestSchema,
            )

        kwargs = mock_provider.generate.call_args[1]
        assert "response_format" in kwargs
        assert kwargs["response_format"]["type"] == "json_schema"

    def test_call_llm_provider_with_plugins(self):
        """Plugins should be passed through to provider."""
        from research_viz.manim_generator.pdf_explanation_generator import call_llm_provider

        mock_response = LLMResponse(content="ok", model="m")
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = mock_response

        plugins = [{"id": "file-parser"}]
        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            call_llm_provider(
                [{"role": "user", "content": "test"}],
                model_name="m",
                plugins=plugins,
            )

        kwargs = mock_provider.generate.call_args[1]
        assert kwargs["plugins"] == plugins

    def test_judge_explanation_uses_provider(self):
        """judge_explanation should call provider, not requests directly."""
        from research_viz.manim_generator.pdf_explanation_generator import judge_explanation

        judge_json = json.dumps({"score": 1, "criteria_scores": {}, "feedback": None})
        mock_response = LLMResponse(content=judge_json, model="m")
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = mock_response

        with patch("research_viz.manim_generator.pdf_explanation_generator.get_provider", return_value=mock_provider):
            result = judge_explanation('{"test": "data"}', model_name="test/judge")

        assert result.score == 1
        mock_provider.generate.assert_called_once()

    def test_no_requests_import(self):
        """pdf_explanation_generator should not import requests anymore."""
        import research_viz.manim_generator.pdf_explanation_generator as mod
        import inspect
        source = inspect.getsource(mod)
        # The module should not have 'import requests' at the top level
        lines = source.split("\n")
        top_imports = [l for l in lines[:20] if l.strip().startswith("import requests")]
        assert len(top_imports) == 0


# --- llm_utils uses provider ---

class TestLLMUtilsMigration:
    def test_create_llm_response_uses_provider(self):
        """create_llm_response should use provider, not OpenAI client."""
        from research_viz.utils.llm_utils import create_llm_response

        mock_response = LLMResponse(content="hello world", model="m")
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = mock_response

        with patch("research_viz.utils.llm_utils.get_provider", return_value=mock_provider):
            result = create_llm_response(
                prepared_usr_prompt="test prompt",
                system_prompt="system",
                model_name="test/model",
            )

        assert result == "hello world"
        mock_provider.generate.assert_called_once()

    def test_create_llm_response_with_schema(self):
        """Schema should trigger structured parsing."""
        from research_viz.utils.llm_utils import create_llm_response
        from pydantic import BaseModel

        class Item(BaseModel):
            name: str

        mock_response = LLMResponse(content='{"name": "test"}', model="m")
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = mock_response

        with patch("research_viz.utils.llm_utils.get_provider", return_value=mock_provider):
            result = create_llm_response(
                prepared_usr_prompt="test",
                system_prompt="sys",
                model_name="m",
                schema=Item,
            )

        assert isinstance(result, Item)
        assert result.name == "test"

    def test_no_openai_import(self):
        """llm_utils should not import openai anymore."""
        import research_viz.utils.llm_utils as mod
        import inspect
        source = inspect.getsource(mod)
        lines = source.split("\n")
        openai_imports = [l for l in lines[:10] if "from openai" in l or "import openai" in l]
        assert len(openai_imports) == 0


# --- pdf_to_manim_pipeline uses provider ---

class TestPipelineMigration:
    def test_generate_scene_code_imports_provider_function(self):
        """Pipeline should import call_llm_provider, not call_openrouter."""
        import research_viz.manim_generator.pdf_to_manim_pipeline as mod
        assert hasattr(mod, "call_llm_provider")
        # call_openrouter should not be imported
        import inspect
        source = inspect.getsource(mod)
        assert "call_openrouter" not in source


# --- CallStat dataclass ---

class TestCallStat:
    def test_fields(self):
        s = CallStat(model="m", tokens_used=100, tokens_in=60, tokens_out=40, latency_ms=50.0)
        assert s.model == "m"
        assert s.tokens_used == 100
        assert s.tokens_in == 60
        assert s.tokens_out == 40
        assert s.latency_ms == 50.0
