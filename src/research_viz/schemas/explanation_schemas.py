"""Explanation schemas for the pipeline.

Only contains the 3Blue1Brown-style schemas that are actively used.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict


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


# =============================================================================
# Book Pipeline Schemas
# =============================================================================

class BookSection(BaseModel):
    """A section within a chapter (e.g., 1.1, 1.2)."""
    model_config = ConfigDict(extra="allow")

    section_id: str = Field(..., description="Section identifier, e.g. '3.2'")
    title: str = Field(..., description="Section title")
    start_page: int = Field(..., description="0-indexed start page in the book PDF")
    end_page: int = Field(..., description="0-indexed end page (inclusive)")
    token_count: int = Field(0, description="Approximate token count for this section")


class BookChapter(BaseModel):
    """A chapter extracted from a book PDF."""
    model_config = ConfigDict(extra="allow")

    chapter_id: str = Field(..., description="Chapter identifier, e.g. 'ch_03'")
    title: str = Field(..., description="Chapter title")
    chapter_number: int = Field(..., description="Chapter number (1-indexed)")
    start_page: int = Field(..., description="0-indexed start page in the book PDF")
    end_page: int = Field(..., description="0-indexed end page (inclusive)")
    sections: List[BookSection] = Field(default_factory=list, description="Sections within this chapter")
    token_count: int = Field(0, description="Approximate token count for the full chapter")


class BookChapterPart(BaseModel):
    """A sub-chunk of a chapter when the chapter exceeds the token budget."""
    model_config = ConfigDict(extra="allow")

    part_id: str = Field(..., description="e.g. 'ch_03_part_1'")
    chapter_id: str = Field(..., description="Parent chapter id")
    part_number: int = Field(..., description="1-indexed part number within the chapter")
    title: str = Field(..., description="Display title, e.g. 'Chapter 3, Part 1: Backpropagation'")
    start_page: int
    end_page: int
    sections: List[BookSection] = Field(default_factory=list)
    token_count: int = Field(0)


class SeriesBible(BaseModel):
    """Shared context generated once for the whole book to enforce consistency across chapter videos."""
    model_config = ConfigDict(extra="allow")

    book_title: str = Field(..., description="Title of the book")
    series_running_example: str = Field(
        ...,
        description="ONE concrete example used throughout ALL chapter videos (e.g., 'training a 2-layer net to classify handwritten digits')"
    )
    notation_glossary: Dict[str, str] = Field(
        default_factory=dict,
        description="Established symbol-to-meaning mapping (e.g. {'W': 'weight matrix', 'L': 'loss function'})"
    )
    visual_style_notes: str = Field(
        "",
        description="Brief notes on visual style, color palette, or animation conventions to maintain consistency"
    )
    chapter_briefs: Dict[str, str] = Field(
        default_factory=dict,
        description="chapter_id → one-sentence description of what that chapter covers"
    )