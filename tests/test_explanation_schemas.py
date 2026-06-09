"""Tests for explanation schemas including new difficulty/prerequisite models."""

import pytest
from pydantic import ValidationError
from research_viz.schemas.explanation_schemas import (
    PrerequisiteConcept,
    PrerequisiteTree,
    EducationalExplanation3B1B,
    Segment3B1B,
    IntuitiveSection,
    TechnicalSection,
    EquationExplanation,
)


def test_prerequisite_concept():
    pc = PrerequisiteConcept(
        concept_name="Chain Rule",
        why_needed="Required for understanding backpropagation",
        depth_level=2,
        parent_concept="Backpropagation",
        estimated_explanation_time_seconds=60,
    )
    assert pc.concept_name == "Chain Rule"
    assert pc.depth_level == 2
    assert pc.parent_concept == "Backpropagation"


def test_prerequisite_concept_optional_parent():
    pc = PrerequisiteConcept(
        concept_name="Linear Algebra",
        why_needed="Foundation for matrix ops",
        depth_level=3,
        estimated_explanation_time_seconds=120,
    )
    assert pc.parent_concept is None


def test_prerequisite_tree():
    tree = PrerequisiteTree(
        paper_title="Attention Is All You Need",
        root_concepts=["Self-Attention", "Transformer"],
        prerequisites=[
            PrerequisiteConcept(
                concept_name="Matrix Multiplication",
                why_needed="Core of attention computation",
                depth_level=1,
                estimated_explanation_time_seconds=90,
            )
        ],
    )
    assert tree.paper_title == "Attention Is All You Need"
    assert len(tree.prerequisites) == 1


def _make_segment(order=0):
    return Segment3B1B(
        segment_id="seg_01",
        title="Test Segment",
        order=order,
        intuition=IntuitiveSection(
            core_insight="Test insight",
            visual_metaphor="Test metaphor",
            metaphor_example="Test example",
            starting_question="Why?",
            intuitive_walkthrough="Step by step",
            key_visuals=["visual1"],
            transformations_to_show=["transform1"],
        ),
        technical=TechnicalSection(
            intuition_to_math_bridge="Bridge",
            key_equations=[
                EquationExplanation(
                    latex_formula="E=mc^2",
                    what_it_means="Energy equals mass times speed of light squared",
                    visualizable_aspect="Growing energy bar",
                )
            ],
            shape_intuitions=["shape1"],
            mathematical_insight="Insight",
        ),
        narration_script="This is a test narration script.",
    )


def test_educational_explanation_with_difficulty_fields():
    explanation = EducationalExplanation3B1B(
        paper_title="Test Paper",
        opening_question="What is this?",
        why_it_matters="Because reasons",
        running_example="Example X",
        segments=[_make_segment()],
        difficulty_level="easy",
        prerequisite_tree={"paper_title": "Test", "root_concepts": [], "prerequisites": []},
    )
    assert explanation.difficulty_level == "easy"
    assert explanation.prerequisite_tree is not None


def test_educational_explanation_without_difficulty_fields():
    explanation = EducationalExplanation3B1B(
        paper_title="Test Paper",
        opening_question="What is this?",
        why_it_matters="Because reasons",
        running_example="Example X",
        segments=[_make_segment()],
    )
    assert explanation.difficulty_level is None
    assert explanation.prerequisite_tree is None


def test_schema_rejects_extra_fields():
    """EducationalExplanation3B1B uses extra='forbid' and should reject unknown fields."""
    with pytest.raises(ValidationError):
        EducationalExplanation3B1B(
            paper_title="Test",
            opening_question="Q",
            why_it_matters="M",
            running_example="E",
            segments=[_make_segment()],
            unknown_field="should fail",
        )


def test_prerequisite_tree_rejects_extra_fields():
    with pytest.raises(ValidationError):
        PrerequisiteTree(
            paper_title="Test",
            root_concepts=[],
            prerequisites=[],
            extra_field="should fail",
        )
