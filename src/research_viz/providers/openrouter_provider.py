"""OpenRouter LLM provider implementation."""

import os
import time
from typing import Any

import requests

from research_viz.providers.llm_provider import LLMProvider, LLMResponse


class OpenRouterProvider(LLMProvider):
    """LLM provider that routes calls through the OpenRouter API."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")

    def generate(
        self,
        messages: list[dict],
        model: str,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call OpenRouter and return an LLMResponse.

        Supported kwargs:
            response_format: dict for structured output (json_schema).
            plugins: list of OpenRouter plugins.
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

        start = time.perf_counter()
        resp = requests.post(self.BASE_URL, headers=headers, json=payload)
        latency_ms = (time.perf_counter() - start) * 1000

        data = resp.json()

        content = ""
        tokens_used = 0
        if "choices" in data and data["choices"]:
            content = data["choices"][0].get("message", {}).get("content", "")
        if "usage" in data:
            usage = data["usage"]
            tokens_used = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

        return LLMResponse(
            content=content,
            model=model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            raw=data,
        )
