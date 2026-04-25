"""
Hard-mode end-to-end latency profiling script.

Runs the pipeline in hard mode on a sample paper and reports per-stage timings.
Uses fast model tier + parallel stages + single-pass ffmpeg + skip judge.

Usage:
    python scripts/profile_hard_mode.py --pdf-path papers/sample.pdf
    python scripts/profile_hard_mode.py --pdf-path papers/sample.pdf --output-dir output/profile_run
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from research_viz.config.pipeline_config import get_config, get_provider, reset_config
from research_viz.pipeline.run_metrics import RunMetricsCollector

logger = logging.getLogger(__name__)

TARGET_LATENCY_SECONDS = 300  # 5 minutes


def run_profile(pdf_path: str, output_dir: str) -> dict:
    """Run hard-mode pipeline with profiling and return metrics."""
    # Force hard difficulty tier
    os.environ.setdefault("ANVAYA_PROFILE", "dev")
    reset_config()
    cfg = get_config()
    provider = get_provider()

    collector = RunMetricsCollector()
    collector.start()

    from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
    from research_viz.manim_generator.pdf_to_manim_pipeline import run_pipeline

    # Stage 1: Explanation (with skip_judge for hard mode)
    explanation_output = f"{output_dir}/explanation.json"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    provider.set_stage("explanation")
    with collector.time_stage("explanation", provider):
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_output,
            difficulty="hard",
        )

    if not explanation:
        logger.error("Explanation generation failed")
        collector.stop()
        return collector.collect(provider)

    # Stage 2+3: Code gen + TTS (parallel) + assembly via run_pipeline
    provider.set_stage("pipeline")
    with collector.time_stage("pipeline_remainder", provider):
        result = run_pipeline(
            pdf_path=pdf_path,
            output_dir=output_dir,
            skip_explanation=True,
            explanation_path=explanation_output,
        )

    collector.stop()
    metrics = collector.collect(provider)

    # Write metrics
    metrics_path = Path(output_dir) / "run_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    return metrics


def report(metrics: dict) -> bool:
    """Print profiling report and return True if under target latency."""
    total = metrics["total_duration"]

    print(f"\n{'=' * 60}")
    print(f"HARD-MODE PROFILING REPORT")
    print(f"{'=' * 60}")

    if metrics.get("stage_timings"):
        print(f"\nPer-stage timings:")
        for t in metrics["stage_timings"]:
            status = "ERROR" if t.get("error") else "OK"
            print(f"  {t['stage_name']:25s} {t['duration_seconds']:7.1f}s  "
                  f"tokens={t['tokens_used']:6d}  calls={t['api_calls_count']:2d}  [{status}]")

    print(f"\nTotal duration:    {total:.1f}s")
    print(f"Target:            {TARGET_LATENCY_SECONDS}s (5 min)")
    print(f"Total tokens:      {metrics['total_tokens']}")
    print(f"Total API calls:   {metrics['total_calls']}")
    print(f"Estimated cost:    ${metrics['total_cost_estimate']:.4f}")

    passed = total < TARGET_LATENCY_SECONDS
    if passed:
        print(f"\nRESULT: PASS ({total:.0f}s < {TARGET_LATENCY_SECONDS}s)")
    else:
        print(f"\nRESULT: FAIL ({total:.0f}s >= {TARGET_LATENCY_SECONDS}s)")
        # Identify bottleneck
        if metrics.get("stage_timings"):
            slowest = max(metrics["stage_timings"], key=lambda t: t["duration_seconds"])
            print(f"BOTTLENECK: {slowest['stage_name']} ({slowest['duration_seconds']:.1f}s)")

    print(f"{'=' * 60}\n")
    return passed


def main():
    parser = argparse.ArgumentParser(description="Profile hard-mode pipeline latency")
    parser.add_argument("--pdf-path", required=True, help="Path to sample PDF")
    parser.add_argument("--output-dir", default="output/profile_hard_mode", help="Output directory")
    args = parser.parse_args()

    if not Path(args.pdf_path).exists():
        print(f"PDF not found: {args.pdf_path}")
        sys.exit(1)

    metrics = run_profile(args.pdf_path, args.output_dir)
    passed = report(metrics)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
