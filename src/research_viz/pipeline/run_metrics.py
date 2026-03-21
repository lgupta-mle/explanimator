"""Run metrics collection and persistence for pipeline jobs."""

import logging
import json
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from research_viz.config.pipeline_config import get_config, ModelPricing
from research_viz.providers.llm_provider import LLMProvider, CallStat

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """Aggregated metrics for a single pipeline stage."""
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_total: int = 0
    cost_estimate: float = 0.0
    latency_ms: float = 0.0


@dataclass
class StageTiming:
    """Wall-clock timing for a pipeline stage."""
    stage_name: str
    duration_seconds: float
    tokens_used: int = 0
    api_calls_count: int = 0
    error: Optional[str] = None


@dataclass
class StageError:
    """Structured error record for a pipeline stage."""
    stage: str
    exception_type: str
    message: str
    artifact_id: Optional[str] = None
    recoverable: bool = False


class RunMetricsCollector:
    """Collects and writes per-run metrics from the LLM provider."""

    def __init__(self) -> None:
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self.stage_timings: list[StageTiming] = []
        self.stage_errors: list[StageError] = []

    def start(self) -> None:
        self._start_time = time.time()

    def stop(self) -> None:
        self._end_time = time.time()

    @property
    def total_duration(self) -> float:
        if self._start_time is None:
            return 0.0
        end = self._end_time or time.time()
        return end - self._start_time

    @contextmanager
    def time_stage(self, stage_name: str, provider: Optional[LLMProvider] = None):
        """Context manager that times a stage and logs metrics on completion."""
        start = time.time()
        tokens_before = provider.total_tokens if provider else 0
        calls_before = provider.total_calls if provider else 0
        try:
            yield
        except Exception as exc:
            duration = time.time() - start
            tokens = (provider.total_tokens - tokens_before) if provider else 0
            calls = (provider.total_calls - calls_before) if provider else 0
            timing = StageTiming(stage_name, duration, tokens, calls, error=type(exc).__name__)
            self.stage_timings.append(timing)
            logger.error(f"Stage {stage_name} failed after {duration:.1f}s: {type(exc).__name__}: {exc}")
            raise
        else:
            duration = time.time() - start
            tokens = (provider.total_tokens - tokens_before) if provider else 0
            calls = (provider.total_calls - calls_before) if provider else 0
            timing = StageTiming(stage_name, duration, tokens, calls)
            self.stage_timings.append(timing)
            logger.info(f"Stage {stage_name}: {duration:.1f}s, {tokens} tokens, {calls} API calls")

    def record_error(self, stage: str, exc: Exception, artifact_id: Optional[str] = None, recoverable: bool = False):
        """Record a structured error for a stage."""
        err = StageError(
            stage=stage,
            exception_type=type(exc).__name__,
            message=str(exc)[:200],
            artifact_id=artifact_id,
            recoverable=recoverable,
        )
        self.stage_errors.append(err)
        logger.error(f"Stage {stage} error: {type(exc).__name__}: {exc} (artifact={artifact_id}, recoverable={recoverable})")

    def collect(self, provider: LLMProvider) -> dict:
        """Build the metrics dict from provider call_stats."""
        pricing = get_config().llm.model_pricing
        stages: dict[str, StageMetrics] = defaultdict(StageMetrics)
        total_cost = 0.0

        for stat in provider.call_stats:
            stage_key = stat.stage or "unknown"
            sm = stages[stage_key]
            sm.calls += 1
            sm.tokens_in += stat.tokens_in
            sm.tokens_out += stat.tokens_out
            sm.tokens_total += stat.tokens_used
            sm.latency_ms += stat.latency_ms

            model_price = pricing.get(stat.model)
            if model_price:
                call_cost = (stat.tokens_in * model_price.input
                             + stat.tokens_out * model_price.output)
                sm.cost_estimate += call_cost
                total_cost += call_cost

        metrics = {
            "total_tokens": provider.total_tokens,
            "total_cost_estimate": round(total_cost, 6),
            "total_duration": round(self.total_duration, 2),
            "total_calls": provider.total_calls,
            "calls_per_stage": {
                stage: {
                    "calls": sm.calls,
                    "tokens_in": sm.tokens_in,
                    "tokens_out": sm.tokens_out,
                    "tokens_total": sm.tokens_total,
                    "cost_estimate": round(sm.cost_estimate, 6),
                    "latency_ms": round(sm.latency_ms, 1),
                }
                for stage, sm in stages.items()
            },
            "stage_timings": [
                {
                    "stage_name": t.stage_name,
                    "duration_seconds": round(t.duration_seconds, 2),
                    "tokens_used": t.tokens_used,
                    "api_calls_count": t.api_calls_count,
                    **({"error": t.error} if t.error else {}),
                }
                for t in self.stage_timings
            ],
            "errors": [
                {
                    "stage": e.stage,
                    "exception_type": e.exception_type,
                    "message": e.message,
                    **({"artifact_id": e.artifact_id} if e.artifact_id else {}),
                    "recoverable": e.recoverable,
                }
                for e in self.stage_errors
            ],
        }
        return metrics

    def write(self, provider: LLMProvider, output_dir: Path) -> Path:
        """Collect metrics and write run_metrics.json to output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        metrics = self.collect(provider)
        path = output_dir / "run_metrics.json"
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2)
        return path
