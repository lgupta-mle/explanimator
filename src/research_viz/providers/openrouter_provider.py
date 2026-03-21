"""OpenRouter LLM provider implementation."""

import logging
import os
import time
from typing import Any

import requests

from research_viz.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}


class OpenRouterProvider(LLMProvider):
    """LLM provider that routes calls through the OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str | None = None,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
    ):
        super().__init__()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }

        if kwargs.get("plugins"):
            payload["plugins"] = kwargs["plugins"]

        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]

        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.perf_counter()
                resp = requests.post(self.BASE_URL, headers=headers, json=payload)
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

                data = resp.json()
                content = ""
                tokens_used = 0
                if "choices" in data and data["choices"]:
                    content = data["choices"][0].get("message", {}).get("content", "")
                if "usage" in data:
                    usage = data["usage"]
                    tokens_used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

                response = LLMResponse(
                    content=content,
                    model=model,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms,
                    raw=data,
                )
                self._record_call(response)
                return response

            except (requests.ConnectionError, requests.Timeout) as exc:
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
