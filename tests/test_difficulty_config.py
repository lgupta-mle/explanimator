"""Tests for difficulty configuration module."""

from research_viz.config.difficulty import DifficultyConfig, DIFFICULTY_CONFIGS


def test_all_difficulty_levels_exist():
    assert set(DIFFICULTY_CONFIGS.keys()) == {"easy", "medium", "hard"}


def test_difficulty_config_fields():
    for level, config in DIFFICULTY_CONFIGS.items():
        assert isinstance(config, DifficultyConfig)
        assert config.level == level
        assert config.min_segments > 0
        assert config.max_segments >= config.min_segments
        assert config.min_narration_words > 0
        assert config.max_narration_words >= config.min_narration_words
        assert config.beat_min_words > 0
        assert config.beat_max_words >= config.beat_min_words


def test_easy_has_prerequisites():
    assert DIFFICULTY_CONFIGS["easy"].include_prerequisite_segments is True
    assert DIFFICULTY_CONFIGS["easy"].prerequisite_depth == 3


def test_medium_is_default_range():
    config = DIFFICULTY_CONFIGS["medium"]
    assert config.min_segments == 4
    assert config.max_segments == 6
    assert config.include_prerequisite_segments is False


def test_hard_is_concise():
    config = DIFFICULTY_CONFIGS["hard"]
    assert config.min_segments == 2
    assert config.max_segments == 3
    assert config.prerequisite_depth == 0
    assert config.include_prerequisite_segments is False


def test_segment_ranges_dont_overlap():
    easy = DIFFICULTY_CONFIGS["easy"]
    medium = DIFFICULTY_CONFIGS["medium"]
    hard = DIFFICULTY_CONFIGS["hard"]
    assert hard.max_segments <= medium.min_segments
    assert medium.max_segments <= easy.min_segments
