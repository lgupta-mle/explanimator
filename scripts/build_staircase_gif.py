"""
Render a "streaming staircase" timeline GIF from a debug_ready_segments/ folder.
Each segment file is named order{NN}_seg_id_t{unix_ts}.mp4; this script:
- Reads (order, ready_at, title) from filenames
- Draws an animated horizontal Gantt where each segment fills in at its ready time
- Saves as docs/assets/streaming_staircase.gif

Pure matplotlib + Pillow. No API calls.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import tyro


_FNAME = re.compile(r"order(\d{2})_(.+)_t(\d+)\.mp4")


def parse_dir(debug_dir: Path):
    segs = []
    for p in sorted(debug_dir.glob("order*.mp4")):
        m = _FNAME.search(p.name)
        if not m:
            continue
        order = int(m.group(1))
        title = m.group(2).replace("_", " ").title()
        ready_ts = int(m.group(3))
        segs.append({"order": order, "title": title, "ready_ts": ready_ts})
    if not segs:
        raise SystemExit(f"No segments found in {debug_dir}")
    t0 = min(s["ready_ts"] for s in segs)
    for s in segs:
        s["ready_rel"] = s["ready_ts"] - t0
    return sorted(segs, key=lambda s: s["order"])


def main(
    debug_dir: str = "src/research_viz/manim_generator/output/SAM_easy_en/debug_ready_segments",
    out: str = "docs/assets/streaming_staircase.gif",
    fps: int = 15,
    duration: float = 8.0,
    width_in: float = 9.0,
    height_in: float = 4.0,
):
    """Animate a per-segment readiness timeline."""
    segs = parse_dir(Path(debug_dir))
    n = len(segs)
    total = max(s["ready_rel"] for s in segs)

    fig, ax = plt.subplots(figsize=(width_in, height_in), facecolor="#0E0D1B")
    ax.set_facecolor("#0E0D1B")
    ax.set_xlim(0, total * 1.02)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()

    labels = [f"{s['order']:>2}.  {s['title'][:34]}" for s in segs]
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=9, color="#C9B8B5", family="monospace")
    ax.set_xlabel("Wall-clock time since pipeline started (s)", color="#C9B8B5", fontsize=10)
    ax.set_title("Segments become watchable as the pipeline runs",
                 color="#F39F5A", fontsize=13, pad=14, loc="left")

    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#332B47")
    ax.tick_params(colors="#C9B8B5")
    ax.grid(axis="x", color="#221E3D", linewidth=0.6)

    bars = []
    dots = []
    for i, s in enumerate(segs):
        bar = ax.barh(i, 0, color="#F39F5A", alpha=0.85, edgecolor="#F39F5A",
                      height=0.55, zorder=3)
        bars.append(bar[0])
        dot = ax.scatter([], [], s=70, color="#F39F5A",
                         edgecolor="white", linewidth=1.2, zorder=4)
        dots.append(dot)

    cursor = ax.axvline(0, color="#E8BCB9", linewidth=2, alpha=0.7, zorder=5)
    t_label = ax.text(0.02, 1.03, "", transform=ax.transAxes,
                      color="#F39F5A", fontsize=11, family="monospace")
    counter = ax.text(0.98, 1.03, "", transform=ax.transAxes,
                      color="#C9B8B5", fontsize=11, family="monospace", ha="right")

    plt.tight_layout()

    total_frames = int(fps * duration)

    def update(frame):
        t = (frame / max(1, total_frames - 1)) * total
        ready_count = 0
        for i, s in enumerate(segs):
            if t >= s["ready_rel"]:
                bars[i].set_width(s["ready_rel"])
                dots[i].set_offsets([[s["ready_rel"], i]])
                ready_count += 1
            else:
                bars[i].set_width(0)
                dots[i].set_offsets([[None, None]])
        cursor.set_xdata([t, t])
        t_label.set_text(f"t = {t:>5.0f}s")
        counter.set_text(f"{ready_count} / {n} segments ready")
        return bars + dots + [cursor, t_label, counter]

    anim = FuncAnimation(fig, update, frames=total_frames, interval=1000 / fps, blit=False)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    anim.save(out, writer=PillowWriter(fps=fps))
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    tyro.cli(main)
