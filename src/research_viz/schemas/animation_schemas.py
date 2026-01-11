from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class PropertyValue(BaseModel):
    """Key-value pair for flexible properties."""
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., description="Property name")
    value: str = Field(..., description="Property value (as string)")


class ShapeSpec(BaseModel):
    """Specification for a visual shape/object to create."""
    model_config = ConfigDict(extra="forbid")

    shape_id: str = Field(..., description="Unique identifier for this shape")
    shape_type: str = Field(..., description="Type of shape (e.g., circle, rectangle, arrow, text, equation, matrix, graph, line, dot, box)")

    position: Optional[str] = Field(None, description="Position on screen (e.g., center, left, top_right, above_previous)")
    color: Optional[str] = Field(None, description="Color name or description")
    scale: float = Field(1.0, description="Scale factor")

    content: Optional[str] = Field(None, description="Text content or LaTeX formula")

    represents: str = Field(..., description="What this shape represents conceptually")
    from_kg_component: Optional[str] = Field(None, description="Component ID from KG this relates to")

    properties: Optional[List[PropertyValue]] = Field(None, description="Additional shape-specific properties as key-value pairs")

class AnimationTransform(BaseModel):
    """Specification for an animation/transformation."""
    model_config = ConfigDict(extra="forbid")

    animation_id: str = Field(..., description="Unique identifier")
    animation_type: str = Field(..., description="Type of animation (e.g., create, write, fade_in, fade_out, transform, move_to, scale, rotate, highlight, indicate, morph)")

    target_shape_ids: List[str] = Field(..., description="Shape IDs this animation affects")

    duration: float = Field(1.0, description="Animation duration in seconds")
    start_time_offset: float = Field(0.0, description="Offset from scene start in seconds")
    sync_with_narration: Optional[str] = Field(None, description="Narration phrase this should sync with")

    target_properties: List[PropertyValue] = Field(default_factory=list, description="Target properties for transform as key-value pairs")
    description: str = Field(..., description="What this animation accomplishes")


class MathAnimation(BaseModel):
    """Specialized animation for mathematical operations."""
    model_config = ConfigDict(extra="forbid")

    math_id: str = Field(..., description="Unique identifier")
    operation_type: str = Field(..., description="Type of mathematical operation (e.g., matrix_multiply, dot_product, elementwise, reshape, transpose, concatenate, attention_compute, softmax)")

    input_formulas: List[str] = Field(..., description="LaTeX formulas for inputs")
    output_formula: str = Field(..., description="LaTeX formula for output")

    from_kg_operation: Optional[str] = Field(None, description="Operation ID from low-level KG")
    tensor_shapes: List[PropertyValue] = Field(default_factory=list, description="Tensor shapes as key-value pairs (tensor name → shape string)")

    visualization_style: str = Field(..., description="How to visualize this operation (e.g., step_by_step, simultaneous, highlight_flow, heatmap)")
    show_intermediate_steps: bool = Field(True, description="Whether to show intermediate calculations")

    duration: float = Field(2.0, description="Total duration for this math animation")
    narration_anchor: str = Field(..., description="Narration phrase this anchors to")

    description: str = Field(..., description="High-level description of this math operation")


class AnimationScene(BaseModel):
    """A logical animation scene within a segment."""
    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(..., description="Unique scene identifier")
    scene_purpose: str = Field(..., description="High-level purpose of this scene")

    narration_snippet: str = Field(..., description="The specific portion of narration this scene covers")
    start_time: float = Field(..., description="Start time within segment (seconds)")
    duration: float = Field(..., description="Scene duration (seconds)")

    shapes: List[ShapeSpec] = Field(default_factory=list, description="Shapes to create for this scene")
    animations: List[AnimationTransform] = Field(default_factory=list, description="General animations")
    math_animations: List[MathAnimation] = Field(default_factory=list, description="Mathematical animations if applicable")

    concepts_visualized: List[str] = Field(default_factory=list, description="Concept IDs being visualized")
    kg_operations_shown: List[str] = Field(default_factory=list, description="Operation IDs from low-level KG")

    layout_strategy: str = Field("centered", description="Overall layout approach for this scene (e.g., centered, split_screen, sequential, grid, flow_diagram)")


class SegmentAnimationPlan(BaseModel):
    """Complete animation plan for one video segment."""
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(..., description="Matches segment_id from EducationalExplanation")
    segment_title: str = Field(..., description="Segment title for reference")

    full_narration: str = Field(..., description="Complete narration script for this segment")
    estimated_duration: int = Field(..., description="Total segment duration in seconds")

    scenes: List[AnimationScene] = Field(..., description="Ordered scenes for this segment")

    component_ids_visualized: List[str] = Field(default_factory=list, description="Component IDs from high-level KG")
    low_level_kg_sources: List[str] = Field(default_factory=list, description="Low-level KG file names used")

    color_scheme: List[PropertyValue] = Field(default_factory=list, description="Color mappings for concepts as key-value pairs (concept → color)")
    recurring_elements: List[str] = Field(default_factory=list, description="Shape IDs that persist across scenes")


class AnimationRequirements(BaseModel):
    """Complete animation requirements for all video segments."""
    model_config = ConfigDict(extra="forbid")

    paper_title: str = Field(..., description="Paper title from educational explanation")
    total_segments: int = Field(..., description="Number of video segments")

    segment_plans: List[SegmentAnimationPlan] = Field(..., description="Animation plan for each segment")

    global_color_scheme: List[PropertyValue] = Field(
        default_factory=list,
        description="Global color mappings as key-value pairs"
    )
    global_style: List[PropertyValue] = Field(
        default_factory=list,
        description="Global style settings as key-value pairs"
    )

    kg_files_used: List[str] = Field(default_factory=list, description="All low-level KG files referenced")
