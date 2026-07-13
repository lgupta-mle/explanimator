"""
Book Pipeline Orchestrator: end-to-end book PDF → per-chapter Manim videos.

Phase 1: Generate series bible (one cheap LLM call over TOC + snippets)
Phase 2: For each chapter (or chapter part if oversized):
           a. Extract sub-PDF
           b. Generate explanation (with bible injection + rolling context)
           c. Run full existing Manim pipeline (audio → code → video)

All outputs are saved under: output_dir/<book_slug>/
  series_bible.json
  ch_01/
    explanation.json
    audio_beats/
    scenes/
    final_video.mp4
  ch_02/
    ...
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from research_viz.config.book_config import BookConfig
from research_viz.config.difficulty import DifficultyConfig, DIFFICULTY_CONFIGS
from research_viz.schemas.explanation_schemas import SeriesBible, BookChapterPart
from research_viz.book_generator.book_decomposer import (
    extract_chapters,
    extract_sub_pdf,
    split_chapter_if_needed,
)
from research_viz.book_generator.series_bible_generator import generate_series_bible
from research_viz.book_generator.book_chapter_explainer import (
    generate_chapter_explanation,
    extract_narration_tail,
    bible_fingerprint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str, fallback: str = "book") -> str:
    """Convert a title to a safe directory name."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    text = text.strip("_")[:60]
    return text if text else fallback


def _load_existing_bible(output_dir: Path) -> Optional[SeriesBible]:
    bible_path = output_dir / "series_bible.json"
    if bible_path.exists():
        try:
            with open(bible_path) as f:
                data = json.load(f)
            return SeriesBible(**data)
        except Exception as e:
            print(f"  Warning: failed to load existing bible: {e}")
    return None


def _save_bible(bible: SeriesBible, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bible_path = output_dir / "series_bible.json"
    with open(bible_path, "w") as f:
        json.dump(bible.model_dump(), f, indent=2)
    print(f"  Series bible saved to: {bible_path}")


# ---------------------------------------------------------------------------
# Per-chapter video generation (explanation + Manim pipeline)
# ---------------------------------------------------------------------------

def _run_chapter_video(
    part: BookChapterPart,
    book_pdf_path: str,
    chapter_output_dir: Path,
    bible: SeriesBible,
    model_name: str,
    difficulty_config: Optional[DifficultyConfig],
    prev_narration: Optional[str],
    chroma_path: str,
    max_retries: int,
    extraction_model: str = "google/gemini-2.5-flash",
    skip_video: bool = False,
    max_judge_attempts: int = 6,
    codegen_model: Optional[str] = None,
) -> Optional[dict]:
    """Run the full pipeline for a single chapter part. Returns the explanation dict or None."""
    part_dir = chapter_output_dir / part.part_id
    part_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: Extract sub-PDF ---
    sub_pdf_path = str(part_dir / "chapter.pdf")
    if not Path(sub_pdf_path).exists():
        print(f"\n  [{part.part_id}] Extracting pages {part.start_page}–{part.end_page}...")
        extract_sub_pdf(book_pdf_path, part.start_page, part.end_page, sub_pdf_path)
    else:
        print(f"\n  [{part.part_id}] Using cached sub-PDF: {sub_pdf_path}")

    # --- Step 2: Generate explanation ---
    explanation_path = str(part_dir / "explanation.json")
    current_fp = bible_fingerprint(bible)
    explanation = None
    if Path(explanation_path).exists():
        with open(explanation_path) as f:
            cached = json.load(f)
        if cached.get("_bible_fingerprint", "") == current_fp:
            print(f"  [{part.part_id}] Loading cached explanation (bible fingerprint matches)")
            explanation = cached
        else:
            print(f"  [{part.part_id}] Stale explanation cache (bible changed) — regenerating")

    if explanation is None:
        explanation = generate_chapter_explanation(
            chapter_pdf_path=sub_pdf_path,
            chapter_title=part.title,
            chapter_id=part.chapter_id,
            output_path=explanation_path,
            bible=bible,
            model_name=model_name,
            extraction_model=extraction_model,
            max_judge_attempts=max_judge_attempts,
            difficulty_config=difficulty_config,
            prev_chapter_narration=prev_narration,
        )

    if explanation is None:
        print(f"  [{part.part_id}] Explanation generation failed — skipping video")
        return None

    # --- Step 3: Full Manim pipeline (audio → code → video) ---
    if skip_video:
        print(f"  [{part.part_id}] --skip-video set — skipping Manim pipeline")
        return explanation

    print(f"\n  [{part.part_id}] Running Manim video pipeline...")
    try:
        from research_viz.manim_generator.pdf_to_manim_pipeline import main as manim_main
        difficulty_name = difficulty_config.level if difficulty_config else "medium"
        manim_main(
            pdf_path=None,
            explanation_path=explanation_path,
            output_dir=str(part_dir),
            # NOTE: manim_main's `model_name` is the code-gen model (used for Manim
            # scene generation), not the explanation model — pass codegen_model here
            # so it can be tuned independently of the explanation/judge model above.
            model_name=codegen_model,
            max_retries=max_retries,
            generate_audio=True,
            render_video=True,
            difficulty=difficulty_name,
        )
        print(f"  [{part.part_id}] Manim pipeline complete")
    except Exception as e:
        print(f"  [{part.part_id}] Manim pipeline error: {e}")

    return explanation


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_book_pipeline(
    book_pdf_path: str,
    output_base_dir: str = "output/books",
    model_name: str = "google/gemini-2.5-pro",
    extraction_model: Optional[str] = None,
    difficulty: str = "medium",
    book_config: Optional[BookConfig] = None,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db",
    max_retries: int = 3,
    skip_bible: bool = False,
    skip_video: bool = False,
    chapters_to_process: Optional[List[int]] = None,
    max_judge_attempts: int = 6,
    codegen_model: Optional[str] = None,
) -> dict:
    """
    Run the full book-to-video pipeline.

    Args:
        book_pdf_path: Path to the book PDF.
        output_base_dir: Root directory for all book outputs.
        model_name: LLM model for explanation + bible generation.
        difficulty: "easy", "medium", or "hard".
        book_config: BookConfig instance (uses defaults if None).
        chroma_path: Path to the Manim RAG vector DB.
        max_retries: Max Manim code retries per scene.
        skip_bible: If True, skip bible generation and load from disk if available.
        chapters_to_process: List of chapter numbers (1-indexed) to process.
                             Defaults to [1] (chapter 1 only). Pass None to process ALL chapters.
        max_judge_attempts: Max attempts to pass the chapter explanation quality check.
        codegen_model: LLM model for Manim scene code generation. Defaults (None) to the
                       difficulty tier's code_gen_model from config.yaml.

    Returns:
        A summary dict with paths to all generated videos.
    """
    if book_config is None:
        book_config = BookConfig()

    effective_extraction_model = extraction_model or book_config.extraction_model

    difficulty_config = DIFFICULTY_CONFIGS.get(difficulty)
    if not difficulty_config:
        raise ValueError(f"Unknown difficulty '{difficulty}'. Choose from: {list(DIFFICULTY_CONFIGS.keys())}")

    book_pdf_path = str(Path(book_pdf_path).resolve())
    print(f"\n{'='*60}")
    print(f"BOOK PIPELINE")
    print(f"  PDF:        {book_pdf_path}")
    print(f"  Model:      {model_name}")
    print(f"  Extraction: {effective_extraction_model}")
    print(f"  Difficulty: {difficulty}")
    print(f"{'='*60}")

    # --- Phase 1: Decompose book ---
    print("\n[Phase 1] Extracting chapter structure...")
    chapters = extract_chapters(book_pdf_path, model_name=model_name, book_config=book_config)
    print(f"  Found {len(chapters)} chapters")
    for ch in chapters:
        print(f"    {ch.chapter_id}: {ch.title} (pp.{ch.start_page+1}–{ch.end_page+1}, ~{ch.token_count:,} tokens)")

    # Filter chapters — default is chapter 1 only
    if chapters_to_process is None:
        chapters_to_process = [1]
    if chapters_to_process != []:
        chapters = [ch for ch in chapters if ch.chapter_number in chapters_to_process]
        print(f"  Processing {len(chapters)} selected chapter(s): {[ch.chapter_number for ch in chapters]}")

    # Split oversized chapters into parts
    all_parts: List[BookChapterPart] = []
    for ch in chapters:
        parts = split_chapter_if_needed(ch, book_config)
        if len(parts) > 1:
            print(f"  {ch.chapter_id} split into {len(parts)} parts ({ch.token_count:,} tokens > {book_config.max_tokens_per_chunk:,} limit)")
        all_parts.extend(parts)

    print(f"  Total processing units: {len(all_parts)}")

    # --- Determine output directory ---
    # Stable directory based on the PDF filename — never renamed after the fact, so the
    # bible/explanation/segment caches persist across every rerun of the same book instead
    # of silently regenerating (and invalidating everything downstream) each time.
    output_dir = Path(output_base_dir) / _slugify(Path(book_pdf_path).stem, fallback="book")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  Output directory: {output_dir}")

    # --- Phase 1b: Generate (or load) series bible ---
    bible = None
    if not skip_bible:
        existing = _load_existing_bible(output_dir)
        if existing:
            print("\n[Phase 1b] Loaded existing series bible from disk")
            bible = existing
        else:
            print("\n[Phase 1b] Generating series bible...")
            toc_cache = str(Path(book_pdf_path).with_suffix(".toc.json"))
            bible = generate_series_bible(
                book_pdf_path, model_name=model_name,
                snippet_pages=book_config.bible_snippet_pages,
                toc_cache_path=toc_cache,
            )
            if bible:
                _save_bible(bible, output_dir)
    else:
        bible = _load_existing_bible(output_dir)

    if bible is None:
        print("  WARNING: No series bible available — proceeding without consistency enforcement")
        bible = SeriesBible(
            book_title=Path(book_pdf_path).stem,
            series_running_example="a concrete worked example relevant to each chapter",
            notation_glossary={},
            visual_style_notes="Dark background, 3Blue1Brown style",
            chapter_briefs={},
        )

    # --- Phase 2: Per-chapter video generation ---
    print(f"\n[Phase 2] Generating videos for {len(all_parts)} chapter unit(s)...")
    print(f"  Parallel: {book_config.parallel_chapters} (max_workers={book_config.max_workers})")

    results = {}
    # Sequential rolling context — parts processed in order to carry narration forward
    prev_narration: Optional[str] = None

    if book_config.parallel_chapters and len(all_parts) > 1:
        # Parallel: independent chapters run concurrently; rolling context is unavailable
        print("  NOTE: Parallel mode — chapters will NOT have rolling context from previous chapters.")
        print("        Use --parallel false for sequential mode with continuity between chapters.")
        with ThreadPoolExecutor(max_workers=book_config.max_workers) as executor:
            futures = {
                executor.submit(
                    _run_chapter_video,
                    part,
                    book_pdf_path,
                    output_dir,
                    bible,
                    model_name,
                    difficulty_config,
                    None,  # no rolling context in parallel mode
                    chroma_path,
                    max_retries,
                    effective_extraction_model,
                    skip_video,
                    max_judge_attempts,
                    codegen_model,
                ): part
                for part in all_parts
            }
            for future in as_completed(futures):
                part = futures[future]
                try:
                    explanation = future.result()
                    video_path = output_dir / part.part_id / "final_video.mp4"
                    results[part.part_id] = {
                        "title": part.title,
                        "status": "success" if explanation else "failed",
                        "video_path": str(video_path) if video_path.exists() else None,
                        "explanation_path": str(output_dir / part.part_id / "explanation.json"),
                    }
                except Exception as e:
                    print(f"  [{part.part_id}] Unhandled exception: {e}")
                    results[part.part_id] = {"title": part.title, "status": "error", "error": str(e)}
    else:
        # Sequential: propagate rolling context
        for part in all_parts:
            explanation = _run_chapter_video(
                part=part,
                book_pdf_path=book_pdf_path,
                chapter_output_dir=output_dir,
                bible=bible,
                model_name=model_name,
                difficulty_config=difficulty_config,
                prev_narration=prev_narration,
                chroma_path=chroma_path,
                max_retries=max_retries,
                extraction_model=effective_extraction_model,
                skip_video=skip_video,
                max_judge_attempts=max_judge_attempts,
                codegen_model=codegen_model,
            )
            video_path = output_dir / part.part_id / "final_video.mp4"
            results[part.part_id] = {
                "title": part.title,
                "status": "success" if explanation else "failed",
                "video_path": str(video_path) if video_path.exists() else None,
                "explanation_path": str(output_dir / part.part_id / "explanation.json"),
            }
            if explanation:
                prev_narration = extract_narration_tail(explanation)

    # --- Summary ---
    successful = [p for p, r in results.items() if r["status"] == "success"]
    failed = [p for p, r in results.items() if r["status"] != "success"]

    summary = {
        "book_title": bible.book_title,
        "output_dir": str(output_dir),
        "total_chapters": len(all_parts),
        "successful": len(successful),
        "failed": len(failed),
        "results": results,
    }

    summary_path = output_dir / "pipeline_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"BOOK PIPELINE COMPLETE")
    print(f"  Book:       {bible.book_title}")
    print(f"  Output:     {output_dir}")
    print(f"  Successful: {len(successful)}/{len(all_parts)}")
    if failed:
        print(f"  Failed:     {failed}")
    print(f"  Summary:    {summary_path}")
    print(f"{'='*60}")

    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tyro
    from dataclasses import dataclass

    @dataclass
    class BookPipelineCLIArgs:
        book_pdf: str
        """Path to the book PDF."""
        output_dir: str = "output/books"
        """Root directory for all output."""
        model: str = "google/gemini-2.5-pro"
        """LLM model for explanation generation (Stage 2)."""
        extraction_model: str = "google/gemini-2.5-flash"
        """Cheap model for chapter digest extraction (Stage 1)."""
        difficulty: str = "medium"
        """Difficulty: easy, medium, or hard."""
        chroma_path: str = "data/manim_docs/vector_db/chroma_db"
        """Path to Manim RAG vector DB."""
        max_retries: int = 3
        """Max Manim code retries per scene."""
        max_judge_attempts: int = 6
        """Max attempts to pass the chapter explanation quality check."""
        codegen_model: str = "google/gemini-3.1-pro-preview"
        """LLM model for Manim scene code generation (video generation)."""
        skip_bible: bool = False
        """Skip bible generation (load from disk if available)."""
        skip_video: bool = False
        """Stop after explanation generation — skip Manim video rendering."""
        parallel: bool = True
        """Process chapters in parallel."""
        max_workers: int = 4
        """Max parallel workers."""
        chapters: str = "1"
        """Comma-separated list of chapter numbers to process (e.g. '1,2,5'). Default: chapter 1 only. Use '0' to process all."""

    args = tyro.cli(BookPipelineCLIArgs)

    if args.chapters == "0":
        chapters_list = None  # None with updated logic means all
        # Override: pass empty list sentinel to skip filtering
        chapters_list = []
    else:
        chapters_list = [int(c.strip()) for c in args.chapters.split(",") if c.strip()]

    config = BookConfig(
        max_tokens_per_chunk=50000,
        parallel_chapters=args.parallel,
        max_workers=args.max_workers,
        extraction_model=args.extraction_model,
    )

    run_book_pipeline(
        book_pdf_path=args.book_pdf,
        output_base_dir=args.output_dir,
        model_name=args.model,
        extraction_model=args.extraction_model,
        difficulty=args.difficulty,
        book_config=config,
        chroma_path=args.chroma_path,
        max_retries=args.max_retries,
        skip_bible=args.skip_bible,
        skip_video=args.skip_video,
        chapters_to_process=chapters_list,
        max_judge_attempts=args.max_judge_attempts,
        codegen_model=args.codegen_model,
    )
