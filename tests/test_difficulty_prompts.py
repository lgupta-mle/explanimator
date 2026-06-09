"""Tests for difficulty-aware prompt building in pdf_explanation_generator."""

from research_viz.config.difficulty import DIFFICULTY_CONFIGS
from research_viz.manim_generator.pdf_explanation_generator import (
    _build_difficulty_prompt_section,
    _build_difficulty_judge_section,
)


def test_easy_prompt_includes_segment_range():
    config = DIFFICULTY_CONFIGS["easy"]
    prompt = _build_difficulty_prompt_section(config)
    assert "10-14" in prompt
    assert "350-600" in prompt
    assert "EASY" in prompt


def test_easy_prompt_with_prereq_tree():
    config = DIFFICULTY_CONFIGS["easy"]
    tree = {
        "prerequisites": [
            {"concept_name": "Chain Rule"},
            {"concept_name": "Matrix Multiplication"},
        ]
    }
    prompt = _build_difficulty_prompt_section(config, tree)
    assert "Chain Rule" in prompt
    assert "Matrix Multiplication" in prompt
    assert "MANDATORY" in prompt


def test_medium_prompt_is_empty():
    config = DIFFICULTY_CONFIGS["medium"]
    prompt = _build_difficulty_prompt_section(config)
    assert prompt == ""


def test_hard_prompt_includes_constraints():
    config = DIFFICULTY_CONFIGS["hard"]
    prompt = _build_difficulty_prompt_section(config)
    assert "2-3" in prompt
    assert "80-180" in prompt
    assert "PhD-level" in prompt


def test_easy_judge_includes_prerequisite_criterion():
    config = DIFFICULTY_CONFIGS["easy"]
    section = _build_difficulty_judge_section(config)
    assert "prerequisite_coverage" in section


def test_hard_judge_notes_expert_mode():
    config = DIFFICULTY_CONFIGS["hard"]
    section = _build_difficulty_judge_section(config)
    assert "expert-level" in section
    assert "Do NOT penalize" in section


def test_medium_judge_is_empty():
    config = DIFFICULTY_CONFIGS["medium"]
    section = _build_difficulty_judge_section(config)
    assert section == ""
