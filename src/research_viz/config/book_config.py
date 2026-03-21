"""Configuration for the book-to-video pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BookConfig:
    max_tokens_per_chunk: int = 60_000
    parallel_chapters: bool = True
    max_workers: int = 4
    token_count_method: str = "approx"  # "approx" uses len(text)/4
    output_subdir_name: Optional[str] = None  # defaults to book title slug
    skip_exercises: bool = True  # exclude exercise/bibliographical sections from animation
