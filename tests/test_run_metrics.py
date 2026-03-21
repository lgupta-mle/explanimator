"""Tests for US-007: Token usage tracking per job."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from research_viz.config.pipeline_config import (
    PipelineConfig,
    ModelPricing,
    get_config,
    reset_config,
)
from research_viz.providers.llm_provider import CallStat, LLMProvider, LLMResponse
from research_viz.pipeline.run_metrics import RunMetricsCollector, StageMetrics


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path):
    os.environ["ANVAYA_CONFIG_PATH"] = str(tmp_path / "config.yaml")
    os.environ.pop("ANVAYA_PROFILE", None)
    reset_config()
    yield
    reset_config()
    os.environ.pop("ANVAYA_CONFIG_PATH", None)


class FakeProvider(LLMProvider):
    def generate(self, messages, model, **kwargs):
        return LLMResponse(content="", model=model)


# --- CallStat fields ---

def test_call_stat_has_token_breakdown():
    stat = CallStat(model="m", tokens_used=150, tokens_in=100, tokens_out=50, latency_ms=10.0)
    assert stat.tokens_in == 100
    assert stat.tokens_out == 50

def test_call_stat_has_stage():
    stat = CallStat(model="m", tokens_used=0, tokens_in=0, tokens_out=0, latency_ms=0, stage="explanation")
    assert stat.stage == "explanation"

def test_call_stat_default_stage_empty():
    stat = CallStat(model="m", tokens_used=0, tokens_in=0, tokens_out=0, latency_ms=0)
    assert stat.stage == ""


# --- LLMResponse fields ---

def test_llm_response_has_token_breakdown():
    r = LLMResponse(content="hi", model="m", tokens_used=30, tokens_in=10, tokens_out=20)
    assert r.tokens_in == 10
    assert r.tokens_out == 20


# --- Provider stage tracking ---

def test_provider_set_stage():
    p = FakeProvider()
    p.set_stage("judge")
    resp = LLMResponse(content="", model="m", tokens_used=5, tokens_in=2, tokens_out=3, latency_ms=1.0)
    p._record_call(resp)
    assert p.call_stats[0].stage == "judge"

def test_provider_reset_stats():
    p = FakeProvider()
    resp = LLMResponse(content="", model="m", tokens_used=5, tokens_in=2, tokens_out=3, latency_ms=1.0)
    p._record_call(resp)
    assert p.total_calls == 1
    p.reset_stats()
    assert p.total_calls == 0
    assert p._current_stage == ""


# --- ModelPricing config ---

def test_model_pricing_in_config():
    cfg = PipelineConfig()
    assert "openai/gpt-5" in cfg.llm.model_pricing
    pricing = cfg.llm.model_pricing["openai/gpt-5"]
    assert pricing.input > 0
    assert pricing.output > 0

def test_model_pricing_from_yaml(tmp_path):
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text(
        "llm:\n"
        "  model_pricing:\n"
        "    test/model:\n"
        "      input: 0.001\n"
        "      output: 0.002\n"
    )
    os.environ["ANVAYA_CONFIG_PATH"] = str(cfg_yaml)
    reset_config()
    cfg = get_config()
    assert "test/model" in cfg.llm.model_pricing
    assert cfg.llm.model_pricing["test/model"].input == 0.001


# --- RunMetricsCollector ---

def _make_provider_with_stats() -> FakeProvider:
    p = FakeProvider()
    p.set_stage("explanation")
    p._record_call(LLMResponse(content="", model="openai/gpt-5", tokens_used=1500, tokens_in=1000, tokens_out=500, latency_ms=200.0))
    p._record_call(LLMResponse(content="", model="openai/gpt-5", tokens_used=800, tokens_in=600, tokens_out=200, latency_ms=150.0))
    p.set_stage("code_gen")
    p._record_call(LLMResponse(content="", model="anthropic/claude-sonnet-4.5", tokens_used=2000, tokens_in=1200, tokens_out=800, latency_ms=300.0))
    return p

def test_collect_totals():
    p = _make_provider_with_stats()
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    metrics = collector.collect(p)
    assert metrics["total_tokens"] == 4300
    assert metrics["total_calls"] == 3

def test_collect_calls_per_stage():
    p = _make_provider_with_stats()
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    metrics = collector.collect(p)
    stages = metrics["calls_per_stage"]
    assert "explanation" in stages
    assert "code_gen" in stages
    assert stages["explanation"]["calls"] == 2
    assert stages["code_gen"]["calls"] == 1
    assert stages["explanation"]["tokens_in"] == 1600
    assert stages["code_gen"]["tokens_out"] == 800

def test_collect_cost_estimate():
    p = _make_provider_with_stats()
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    metrics = collector.collect(p)
    assert metrics["total_cost_estimate"] > 0
    # Verify explanation cost: (1000+600)*2.5e-6 input + (500+200)*10e-6 output = 0.004 + 0.007 = 0.011
    exp_stage = metrics["calls_per_stage"]["explanation"]
    expected_exp_cost = 1600 * 2.5e-6 + 700 * 10.0e-6
    assert abs(exp_stage["cost_estimate"] - expected_exp_cost) < 1e-9

def test_collect_duration():
    collector = RunMetricsCollector()
    collector.start()
    import time
    time.sleep(0.05)
    collector.stop()
    metrics = collector.collect(FakeProvider())
    assert metrics["total_duration"] >= 0.04

def test_collect_unknown_model_no_cost():
    """Models not in pricing table contribute zero cost."""
    p = FakeProvider()
    p.set_stage("test")
    p._record_call(LLMResponse(content="", model="unknown/model", tokens_used=100, tokens_in=50, tokens_out=50, latency_ms=10.0))
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    metrics = collector.collect(p)
    assert metrics["total_cost_estimate"] == 0.0

def test_write_creates_json(tmp_path):
    p = _make_provider_with_stats()
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    out_dir = tmp_path / "run_output"
    path = collector.write(p, out_dir)
    assert path.exists()
    data = json.loads(path.read_text())
    assert "total_tokens" in data
    assert "calls_per_stage" in data
    assert "total_cost_estimate" in data
    assert "total_duration" in data

def test_write_creates_parent_dirs(tmp_path):
    p = FakeProvider()
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    out_dir = tmp_path / "a" / "b" / "c"
    path = collector.write(p, out_dir)
    assert path.exists()

def test_no_calls_produces_empty_metrics():
    p = FakeProvider()
    collector = RunMetricsCollector()
    collector.start()
    collector.stop()
    metrics = collector.collect(p)
    assert metrics["total_tokens"] == 0
    assert metrics["total_cost_estimate"] == 0.0
    assert metrics["calls_per_stage"] == {}
