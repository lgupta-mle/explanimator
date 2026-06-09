# Anvya — Research papers → 3Blue1Brown-style explainer videos

Turn any research-paper PDF into a narrated, Manim-animated explainer video.
The pipeline reads the paper, writes a 3B1B-style lesson plan, generates Manim
code per segment, renders and syncs each segment to AI narration, and stitches
them into a final MP4 — and starts handing you finished segments while the rest
of the video is still being rendered.

<p align="center">
  <img src="docs/assets/demo_sam.gif" alt="Generated SAM explainer (3x speed)" width="640" />
</p>

> The clip above is segment 1 of the SAM paper (Segment Anything, Kirillov et
> al.) generated end-to-end from the PDF — 3× speed for the README.

---

## Why this is interesting

**Pipeline-parallel codegen → render → sync** means each segment moves through
the three stages independently. As soon as a segment's code is written, its
render is queued; the moment its render finishes, audio sync starts. The
final concat happens once at the end. The practical effect: **segment 1 is
ready to watch ~10× sooner than it would be if every stage ran in bulk.**

<p align="center">
  <img src="docs/assets/streaming_staircase.gif" alt="Streaming staircase: segments become watchable as the pipeline runs" width="720" />
</p>

```
                              BEFORE              AFTER
Time to first watchable:      ≈ 19 min            ≈ 8 min
Total wall time:              ≈ 20 min            ≈ 22 min
Codegen prompt-cache hit:     —                   ≈ 70–80 %
```

Measured on `resources/SAM.pdf` → "Beginner" tier (12 segments, with audio).
Numbers above are from the optimization branch's CI runs.

---

## Quick start

### 1. Prerequisites

```bash
# Python 3.10+
python --version

# ffmpeg for audio/video processing
brew install ffmpeg          # macOS
# or: apt-get install ffmpeg # Debian/Ubuntu

# Manim for rendering
pip install manim
# or follow https://docs.manim.community/en/stable/installation.html
```

### 2. Install Python dependencies

Two paths — use whichever you already have:

```bash
# Option A — uv (recommended; what we use)
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Option B — vanilla pip
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API keys

Copy the template and fill in your key:

```bash
cp .env.example .env
# Edit .env and paste your OpenRouter key
```

`.env` needs at minimum:

```env
OPENROUTER_API_KEY=sk-or-v1-…
```

That's it for the default config. All LLM calls (explanation, judge, codegen)
and Gemini TTS go through OpenRouter. Get a key at
https://openrouter.ai/keys — pay-as-you-go, no monthly minimum.

`OPENAI_API_KEY` is **only** required if you switch the TTS provider back
to OpenAI in `config.yaml` (`audio.provider: openai`), or if you want to
rebuild the Manim RAG vector DB from scratch (a pre-built one ships in
`data/manim_docs/vector_db/chroma_db/`).

### 4. Run

```bash
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --pdf-path resources/SAM.pdf \
  --difficulty easy
```

The pipeline-parallel fast path is on by default for single-language English
runs. Output lands in
`src/research_viz/manim_generator/output/<paper>_<difficulty>_en/`:

- `final_video.mp4` — the stitched final video
- `debug_ready_segments/order{NN}_*.mp4` — per-segment files, written the
  moment each becomes watchable (great for streaming UI demos)
- `run_metrics.json` — per-stage timing, cache hit rate, cost estimate
- `<paper>_explanation.json` — the structured 3B1B lesson plan
- `audio_beats/beat_timeline.json` — per-beat TTS timing
- `<paper>_animation.py` — the generated Manim code

---

## Difficulty tiers

```
easy    →  10–14 segments, 350–600 words/segment, prereqs taught from scratch
medium  →   4–6  segments, 150–300 words/segment, full notation
hard    →   2–3  segments,  80–180 words/segment, terse, expert-level
```

```bash
# CLI flag picks the tier directly
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
  --pdf-path <paper.pdf> --difficulty easy
```

Each tier maps to a different model lineup in `config.yaml`:

| Tier   | Explanation                  | Codegen                  | Judge       |
| ------ | ---------------------------- | ------------------------ | ----------- |
| easy   | gemini-3.1-pro-preview       | gemini-3.1-pro-preview   | gemini-2.5-flash |
| medium | gemini-3.1-flash-lite        | claude-sonnet-4.5        | gemini-2.5-flash |
| hard   | gemini-3.1-flash-lite        | deepseek-v3.2            | (skipped)   |

Override any of these in `config.yaml` (root) or `config/dev.yaml` (per-profile).

---

## Pipeline flow

```
PDF
  │
  ▼
[ 1 ] Explanation        Pro LLM reads the PDF and writes a structured
                         3B1B lesson plan: opening question, running
                         example, segments × { intuition + technical +
                         narration script }. Judge loop verifies quality.
  │
  ▼
[ 2 ] Pipeline-parallel codegen → render → sync (per segment)
       │
       ├── Audio (parallel)       Gemini TTS narrates every beat;
       │                          per-segment readiness signals downstream.
       │
       ├── Codegen (parallel)     LLM writes the Manim animation for the
       │                          segment, with beat-timed run_times. RAG
       │                          retrieves Manim docs on execution errors.
       │
       ├── Render (parallel)      Manim renders the scene as soon as its
       │                          codegen finishes.
       │
       └── Sync   (parallel)      ffmpeg single-pass: speed-adjust the
                                  video to match audio duration, mux.
                                  Result: a per-segment MP4 that's
                                  immediately watchable.
  │
  ▼
[ 3 ] Stitch              Concat all per-segment MP4s → final_video.mp4
```

The pipeline is **resumable.** If a run is interrupted, re-running with
the same args picks up where it left off — anything already on disk
(explanation JSON, scene metadata, audio beats, rendered scenes) is
reused.

---

## Web app (beta)

There's also a browser UI for uploading a PDF and watching segments
stream onto the page as they're rendered.

```bash
# Terminal 1 — backend (FastAPI + SSE)
cd anvaya_website/apps/api
pip install -r requirements.txt        # only once
python main.py

# Terminal 2 — frontend (static React-via-CDN prototype)
cd app
python -m http.server 5500

# Then open http://localhost:5500
```

Flow: upload a PDF → progress page shows five circles (Explanation / Audio /
Codegen / Render / Sync) lighting up for segment 1 in real time → other
segments appear as "Preparing segment N…" cards → as soon as any segment is
done the page auto-scrolls to an inline `<video>` that starts playing it →
when it ends, it auto-advances to the next ready segment.

The `app/` directory uses Babel-standalone (no build step), so you can edit
`.jsx` files and reload.

---

## Configuration

`config.yaml` at the repo root carries the defaults. `config/{dev,staging,prod}.yaml`
overlay on top (selected via `ANVAYA_PROFILE`, default `dev`). Common knobs:

```yaml
llm:
  route_sort: throughput        # OpenRouter picks the fastest endpoint
  prompt_cache: true            # auto-add cache_control on system prompts
  judge_reasoning_effort: null  # "low" | "medium" | "high" to opt in

audio:
  tts_model: google/gemini-3.1-flash-tts-preview
  voice: Leda
  provider: openrouter
  max_workers: 4

video:
  quality: l                    # l/m/h/k → 480p/720p/1080p/2160p
  sync_mode: segment            # vs "beat"  (frame-perfect, experimental)
  max_speed_change: 0.3         # cap on speed adjust during audio sync

manim:
  timeout: 120
  max_workers: 4
  max_retries: 3                # per-segment retries on codegen failure
```

ENV overrides also work for any key — e.g. `ANVAYA_VIDEO__QUALITY=h`.

---

## Project layout

```
src/research_viz/
├── manim_generator/
│   ├── pdf_to_manim_pipeline.py        # Main orchestrator + pipelined runner
│   ├── pdf_explanation_generator.py    # PDF → structured 3B1B lesson
│   ├── scene_validator.py              # Static fixes on generated Manim code
│   └── prompts/                        # System prompts for each stage
├── audio_generator/
│   └── beat_sync_tts.py                # StreamingBeatGenerator + classic mode
├── book_generator/                     # Book-to-video pipeline (chapters)
├── providers/
│   ├── llm_provider.py                 # Provider ABC + LLMResponse
│   └── openrouter_provider.py          # OpenRouter impl w/ retries + caching
├── pipeline/
│   ├── checkpoint.py                   # Resume support
│   └── run_metrics.py                  # Per-stage timing + cost
├── translation/                        # Multilingual fan-out
├── preprocessing/                      # Manim docs scraping + RAG build
└── schemas/                            # Pydantic models

anvaya_website/apps/api/                # FastAPI backend (SSE + segments)
app/                                    # React-via-CDN prototype frontend

scripts/
├── analyze_pipeline_timeline.py        # Gantt + time-to-first-watchable from logs
├── build_staircase_gif.py              # README streaming-staircase animation
└── profile_hard_mode.py                # End-to-end latency profiler
```

---

## Troubleshooting

**`OpenRouter error 401`** — `OPENROUTER_API_KEY` is unset or revoked. Re-source
your shell after editing `.env`.

**`Model tts-1 does not exist`** — a stale `config/dev.yaml` overriding
`audio.tts_model`. Remove the override; default is the OpenRouter Gemini TTS.

**`Address already in use` on `:8000`** — old backend still running.
`lsof -i :8000 -t | xargs kill -9`.

**No segments under `debug_ready_segments/`** — codegen failed all 3 attempts
for that segment. Check `run_metrics.json` for which stage errored.

---

## Authors

- **Lakshya Gupta** — [LinkedIn](https://www.linkedin.com/in/lakshyaadm/)
- **Anannya Popat** — [LinkedIn](https://www.linkedin.com/in/anannya-popat/)

GitHub Pages: https://chaosadmstudent.github.io/research-paper-graphviz/

## License

MIT.
