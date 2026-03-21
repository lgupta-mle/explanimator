"""Tests for US-018: Hard-mode end-to-end latency validation."""

import json
import os

import pytest

from research_viz.config.pipeline_config import reset_config
from research_viz.pipeline.run_metrics import RunMetricsCollector


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ANVAYA_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("ANVAYA_PROFILE", raising=False)
    reset_config()
    yield
    reset_config()


class TestRunMetricsCollectorIntegration:
    def test_stage_timings_in_output(self, tmp_path):
        """Metrics JSON includes stage_timings array."""
        from research_viz.providers.llm_provider import LLMProvider, LLMResponse

        class FakeProvider(LLMProvider):
            def generate(self, messages, model, **kwargs):
                return LLMResponse(content="", model=model)

        p = FakeProvider()
        collector = RunMetricsCollector()
        collector.start()
        with collector.time_stage("explanation", p):
            p._record_call(LLMResponse(content="", model="m", tokens_used=100, tokens_in=60, tokens_out=40, latency_ms=10.0))
        with collector.time_stage("codegen", p):
            pass
        collector.stop()

        path = collector.write(p, tmp_path / "output")
        data = json.loads(path.read_text())
        assert len(data["stage_timings"]) == 2
        assert data["stage_timings"][0]["stage_name"] == "explanation"
        assert data["stage_timings"][0]["tokens_used"] == 100
        assert data["stage_timings"][1]["stage_name"] == "codegen"

    def test_bottleneck_identification(self, tmp_path):
        """Slowest stage can be identified from stage_timings."""
        from research_viz.providers.llm_provider import LLMProvider, LLMResponse
        import time

        class FakeProvider(LLMProvider):
            def generate(self, messages, model, **kwargs):
                return LLMResponse(content="", model=model)

        p = FakeProvider()
        collector = RunMetricsCollector()
        collector.start()
        with collector.time_stage("fast_stage", p):
            pass
        with collector.time_stage("slow_stage", p):
            time.sleep(0.05)
        collector.stop()

        metrics = collector.collect(p)
        timings = metrics["stage_timings"]
        slowest = max(timings, key=lambda t: t["duration_seconds"])
        assert slowest["stage_name"] == "slow_stage"


class TestReportFunction:
    def test_report_pass(self, capsys):
        """report() returns True when under target latency."""
        from scripts.profile_hard_mode import report
        metrics = {
            "total_duration": 120.0,
            "total_tokens": 5000,
            "total_calls": 10,
            "total_cost_estimate": 0.05,
            "stage_timings": [
                {"stage_name": "explanation", "duration_seconds": 60.0, "tokens_used": 3000, "api_calls_count": 5},
                {"stage_name": "pipeline_remainder", "duration_seconds": 60.0, "tokens_used": 2000, "api_calls_count": 5},
            ],
            "errors": [],
        }
        assert report(metrics) is True

    def test_report_fail(self, capsys):
        """report() returns False when over target latency."""
        from scripts.profile_hard_mode import report
        metrics = {
            "total_duration": 400.0,
            "total_tokens": 50000,
            "total_calls": 30,
            "total_cost_estimate": 0.50,
            "stage_timings": [
                {"stage_name": "explanation", "duration_seconds": 350.0, "tokens_used": 40000, "api_calls_count": 20},
                {"stage_name": "pipeline_remainder", "duration_seconds": 50.0, "tokens_used": 10000, "api_calls_count": 10},
            ],
            "errors": [],
        }
        result = report(metrics)
        assert result is False
        captured = capsys.readouterr()
        assert "BOTTLENECK: explanation" in captured.out

    def test_report_identifies_bottleneck(self, capsys):
        """report() identifies the slowest stage as bottleneck on failure."""
        from scripts.profile_hard_mode import report
        metrics = {
            "total_duration": 600.0,
            "total_tokens": 10000,
            "total_calls": 5,
            "total_cost_estimate": 0.10,
            "stage_timings": [
                {"stage_name": "fast_stage", "duration_seconds": 30.0, "tokens_used": 1000, "api_calls_count": 1},
                {"stage_name": "slow_stage", "duration_seconds": 570.0, "tokens_used": 9000, "api_calls_count": 4},
            ],
            "errors": [],
        }
        report(metrics)
        captured = capsys.readouterr()
        assert "BOTTLENECK: slow_stage" in captured.out
