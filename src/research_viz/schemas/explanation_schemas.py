"""Explanation schemas for the pipeline.

Only contains the 3Blue1Brown-style schemas that are actively used.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


# =============================================================================
# Difficulty & Prerequisite Schemas
# =============================================================================

class PrerequisiteConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_name: str
    why_needed: str
    depth_level: int  # 0=paper concept, 1=direct prereq, 2=prereq-of-prereq
    parent_concept: Optional[str] = None
    estimated_explanation_time_seconds: int


class PrerequisiteTree(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_title: str
    root_concepts: List[str]
    prerequisites: List[PrerequisiteConcept]

# =============================================================================
# 3Blue1Brown-Style Schemas (Used by Pipeline)
# =============================================================================

class EquationExplanation(BaseModel):
    """A single equation with its intuitive meaning."""
    model_config = ConfigDict(extra="forbid")

    latex_formula: str = Field(..., description="LaTeX formula")
    what_it_means: str = Field(..., description="Plain English meaning of the formula")
    visualizable_aspect: str = Field(..., description="What part of this can be animated")
    example_values: Optional[str] = Field(None, description="Concrete numbers to illustrate")


class IntuitiveSection(BaseModel):
    """Intuitive breakdown - 3Blue1Brown style."""
    model_config = ConfigDict(extra="forbid")

    core_insight: str = Field(..., description="The 'aha!' moment in 1-2 sentences")
    visual_metaphor: str = Field(..., description="A visual/spatial way to think about this concept")
    metaphor_example: str = Field(..., description="Concrete example of the metaphor in action")
    starting_question: str = Field(..., description="The motivating question this concept answers")
    intuitive_walkthrough: str = Field(..., description="Step-by-step intuitive explanation without formulas")
    key_visuals: List[str] = Field(..., description="Things that should be animated/visualized")
    transformations_to_show: List[str] = Field(..., description="Changes/motions to animate")


class TechnicalSection(BaseModel):
    """Technical math breakdown - ties intuition to formulas."""
    model_config = ConfigDict(extra="forbid")

    intuition_to_math_bridge: str = Field(..., description="How the intuition maps to the math")
    key_equations: List[EquationExplanation] = Field(..., description="Each equation with intuitive meaning")
    shape_intuitions: List[str] = Field(..., description="What the tensor shapes mean conceptually")
    mathematical_insight: str = Field(..., description="The mathematical reason this approach works")


class Segment3B1B(BaseModel):
    """A video segment with intuition-first structure."""
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(..., description="Unique segment identifier")
    title: str = Field(..., description="Segment title")
    order: int = Field(..., description="Sequential order in video (0-indexed)")

    # TWO-PART STRUCTURE: Intuition THEN Technical
    intuition: IntuitiveSection = Field(..., description="Intuitive breakdown FIRST")
    technical: TechnicalSection = Field(..., description="Technical math SECOND")

    # Narration combining both parts
    narration_script: str = Field(..., description="Full narration weaving intuition and math")

    # Timing
    estimated_duration_seconds: Optional[int] = Field(None, description="Estimated duration (calculated post-generation)")


class EducationalExplanation3B1B(BaseModel):
    """Complete 3Blue1Brown-style educational explanation from PDF."""
    model_config = ConfigDict(extra="forbid")

    paper_title: str = Field(..., description="Title of the research paper")

    # Opening hook
    opening_question: str = Field(..., description="The big question this paper addresses")
    why_it_matters: str = Field(..., description="Why should the viewer care (1-2 sentences)")

    # Running example - MUST be consistent throughout
    running_example: str = Field(..., description="ONE concrete example used throughout all segments")

    # Video segments
    segments: List[Segment3B1B] = Field(..., description="Ordered video segments (4-6 typical)")

    # Difficulty metadata (optional, set by pipeline)
    difficulty_level: Optional[str] = Field(None, description="easy, medium, or hard")
    prerequisite_tree: Optional[dict] = Field(None, description="Prerequisite tree for easy mode")