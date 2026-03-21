"""Run metrics collection and persistence for pipeline jobs."""

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from research_viz.config.pipeline_config import get_config, ModelPricing
from research_viz.providers.llm_provider import LLMProvider, CallStat


@dataclass
class StageMetrics:
    """Aggregated metrics for a single pipeline stage."""
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_total: int = 0
    cost_estimate: float = 0.0
    latency_ms: float = 0.0


class RunMetricsCollector:
    """Collects and writes per-run metrics from the LLM provider."""

    def __init__(self) -> None:
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

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

        return {
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
        }

    def write(self, provider: LLMProvider, output_dir: Path) -> Path:
        """Collect metrics and write run_metrics.json to output_dir."""
        output_dir.mkdir(parents=True, exist_ok=True)
        metrics = self.collect(provider)
        path = output_dir / "run_metrics.json"
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2)
        return path
