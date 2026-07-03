"""Configuration for the book-to-video pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BookConfig:
    max_tokens_per_chunk: int = 53355
    parallel_chapters: bool = True
    max_workers: int = 4
    token_count_method: str = "approx"  # "approx" uses len(text)/4
    output_subdir_name: Optional[str] = None  # defaults to book title slug
    skip_exercises: bool = True  # exclude exercise sections from animation
    debug_chapter_detection: bool = False  # print detailed scoring during title-based chapter search
    bible_snippet_pages: int = 4  # pages per chapter sampled for series bible generation
    extraction_model: str = "google/gemini-2.5-flash"  # Stage 1 model for chapter digest extraction
