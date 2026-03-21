"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    """Response from an LLM provider call."""
    content: str
    model: str
    tokens_used: int = 0  # input + output
    latency_ms: float = 0.0
    raw: Optional[dict] = field(default=None, repr=False)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Pipeline stages call generate() instead of coupling to a specific API.
    """

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        model: str,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send messages to the LLM and return a structured response.

        Args:
            messages: Chat messages in OpenAI format.
            model: Model identifier (e.g. "openai/gpt-5").
            **kwargs: Provider-specific options (response_format, plugins, etc.).

        Returns:
            LLMResponse with content, token usage, and latency.
        """
        ...
