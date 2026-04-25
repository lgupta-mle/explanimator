"""Tests for LLMProvider retry with exponential backoff."""

import os
from unittest.mock import patch, MagicMock, call

import pytest
import requests

from research_viz.providers.openrouter_provider import OpenRouterProvider
from research_viz.config.pipeline_config import get_config, reset_config


@pytest.fixture(autouse=True)
def clean_state(tmp_path):
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


def _ok_response(content="ok"):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    }
    return mock


def _error_response(status_code):
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status.side_effect = requests.HTTPError(
        response=MagicMock(status_code=status_code)
    )
    return mock


class TestRetryOnTransientErrors:
    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_retries_on_429_then_succeeds(self, mock_post, mock_sleep):
        mock_post.side_effect = [_error_response(429), _ok_response("recovered")]
        provider = OpenRouterProvider(api_key="k", max_retries=3, retry_base_delay=1.0)
        resp = provider.generate([], "m")
        assert resp.content == "recovered"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_retries_on_500(self, mock_post, mock_sleep):
        mock_post.side_effect = [_error_response(500), _ok_response()]
        provider = OpenRouterProvider(api_key="k", max_retries=3, retry_base_delay=1.0)
        resp = provider.generate([], "m")
        assert resp.content == "ok"
        mock_sleep.assert_called_once_with(1.0)

    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_retries_on_502(self, mock_post, mock_sleep):
        mock_post.side_effect = [_error_response(502), _ok_response()]
        provider = OpenRouterProvider(api_key="k", max_retries=2, retry_base_delay=1.0)
        resp = provider.generate([], "m")
        assert resp.content == "ok"

    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_retries_on_503(self, mock_post, mock_sleep):
        mock_post.side_effect = [_error_response(503), _ok_response()]
        provider = OpenRouterProvider(api_key="k", max_retries=2, retry_base_delay=1.0)
        resp = provider.generate([], "m")
        assert resp.content == "ok"


class TestExponentialBackoff:
    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_backoff_delays(self, mock_post, mock_sleep):
        mock_post.side_effect = [
            _error_response(429),
            _error_response(500),
            _ok_response(),
        ]
        provider = OpenRouterProvider(api_key="k", max_retries=3, retry_base_delay=1.0)
        provider.generate([], "m")
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_custom_base_delay(self, mock_post, mock_sleep):
        mock_post.side_effect = [_error_response(429), _ok_response()]
        provider = OpenRouterProvider(api_key="k", max_retries=2, retry_base_delay=0.5)
        provider.generate([], "m")
        mock_sleep.assert_called_once_with(0.5)


class TestNonRetryableErrors:
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_400_raises_immediately(self, mock_post):
        mock_post.return_value = _error_response(400)
        provider = OpenRouterProvider(api_key="k", max_retries=3)
        with pytest.raises(requests.HTTPError):
            provider.generate([], "m")
        assert mock_post.call_count == 1

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_401_raises_immediately(self, mock_post):
        mock_post.return_value = _error_response(401)
        provider = OpenRouterProvider(api_key="k", max_retries=3)
        with pytest.raises(requests.HTTPError):
            provider.generate([], "m")
        assert mock_post.call_count == 1

    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_404_raises_immediately(self, mock_post):
        mock_post.return_value = _error_response(404)
        provider = OpenRouterProvider(api_key="k", max_retries=3)
        with pytest.raises(requests.HTTPError):
            provider.generate([], "m")
        assert mock_post.call_count == 1


class TestMaxRetriesExhausted:
    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_raises_after_all_retries_exhausted(self, mock_post, mock_sleep):
        mock_post.return_value = _error_response(429)
        provider = OpenRouterProvider(api_key="k", max_retries=3, retry_base_delay=1.0)
        with pytest.raises(requests.HTTPError):
            provider.generate([], "m")
        assert mock_post.call_count == 3
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]


class TestConnectionAndTimeoutRetry:
    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_retries_on_connection_error(self, mock_post, mock_sleep):
        mock_post.side_effect = [requests.ConnectionError("conn failed"), _ok_response()]
        provider = OpenRouterProvider(api_key="k", max_retries=2, retry_base_delay=1.0)
        resp = provider.generate([], "m")
        assert resp.content == "ok"
        mock_sleep.assert_called_once_with(1.0)

    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_retries_on_timeout(self, mock_post, mock_sleep):
        mock_post.side_effect = [requests.Timeout("timed out"), _ok_response()]
        provider = OpenRouterProvider(api_key="k", max_retries=2, retry_base_delay=1.0)
        resp = provider.generate([], "m")
        assert resp.content == "ok"

    @patch("research_viz.providers.openrouter_provider.time.sleep")
    @patch("research_viz.providers.openrouter_provider.requests.post")
    def test_connection_error_exhausts_retries(self, mock_post, mock_sleep):
        mock_post.side_effect = requests.ConnectionError("down")
        provider = OpenRouterProvider(api_key="k", max_retries=2, retry_base_delay=1.0)
        with pytest.raises(requests.ConnectionError):
            provider.generate([], "m")
        assert mock_post.call_count == 2


class TestRetryConfig:
    def test_config_has_retry_fields(self):
        cfg = get_config()
        assert cfg.llm.max_retries == 3
        assert cfg.llm.retry_base_delay == 1.0

    def test_provider_gets_retry_config(self):
        from research_viz.config.pipeline_config import get_provider
        provider = get_provider()
        assert provider.max_retries == 3
        assert provider.retry_base_delay == 1.0
