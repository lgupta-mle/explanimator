"""
Parse a pipeline log + explanation JSON and print:
- An ASCII Gantt chart of per-segment lifecycle (codegen attempts, render, sync)
- Time-to-first-watchable-segment
- Cumulative watchable curve: at wall-clock t, how many seconds of in-order
  video is on disk and could be streamed to the viewer
- Verdict on whether the pipeline outpaces 1x playback
"""

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import tyro


LOG_TS = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ")
CODEGEN_ATTEMPT = re.compile(r"\[([^\]]+)\] Attempt (\d)/3 \(t=([\d.]+)\)")
CODEGEN_SUCCESS = re.compile(r"\[([^\]]+)\] SUCCESS in [\d.]+s \(t=([\d.]+)\)")
RENDER_START = re.compile(r"\[(\d+)\] Rendering Manim scene ([\w-]+)")
SYNC_START = re.compile(r"\[(\d+)\] Syncing audio with video")
READY = re.compile(r"\[(\d+)\] READY-TO-WATCH \(sync done, t=([\d.]+)\)")
RENDER_DONE = re.compile(r"\[(\d+)\] render done -> submitting sync \(t=([\d.]+)\)")
FINAL_SUCCESS = re.compile(r"SUCCESS! Final video:")
WPS = 2.5  # words per second of narration


@dataclass
class SegmentTimeline:
    seg_id: str
    order: int
    title: str
    duration: float
    codegen_start: Optional[float] = None
    codegen_end: Optional[float] = None
    codegen_attempts: int = 0
    render_start: Optional[float] = None
    sync_start: Optional[float] = None  # = render_end
    sync_end: Optional[float] = None


def parse_log_ts(line: str) -> Optional[float]:
    m = LOG_TS.match(line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp()


def parse_pipeline_log(log_path: Path, explanation_path: Path) -> tuple[list[SegmentTimeline], float]:
    """Parse a pipeline log and return per-segment timelines plus pipeline t0."""
    explanation = json.loads(explanation_path.read_text())
    title_to_seg: dict[str, SegmentTimeline] = {}
    by_order: dict[int, SegmentTimeline] = {}
    for s in explanation["segments"]:
        nar = s.get("narration_script", "")
        wc = len(nar.split())
        st = SegmentTimeline(
            seg_id=s["segment_id"],
            order=s.get("order", 0),
            title=s.get("title", s["segment_id"]),
            duration=wc / WPS,
        )
        title_to_seg[st.title] = st
        by_order[st.order] = st

    seg_index_to_id: dict[int, str] = {}
    pipeline_t0: Optional[float] = None
    last_event_ts: Optional[float] = None
    final_t: Optional[float] = None

    for line in log_path.read_text().splitlines():
        line_ts = parse_log_ts(line)
        if line_ts is not None:
            if pipeline_t0 is None:
                pipeline_t0 = line_ts
            last_event_ts = line_ts

        m = CODEGEN_ATTEMPT.search(line)
        if m:
            title, attempt_n, t = m.group(1), int(m.group(2)), float(m.group(3))
            seg = title_to_seg.get(title)
            if seg:
                if seg.codegen_start is None:
                    seg.codegen_start = t
                seg.codegen_attempts = max(seg.codegen_attempts, attempt_n)
            continue

        m = CODEGEN_SUCCESS.search(line)
        if m:
            title, t = m.group(1), float(m.group(2))
            seg = title_to_seg.get(title)
            if seg:
                seg.codegen_end = t
            continue

        m = RENDER_START.search(line)
        if m and line_ts is not None:
            idx, seg_id = int(m.group(1)), m.group(2)
            seg_index_to_id[idx] = seg_id
            target = next((s for s in by_order.values() if s.seg_id == seg_id), None)
            if target:
                target.render_start = line_ts
            continue

        m = SYNC_START.search(line)
        if m and line_ts is not None:
            idx = int(m.group(1))
            seg_id = seg_index_to_id.get(idx)
            if seg_id:
                target = next((s for s in by_order.values() if s.seg_id == seg_id), None)
                if target:
                    target.sync_start = line_ts
            continue

        m = RENDER_DONE.search(line)
        if m:
            idx = int(m.group(1))
            t = float(m.group(2))
            seg_id = seg_index_to_id.get(idx)
            if seg_id:
                target = next((s for s in by_order.values() if s.seg_id == seg_id), None)
                if target and target.sync_start is None:
                    # In pipelined runs, render-done == sync-start (sync is submitted immediately)
                    target.sync_start = t
            continue

        m = READY.search(line)
        if m:
            idx = int(m.group(1))
            t = float(m.group(2))
            seg_id = seg_index_to_id.get(idx)
            if seg_id:
                target = next((s for s in by_order.values() if s.seg_id == seg_id), None)
                if target:
                    target.sync_end = t
            continue

        if FINAL_SUCCESS.search(line) and line_ts is not None:
            final_t = line_ts

    # sync_end inference: next segment's render_start is a noisy proxy because
    # render and sync run on separate workers. Better: assume sync_end ≈ next
    # sync_start for parallel pool with sync_workers=2, otherwise = final_t.
    # Simplest: order segments by sync_start and use the next sync_start as a
    # cap. Last segment's sync_end = final_t.
    # For segments that didn't get an explicit READY-TO-WATCH timestamp,
    # estimate sync_end from sync_start + 5s or the next sync start.
    syncs_sorted = sorted(
        [s for s in by_order.values() if s.sync_start is not None and s.sync_end is None],
        key=lambda s: s.sync_start or 0,
    )
    all_sync_starts = sorted(
        [s.sync_start for s in by_order.values() if s.sync_start is not None]
    )
    for s in syncs_sorted:
        idx = all_sync_starts.index(s.sync_start)
        if idx + 1 < len(all_sync_starts):
            next_start = all_sync_starts[idx + 1]
            s.sync_end = min(s.sync_start + 5.0, next_start)
        else:
            s.sync_end = final_t or (last_event_ts or s.sync_start + 5.0)

    return [by_order[i] for i in sorted(by_order)], pipeline_t0 or 0.0


def render_gantt(segments: list[SegmentTimeline], t0: float, width: int = 100) -> None:
    """ASCII gantt: one row per segment, columns proportional to wall time."""
    end = max(
        (s.sync_end for s in segments if s.sync_end), default=0
    )
    total = end - t0
    if total <= 0:
        print("(no timing data)")
        return

    def col(t: Optional[float]) -> int:
        if t is None:
            return -1
        return int((t - t0) / total * width)

    print(f"\n{'Segment':30s}  Codegen + Render + Sync (each '·' ≈ {total/width:.1f}s)")
    print(f"{'':30s}  {'0s':<{width//2}}{f'{int(total)}s':>{width//2}}")
    print(f"{'':30s}  {'─' * width}")
    for s in segments:
        cg_s, cg_e = col(s.codegen_start), col(s.codegen_end)
        rd_s = col(s.render_start)
        sy_s, sy_e = col(s.sync_start), col(s.sync_end)
        bar = [" "] * width
        # codegen: '═'  render: '▓'  sync: '█'
        if cg_s >= 0 and cg_e >= 0:
            for i in range(cg_s, min(cg_e + 1, width)):
                bar[i] = "═"
        if rd_s >= 0 and sy_s >= 0:
            for i in range(rd_s, min(sy_s + 1, width)):
                bar[i] = "▓"
        if sy_s >= 0 and sy_e >= 0:
            for i in range(sy_s, min(sy_e + 1, width)):
                bar[i] = "█"
        # marker at sync_end = "ready to watch"
        if sy_e >= 0 and sy_e < width:
            bar[sy_e] = "✓"
        label = f"{s.seg_id} {s.title[:22]:22s}"
        attempts = f"({s.codegen_attempts}x)" if s.codegen_attempts > 1 else ""
        print(f"{label:30s}  {''.join(bar)} {attempts}")
    print(f"{'':30s}  {'─' * width}")
    print("Legend:  ═ codegen   ▓ render   █ sync   ✓ ready-to-watch")


def _compute_T_min(ready: list[float], durations: list[float]) -> tuple[float, int]:
    """Earliest zero-buffer start T and the bottleneck segment index."""
    T = ready[0]
    bottleneck = 0
    for i, r in enumerate(ready):
        prefix = sum(durations[:i])
        candidate = r - prefix
        if candidate > T:
            T = candidate
            bottleneck = i
    return T, bottleneck


def watchability_analysis(segments: list[SegmentTimeline], t0: float) -> None:
    """Report when a viewer could start watching with zero buffering."""
    print("\nPER-SEGMENT READY-TO-WATCH TIMES (relative to pipeline start)")
    print(f"{'Seg':>4s}  {'Title':<28s}  {'Ready at':>10s}  {'Length':>8s}  {'Cumul. content':>15s}")
    cumul = 0.0
    completed = []  # subset of segments with known sync_end
    for s in segments:
        ready_at = (s.sync_end - t0) if s.sync_end else None
        cumul += s.duration
        ready_str = f"{ready_at:.1f}s" if ready_at is not None else "FAILED"
        attempts = f" (codegen {s.codegen_attempts}x)" if s.codegen_attempts > 1 else ""
        print(f"{s.seg_id:>4s}  {s.title[:28]:<28s}  {ready_str:>10s}  {s.duration:>7.1f}s  {cumul:>14.1f}s{attempts}")
        if ready_at is not None:
            completed.append((s, ready_at))

    if len(completed) < 2:
        print("\n(too few completed segments to analyze)")
        return

    failed = [s for s in segments if s.sync_end is None]
    if failed:
        print(f"\n  WARNING: {len(failed)} segments missing from final video "
              f"({', '.join(s.seg_id for s in failed)}). Streaming analysis below "
              f"assumes the user only sees the {len(completed)} completed segments.")

    ready_times = [r for _, r in completed]
    durations = [s.duration for s, _ in completed]
    pipeline_end = max(ready_times)
    total_duration = sum(durations)

    T_min, bottleneck_i = _compute_T_min(ready_times, durations)
    savings = pipeline_end - T_min

    print("\nSTREAMING ANALYSIS — actual pipeline (current behavior)")
    print(f"  Completed segments:                 {len(completed)} / {len(segments)}")
    print(f"  Total watchable duration:           {total_duration:>7.1f}s ({total_duration/60:.1f} min)")
    print(f"  Pipeline finished at:               {pipeline_end:>7.1f}s")
    print(f"  Earliest zero-buffer start time:    {T_min:>7.1f}s")
    print(f"  Time saved vs. wait-for-finish:     {savings:>7.1f}s "
          f"({savings/pipeline_end*100:.0f}% of pipeline)")
    print(f"  Time-to-first-segment-watchable:    {ready_times[0]:>7.1f}s")
    bs = completed[bottleneck_i][0]
    print(f"  Streaming bottleneck:               {bs.seg_id} ({bs.title[:30]}) "
          f"ready @ {ready_times[bottleneck_i]:.1f}s")

    # What-if: render+sync starts as soon as each segment's codegen finishes
    # Assume render+sync wall time per segment = observed average
    rs_durations = [
        (s.sync_end - s.render_start)
        for s, _ in completed
        if s.render_start is not None and s.sync_end is not None
    ]
    avg_rs = sum(rs_durations) / len(rs_durations) if rs_durations else 5.0
    hypothetical_ready = []
    for s, _ in completed:
        if s.codegen_end is None:
            hypothetical_ready.append(None)
        else:
            hypothetical_ready.append((s.codegen_end - t0) + avg_rs)
    if all(r is not None for r in hypothetical_ready):
        T_hyp, bn_hyp = _compute_T_min(hypothetical_ready, durations)
        finish_hyp = max(hypothetical_ready)
        print("\nSTREAMING ANALYSIS — hypothetical pipeline-parallel render")
        print(f"  (assume render+sync starts immediately after each segment's codegen,")
        print(f"   avg render+sync wall time = {avg_rs:.1f}s)")
        print(f"  Pipeline finished at:               {finish_hyp:>7.1f}s "
              f"(saved {pipeline_end - finish_hyp:.0f}s)")
        print(f"  Earliest zero-buffer start time:    {T_hyp:>7.1f}s "
              f"(saved {T_min - T_hyp:.0f}s vs. actual)")
        print(f"  Time-to-first-segment-watchable:    {hypothetical_ready[0]:>7.1f}s "
              f"(saved {ready_times[0] - hypothetical_ready[0]:.0f}s)")
        bs2 = completed[bn_hyp][0]
        print(f"  New bottleneck:                     {bs2.seg_id} ({bs2.title[:30]})")


def main(
    log_path: str,
    explanation_path: str,
    width: int = 100,
):
    """Print Gantt + watchability metrics from a pipeline log."""
    segments, t0 = parse_pipeline_log(Path(log_path), Path(explanation_path))
    render_gantt(segments, t0, width=width)
    watchability_analysis(segments, t0)


if __name__ == "__main__":
    tyro.cli(main)
