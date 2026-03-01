"""Difficulty configuration for explanation generation."""

from dataclasses import dataclass


@dataclass
class DifficultyConfig:
    level: str
    min_segments: int
    max_segments: int
    min_narration_words: int
    max_narration_words: int
    prerequisite_depth: int
    beat_min_words: int
    beat_max_words: int
    include_prerequisite_segments: bool


DIFFICULTY_CONFIGS = {
    "easy": DifficultyConfig(
        level="easy",
        min_segments=10,
        max_segments=14,
        min_narration_words=350,
        max_narration_words=600,
        prerequisite_depth=3,
        beat_min_words=10,
        beat_max_words=30,
        include_prerequisite_segments=True,
    ),
    "medium": DifficultyConfig(
        level="medium",
        min_segments=4,
        max_segments=6,
        min_narration_words=150,
        max_narration_words=300,
        prerequisite_depth=1,
        beat_min_words=8,
        beat_max_words=25,
        include_prerequisite_segments=False,
    ),
    "hard": DifficultyConfig(
        level="hard",
        min_segments=2,
        max_segments=3,
        min_narration_words=80,
        max_narration_words=180,
        prerequisite_depth=0,
        beat_min_words=6,
        beat_max_words=20,
        include_prerequisite_segments=False,
    ),
}
