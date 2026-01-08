from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal


class VisualReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    appears_in_figure: Optional[str] = Field(None, description="Figure ID or null")
    location_in_figure: Optional[str] = Field(None, description="Location description in figure")


class Prerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Concept or technique name")
    type: str = Field(..., description="Type of prerequisite (e.g., concept, technique, architecture, mathematical_foundation)")
    description: str = Field(..., description="Clear explanation (2-3 sentences)")
    why_needed: str = Field(..., description="How this relates to understanding the methodology")
    source: Literal["related_works", "introduction"]
    level: Literal["foundational", "intermediate", "advanced"]
    relationships_to_other_prereqs: List[str] = Field(default_factory=list)


class HighLevelComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Component name")
    type: str = Field(..., description="Type of component (e.g., encoder, decoder, module, network, layer, mechanism, process, algorithm)")
    description: str = Field(..., description="What this component does (3-4 sentences)")
    purpose: str = Field(..., description="Why this component exists")
    input: str = Field(..., description="High-level description of input")
    output: str = Field(..., description="High-level description of output")
    key_properties: List[str] = Field(default_factory=list)
    visual_reference: VisualReference = Field(default_factory=VisualReference)
    novel_contribution: bool = Field(..., description="Is this novel or standard?")


class HighLevelRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Unique identifier")
    source_id: str = Field(..., description="Source component/prerequisite ID")
    target_id: str = Field(..., description="Target component ID")
    relation_type: str = Field(..., description="Type of relationship (e.g., flows_into, builds_upon, extends, composed_of, parallel_to, prerequisite_for, feeds_into, replaces)")
    description: str = Field(..., description="Conceptual relationship (2-3 sentences)")
    data_transformation: str = Field(..., description="What changes between source and target")
    order: Optional[int] = Field(None, description="Sequential order in pipeline")
    is_novel: bool = Field(..., description="Is this relationship part of novel contribution?")


class PipelineStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_id: str = Field(..., description="Unique stage identifier")
    name: str = Field(..., description="Stage name")
    description: str = Field(..., description="What happens in this stage")
    components_involved: List[str] = Field(default_factory=list)
    relationships_involved: List[str] = Field(default_factory=list)
    order: int = Field(..., description="Sequential order")


class ParallelPathway(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pathway_name: str = Field(..., description="Name of parallel pathway")
    description: str = Field(..., description="What this pathway does")
    components: List[str] = Field(default_factory=list)


class FeedbackLoop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(..., description="Description of iterative/recurrent process")
    components: List[str] = Field(default_factory=list)


class ArchitectureOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paradigm: str = Field(..., description="e.g., encoder-decoder, autoregressive, diffusion")
    main_pipeline: List[PipelineStage] = Field(default_factory=list)
    parallel_pathways: Optional[List[ParallelPathway]] = Field(None, description="Optional: parallel processing pathways if architecture has multi-stream processing")
    feedback_loops: Optional[List[FeedbackLoop]] = Field(None, description="Optional: iterative/recurrent processes if architecture has feedback")


class KeyInnovation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    innovation_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Name of innovation")
    type: str = Field(..., description="Type of innovation (e.g., architectural, algorithmic, mathematical, training_procedure)")
    description: str = Field(..., description="What makes this novel (3-4 sentences)")
    comparison_to_baseline: str = Field(..., description="How this differs from standard")
    components_involved: List[str] = Field(default_factory=list)
    expected_benefit: str = Field(..., description="Why this improves performance/efficiency")


class DesignDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str = Field(..., description="Description of design choice")
    rationale: str = Field(..., description="Why this choice was made")
    alternatives_considered: List[str] = Field(default_factory=list)
    components_affected: List[str] = Field(default_factory=list)


class HighLevelSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    one_sentence_summary: str = Field(..., description="Ultra-concise description")
    paragraph_summary: str = Field(..., description="3-5 sentence explanation")
    conceptual_analogy: Optional[str] = Field(None, description="Analogy to help understand")
    key_insight: str = Field(..., description="Main 'aha' moment")


class PaperMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., description="Paper title")
    primary_contribution: str = Field(..., description="1-2 sentence summary")
    domain: str = Field(..., description="e.g., deep learning, computer vision, NLP")
    methodology_type: Optional[str] = Field(None, description="e.g., architecture, training_algorithm")


class HighLevelKnowledgeGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_metadata: PaperMetadata
    prerequisites: List[Prerequisite] = Field(default_factory=list)
    high_level_components: List[HighLevelComponent] = Field(default_factory=list)
    high_level_relationships: List[HighLevelRelationship] = Field(default_factory=list)
    architecture_overview: ArchitectureOverview
    key_innovations: List[KeyInnovation] = Field(default_factory=list)
    design_decisions: List[DesignDecision] = Field(default_factory=list)
    high_level_summary: HighLevelSummary


class TensorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Tensor name")
    shape: str = Field(..., description="Symbolic shape")
    dtype: Optional[str] = Field(None, description="Data type")
    description: str = Field(..., description="What this tensor represents")


class ParameterInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Parameter name")
    shape: str = Field(..., description="Parameter shape")
    initialization: str = Field(..., description="Initialization strategy")
    trainable: bool = Field(..., description="Is this trainable?")
    description: str = Field(..., description="Role of parameter")


class Hyperparameter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., description="Hyperparameter name")
    value: str = Field(..., description="Hyperparameter value (as string)")
    description: Optional[str] = Field(None, description="What this hyperparameter controls")


class AtomicOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Operation name")
    type: str = Field(..., description="Type of operation (e.g., linear, matmul, activation, normalization, elementwise, reduction, reshape, concatenation, split, attention, convolution, pooling, dropout, embedding)")
    description: str = Field(..., description="Precise description (2-3 sentences)")
    mathematical_formula: str = Field(..., description="LaTeX formula")
    input_tensors: List[TensorInfo] = Field(default_factory=list)
    output_tensors: List[TensorInfo] = Field(default_factory=list)
    parameters: List[ParameterInfo] = Field(default_factory=list)
    hyperparameters: List[Hyperparameter] = Field(default_factory=list, description="List of hyperparameters as key-value pairs")
    computational_complexity: Optional[str] = Field(None, description="Big-O complexity")
    numerical_stability_notes: Optional[str] = Field(None, description="Stability considerations")


class DataFlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: int = Field(..., description="Step number")
    operation_id: str = Field(..., description="Operation ID being executed")
    input_from: List[str] = Field(default_factory=list)
    output_to: List[str] = Field(default_factory=list)
    intermediate_result: str = Field(..., description="What exists after this step")
    tensor_shape_at_step: str = Field(..., description="Current tensor shape")
    notes: Optional[str] = Field(None, description="Important notes")


class CompositeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Multi-step operation name")
    description: str = Field(..., description="High-level description")
    atomic_operations_involved: List[str] = Field(default_factory=list)
    overall_formula: str = Field(..., description="Combined LaTeX formula")
    why_grouped: str = Field(..., description="Why these operations form a unit")


class TensorTransformation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_shape: str = Field(..., description="Initial tensor shape")
    to_shape: str = Field(..., description="Final tensor shape")
    transformation_type: str = Field(..., description="Type of transformation (e.g., reshape, transpose, permute, broadcast, squeeze, unsqueeze)")
    operations_involved: List[str] = Field(default_factory=list)
    purpose: str = Field(..., description="Why this transformation is needed")
    formula_or_code: str = Field(..., description="Exact transformation code")


class SpecialCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    condition: str = Field(..., description="What triggers this case")
    modified_operations: List[str] = Field(default_factory=list)
    description: str = Field(..., description="What changes")
    example: str = Field(..., description="Concrete example")


class ImplementationHint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(..., description="Topic like 'masking', 'memory_efficiency'")
    description: str = Field(..., description="Practical consideration")
    affected_operations: List[str] = Field(default_factory=list)
    code_snippet: Optional[str] = Field(None, description="Pseudocode or reference")


class VisualizationSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_or_step: str = Field(..., description="Operation ID or step number")
    visualization_type: str = Field(..., description="Type of visualization (e.g., tensor_flow, matrix_animation, attention_heatmap, dimension_transformation)")
    description: str = Field(..., description="What to animate and how")
    complexity_level: Literal["simple", "moderate", "complex"]
    priority: Literal["high", "medium", "low"]


class LowLevelKnowledgeGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component_id: str = Field(..., description="ID of component being decomposed")
    component_name: str = Field(..., description="Name of component")
    atomic_operations: List[AtomicOperation] = Field(default_factory=list)
    data_flow: List[DataFlowStep] = Field(default_factory=list)
    composite_operations: Optional[List[CompositeOperation]] = Field(None, description="Optional: grouped operations if component has multi-step patterns")
    tensor_transformations: Optional[List[TensorTransformation]] = Field(None, description="Optional: explicit reshape/transpose operations if applicable")
    special_cases: Optional[List[SpecialCase]] = Field(None, description="Optional: conditional behavior (training vs inference, masking, etc.)")
    implementation_hints: Optional[List[ImplementationHint]] = Field(None, description="Optional: practical implementation considerations")
    visualization_suggestions: Optional[List[VisualizationSuggestion]] = Field(None, description="Optional: animation recommendations")
