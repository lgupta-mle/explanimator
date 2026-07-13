# Book-to-Video Pipeline

Converts book chapters into 3Blue1Brown-style animated educational videos.

## How It Works

1. **Chapter Detection** — Extracts the table of contents from the PDF (embedded metadata or LLM-parsed) and identifies chapter boundaries. Automatically distinguishes Parts/grouping dividers from actual content chapters.

2. **Series Bible** — Generates a consistency document (running example, notation glossary, visual style) shared across all chapter videos so they feel like a coherent series.

3. **Explanation Generation** — For each chapter, an LLM reads the chapter PDF and creates a structured educational explanation with intuition, technical content, and narration script.

4. **Video Rendering** — Generates Manim animation code from the explanation, TTS audio from the narration, and renders the final video with audio-video synchronization.

## Usage

```bash
python -m research_viz.book_generator.book_pipeline \
  --book-pdf "resources/MyBook.pdf" \
  --chapters "1" \
  --difficulty medium
```

### Key Options

| Flag | Description | Default |
|------|-------------|---------|
| `--book-pdf` | Path to book PDF | Required |
| `--chapters` | Comma-separated chapter numbers, or `"0"` for all | `"1"` |
| `--difficulty` | `easy`, `medium`, or `hard` | `medium` |
| `--parallel` | Process chapters concurrently | `true` |
| `--skip-bible` | Skip bible generation, load from disk | `false` |
| `--output-dir` | Root directory for all output | `output/books` |

### Difficulty Levels

| Level | Segments | Words/Segment | Audience |
|-------|----------|---------------|----------|
| easy | 10-14 | 350-600 | Beginners, includes prerequisites |
| medium | 4-6 | 150-300 | Intermediate |
| hard | 2-3 | 80-180 | PhD-level, concise |

## Output Structure

```
output/books/<book_title>/
├── series_bible.json          # Shared consistency document
├── pipeline_summary.json      # Run results
├── ch_01_part_1/
│   ├── chapter.pdf            # Extracted chapter pages (for verification)
│   ├── explanation.json       # Generated explanation
│   ├── audio_beats/           # TTS audio files + beat timeline
│   └── final_video.mp4        # Rendered video
└── ch_02_part_1/
    └── ...
```

The `chapter.pdf` in each output directory contains the exact pages extracted from the book for that chapter — open it to verify the correct content is being animated.

## Chapter Detection

The pipeline detects chapters using two strategies:

1. **Embedded PDF TOC** (preferred) — uses PyMuPDF's `get_toc()`. Automatically detects whether the TOC uses Parts > Chapters > Sections hierarchy or just Chapters > Sections, without relying on naming conventions.

2. **LLM-based TOC extraction** — if no embedded TOC exists, the pipeline finds the "Contents" page heuristically, sends those pages to an LLM, and parses the structured result.

Both strategies filter out front matter (Preface, Foreword), back matter (References, Index, Glossary), exercise sections, and Part divider pages.

### Supported Book Formats

- Chapters called "Chapter", "Part", "Unit", "Lecture", "Module", or unnumbered
- Arabic or Roman numeral chapter numbering
- Books with Part groupings (Part I, Part II) wrapping chapters
- TOC titled "Contents", "Table of Contents", "Index", "Topics", "Chapters", or "Outline"

## Requirements

- `OPENROUTER_API_KEY` — LLM calls (explanation generation, TOC extraction,
  judging, Manim codegen) and Gemini TTS audio generation (default provider)
- `OPENAI_API_KEY` — Manim RAG lookups (used during code-fix retries in
  Manim codegen); also needed if you switch `audio.provider` back to
  `openai` in `config.yaml`. See the root [README](../../../README.md) for
  the one-time `build_manim_index` setup step this key unlocks.
- `manim` — animation rendering (requires a working LaTeX install for
  `MathTex`/`Tex` — see root README Prerequisites)
- `ffmpeg` — video/audio processing
