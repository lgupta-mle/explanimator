"""OpenRouter LLM provider implementation."""

import logging
import os
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter

from research_viz.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}

CACHE_AWARE_MODEL_PREFIXES = ("anthropic/", "google/gemini")


def _supports_prompt_cache(model: str) -> bool:
    m = model.lower()
    return any(m.startswith(p) for p in CACHE_AWARE_MODEL_PREFIXES)


def _mark_system_cached(messages: list[dict]) -> list[dict]:
    """Add a cache_control breakpoint to the first system message.

    Returns a new messages list; original is not mutated. Caller should
    only invoke this when the target model supports prompt caching.
    """
    out = []
    marked = False
    for msg in messages:
        if not marked and msg.get("role") == "system":
            content = msg["content"]
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            else:
                content = [dict(p) for p in content]
            content[-1] = {**content[-1], "cache_control": {"type": "ephemeral"}}
            out.append({**msg, "content": content})
            marked = True
        else:
            out.append(msg)
    return out


class OpenRouterProvider(LLMProvider):
    """LLM provider that routes calls through the OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        pool_size: int = 32,
        route_sort: str | None = None,
        prompt_cache: bool = True,
    ):
        super().__init__()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.route_sort = route_sort
        self.prompt_cache = prompt_cache

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def generate(
        self,
        messages: list[dict],
        model: str,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call OpenRouter with retry on transient failures.

        Retries on: 429, 500, 502, 503, and timeout/connection errors.
        Raises immediately on: 400, 401, 404 and other non-retryable errors.
        """
        if self.prompt_cache and _supports_prompt_cache(model):
            messages = _mark_system_cached(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if kwargs.get("plugins"):
            payload["plugins"] = kwargs["plugins"]

        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]

        if kwargs.get("reasoning"):
            payload["reasoning"] = kwargs["reasoning"]

        provider_routing = kwargs.get("provider")
        if provider_routing is None and self.route_sort:
            provider_routing = {"sort": self.route_sort}
        if provider_routing:
            payload["provider"] = provider_routing

        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.perf_counter()
                resp = self.session.post(self.BASE_URL, json=payload)
                latency_ms = (time.perf_counter() - start) * 1000

                if resp.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < self.max_retries:
                        wait = self.retry_base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            "Retryable HTTP %d on attempt %d/%d, waiting %.1fs",
                            resp.status_code, attempt, self.max_retries, wait,
                        )
                        time.sleep(wait)
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()

                try:
                    data = resp.json()
                except ValueError:
                    logger.error(
                        "Non-JSON response from OpenRouter (status=%d, content-type=%s, len=%d): %s",
                        resp.status_code,
                        resp.headers.get("content-type"),
                        len(resp.text),
                        resp.text[:500],
                    )
                    raise
                if "error" in data and "choices" not in data:
                    err = data["error"]
                    raise requests.HTTPError(
                        f"OpenRouter error {err.get('code')}: {err.get('message')}",
                        response=resp,
                    )

                content = ""
                tokens_used = 0
                if "choices" in data and data["choices"]:
                    msg = data["choices"][0].get("message", {})
                    content = msg.get("content") or ""
                    if not content:
                        # Reasoning models sometimes only populate `reasoning`
                        content = msg.get("reasoning") or ""
                    if not content:
                        logger.warning(
                            "Empty content from %s; finish_reason=%s, message keys=%s",
                            model,
                            data["choices"][0].get("finish_reason"),
                            list(msg.keys()),
                        )
                tokens_in = 0
                tokens_out = 0
                cache_read = 0
                cache_write = 0
                if "usage" in data:
                    usage = data["usage"]
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    tokens_used = tokens_in + tokens_out
                    details = usage.get("prompt_tokens_details") or {}
                    cache_read = (
                        details.get("cached_tokens")
                        or usage.get("cache_read_input_tokens", 0)
                    )
                    cache_write = usage.get("cache_creation_input_tokens", 0)

                response = LLMResponse(
                    content=content,
                    model=model,
                    tokens_used=tokens_used,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    latency_ms=latency_ms,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                    raw=data,
                )
                self._record_call(response)
                return response

            except (
                requests.ConnectionError,
                requests.Timeout,
                requests.exceptions.ChunkedEncodingError,
            ) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    wait = self.retry_base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "%s on attempt %d/%d, waiting %.1fs",
                        type(exc).__name__, attempt, self.max_retries, wait,
                    )
                    time.sleep(wait)
                    continue
                raise

        raise last_exception  # type: ignore[misc]
