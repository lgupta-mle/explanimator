"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CallStat:
    """Stats for a single LLM call."""
    model: str
    tokens_used: int
    tokens_in: int
    tokens_out: int
    latency_ms: float
    stage: str = ""


@dataclass
class LLMResponse:
    """Response from an LLM provider call."""
    content: str
    model: str
    tokens_used: int = 0  # input + output
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    raw: Optional[dict] = field(default=None, repr=False)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Pipeline stages call generate() instead of coupling to a specific API.
    Tracks per-call stats for token usage accumulation.
    """

    def __init__(self) -> None:
        self.call_stats: list[CallStat] = []
        self._current_stage: str = ""

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens_used for s in self.call_stats)

    @property
    def total_calls(self) -> int:
        return len(self.call_stats)

    def set_stage(self, stage: str) -> None:
        """Set the current pipeline stage for call attribution."""
        self._current_stage = stage

    def reset_stats(self) -> None:
        """Clear accumulated call stats for a new run."""
        self.call_stats = []
        self._current_stage = ""

    def _record_call(self, response: LLMResponse) -> None:
        """Record stats from a completed call."""
        self.call_stats.append(
            CallStat(
                model=response.model,
                tokens_used=response.tokens_used,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                latency_ms=response.latency_ms,
                stage=self._current_stage,
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
