"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CallStat:
    """Stats for a single LLM call."""
    model: str
    tokens_used: int
    latency_ms: float


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
    Tracks per-call stats for token usage accumulation.
    """

    def __init__(self) -> None:
        self.call_stats: list[CallStat] = []

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens_used for s in self.call_stats)

    @property
    def total_calls(self) -> int:
        return len(self.call_stats)

    def _record_call(self, response: LLMResponse) -> None:
        """Record stats from a completed call."""
        self.call_stats.append(
            CallStat(
                model=response.model,
                tokens_used=response.tokens_used,
                latency_ms=response.latency_ms,
            )
        )

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
