from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal, Dict, Any


class ConceptExplanation(BaseModel):
    """Explanation of a single concept from the KG."""
    model_config = ConfigDict(extra="forbid")
    
    concept_id: str = Field(..., description="ID of the concept from the KG")
    concept_name: str = Field(..., description="Name of the concept")
    concept_type: str = Field(..., description="Type: prerequisite, component, innovation, etc.")
    
    # Core explanation
    simple_explanation: str = Field(..., description="Simple, intuitive explanation (2-3 sentences) suitable for beginners")
    detailed_explanation: str = Field(..., description="Detailed technical explanation with context (4-5 sentences)")
    
    # Learning aids
    analogy: Optional[str] = Field(None, description="Real-world analogy to help understand the concept")
    example: Optional[str] = Field(None, description="Concrete example of the concept in action")
    why_it_matters: str = Field(..., description="Why this concept is important in the methodology")
    
    # Prerequisites and dependencies
    prerequisite_concept_ids: List[str] = Field(default_factory=list, description="Concept IDs that should be explained before this one")
    enables_concept_ids: List[str] = Field(default_factory=list, description="Concept IDs that this concept enables/leads to")
    
    # Metadata
    keywords: List[str] = Field(default_factory=list, description="Key terms associated with this concept")


class RelationshipExplanation(BaseModel):
    """Explanation of how and why concepts are connected."""
    model_config = ConfigDict(extra="forbid")
    
    relationship_id: str = Field(..., description="Unique ID for this relationship")
    source_concept_id: str = Field(..., description="Source concept ID from KG")
    target_concept_id: str = Field(..., description="Target concept ID from KG")
    relationship_type: str = Field(..., description="Type: flows_into, builds_upon, enables, composed_of, etc.")
    
    # Explanation
    transition_phrase: str = Field(..., description="Natural transition phrase (e.g., 'Building on this...', 'Now that we understand X...')")
    explanation: str = Field(..., description="How and why these concepts are related (3-4 sentences)")
    significance: str = Field(..., description="Why this relationship matters for understanding")
    data_or_logic_flow: str = Field(..., description="What flows/transforms between concepts")


class ConceptCluster(BaseModel):
    """Group of related concepts that should be explained together."""
    model_config = ConfigDict(extra="forbid")
    
    cluster_id: str = Field(..., description="Unique cluster identifier")
    cluster_name: str = Field(..., description="Name for this group of concepts")
    theme: str = Field(..., description="Common theme connecting these concepts")
    concept_ids: List[str] = Field(..., description="Ordered list of concept IDs in this cluster")
    explanation_order: List[str] = Field(..., description="Optimal order to explain concepts within cluster")
    cluster_summary: str = Field(..., description="Brief summary tying concepts together")


class SubSegment(BaseModel):
    """A sub-segment within a main segment for breaking down complex topics."""
    model_config = ConfigDict(extra="forbid")
    
    sub_segment_id: str = Field(..., description="Unique sub-segment identifier (e.g., 'seg_2_sub_1')")
    title: str = Field(..., description="Sub-segment title")
    order: int = Field(..., description="Order within parent segment (0-indexed)")
    
    # Narration for this sub-segment
    narration_script: str = Field(..., description="Narration for this specific sub-topic (natural, conversational)")
    
    # Concept coverage
    concepts_explained: List[str] = Field(default_factory=list, description="Concept IDs covered in this sub-segment")
    
    # Learning outcome
    key_point: str = Field(..., description="Main point of this sub-segment (1 sentence)")


class VideoSegment(BaseModel):
    """A video segment with narration transcript."""
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(..., description="Unique segment identifier (e.g., 'seg_1_intro')")
    title: str = Field(..., description="Segment title for reference")
    order: int = Field(..., description="Sequential order in video (0-indexed)")

    # Narration transcript
    narration_script: str = Field(..., description="Complete spoken narration for this segment (natural, conversational tone)")
    
    # Sub-segments (optional, for breaking down complex segments like prerequisites)
    sub_segments: Optional[List[SubSegment]] = Field(None, description="Optional sub-segments for organizing complex topics (e.g., multiple prerequisite concepts in Segment 2)")

    # Concept coverage
    concepts_explained: List[str] = Field(default_factory=list, description="Concept IDs covered in this segment")

    # Learning outcome
    key_message: str = Field(..., description="Core takeaway from this segment (1 sentence)")

    # Duration (calculated post-generation, not predicted by LLM)
    estimated_duration_seconds: Optional[int] = Field(None, description="Estimated duration in seconds (calculated post-generation)")


class ArchitecturalOverview(BaseModel):
    """High-level architectural summary for the conclusion."""
    model_config = ConfigDict(extra="forbid")
    
    overview_title: str = Field(..., description="Title for the overview")
    big_picture_explanation: str = Field(..., description="How all components work together (1 paragraph)")
    
    # Structure
    main_flow: List[str] = Field(..., description="High-level flow through the system (ordered component IDs)")
    parallel_pathways: Optional[List[str]] = Field(None, description="Parallel processing paths if applicable")
    feedback_loops: Optional[List[str]] = Field(None, description="Iterative/recurrent patterns if applicable")
    
    # Key insights
    design_philosophy: str = Field(..., description="Overall design philosophy (2-3 sentences)")
    key_innovations_recap: List[str] = Field(..., description="Brief recap of novel contributions")
    why_it_works: str = Field(..., description="Core reason this methodology is effective")


class SegmentOverview(BaseModel):
    """Brief overview of a video segment."""
    model_config = ConfigDict(extra="forbid")
    
    segment_id: str = Field(..., description="Segment identifier")
    title: str = Field(..., description="Segment title")
    focus: str = Field(..., description="What this segment focuses on")


class VideoNarrative(BaseModel):
    """Video structure with 4-6 main segments following a clear narrative arc."""
    model_config = ConfigDict(extra="forbid")
    
    narrative_strategy: Literal["problem_to_solution", "building_blocks", "guided_tour"] = Field(..., description="Overall narrative approach")
    total_segments: int = Field(..., description="Total number of video segments (typically 4-6)")
    
    # Segment descriptions
    segment_overview: List[SegmentOverview] = Field(..., description="Brief overview of each segment")


class SpeechTiming(BaseModel):
    """Timing information and estimation utilities."""
    model_config = ConfigDict(extra="forbid")
    
    words_per_minute: int = Field(150, description="Speaking rate for educational content")
    pause_per_sentence_seconds: float = Field(0.5, description="Pause time after sentences")
    visual_processing_seconds: int = Field(2, description="Time to process visual elements")
    transition_buffer_seconds: int = Field(1, description="Buffer time between segments")


class EducationalExplanation(BaseModel):
    """Complete educational video explanation with narration scripts."""
    model_config = ConfigDict(extra="forbid")
    
    # Video structure (4-6 segments typical)
    video_narrative: VideoNarrative = Field(..., description="Overall video narrative structure")
    video_segments: List[VideoSegment] = Field(..., description="Ordered video segments with narration scripts (4-6 segments)")


class TimingEstimator:
    """Helper class for estimating speech durations."""
    
    @staticmethod
    def estimate_speaking_duration(text: str, words_per_minute: int = 150) -> int:
        """
        Estimate speaking duration in seconds.
        
        Args:
            text: Text to be spoken
            words_per_minute: Speaking rate (150 wpm for educational content)
        
        Returns:
            Duration in seconds
        """
        word_count = len(text.split())
        base_duration = (word_count / words_per_minute) * 60
        
        # Add pause time for punctuation
        sentence_endings = text.count('.') + text.count('!') + text.count('?')
        pause_time = sentence_endings * 0.5
        
        return int(base_duration + pause_time)
    
    @staticmethod
    def add_visual_time(base_duration: int, has_figures: bool = False, 
                        has_tables: bool = False, figure_count: int = 0) -> int:
        """
        Add time for visual element processing.
        
        Args:
            base_duration: Base speaking duration
            has_figures: Whether segment includes figures
            has_tables: Whether segment includes tables
            figure_count: Number of figures shown
        
        Returns:
            Adjusted duration with visual processing time
        """
        additional_time = 0
        
        if has_figures:
            # 2 seconds per figure for visual processing
            additional_time += figure_count * 2
        
        if has_tables:
            # 3 seconds per table (more complex to read)
            additional_time += 3
        
        # Add 1 second transition buffer
        additional_time += 1
        
        return base_duration + additional_time
    
    @staticmethod
    def estimate_segment_duration(segment: VideoSegment, 
                                  timing_config: SpeechTiming) -> int:
        """
        Estimate total duration for a video segment.
        
        Args:
            segment: VideoSegment instance
            timing_config: SpeechTiming configuration
        
        Returns:
            Total estimated duration in seconds
        """
        # Base speaking duration from narration script
        base_duration = TimingEstimator.estimate_speaking_duration(
            segment.narration_script, 
            timing_config.words_per_minute
        )
        
        # Add visual processing time for each visual cue
        visual_count = len(segment.visual_cues)
        if visual_count > 0:
            base_duration += visual_count * timing_config.visual_processing_seconds
        
        # Add transition buffer
        base_duration += timing_config.transition_buffer_seconds
        
        return base_duration