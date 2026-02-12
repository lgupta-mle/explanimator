"""
Generates educational video explanations with narration scripts from Knowledge Graphs.

This script automatically uses the output from breakdown_generator as input.
API keys should be set in your .env file:
- OPENAI_API_KEY for OpenAI models
- OPENROUTER_API_KEY for OpenRouter models
"""

from typing import Dict, Any, Optional
import tyro
import os
import json
from research_viz.utils.llm_utils import create_llm_response
from research_viz.schemas.explanation_schemas import (
    EducationalExplanation,
    TimingEstimator,
    SpeechTiming
)
from dotenv import load_dotenv

load_dotenv()

def create_educational_explanation(
    kg_json_path: str,
    model_name: str = "openai/gpt-5"
) -> Optional[EducationalExplanation]:
    """
    Creates educational explanation with narration scripts from a Knowledge Graph.
    
    Args:
        kg_json_path: Path to the high-level KG JSON file
        model_name: Model to use for generation
    
    Returns:
        EducationalExplanation instance or None if generation fails
    """
    # Load the prompt
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "explanation_prompt.txt")
    system_prompt = open(prompt_path).read()
    
    # Load the KG JSON
    with open(kg_json_path, 'r') as f:
        kg_data = json.load(f)
    
    # Prepare user prompt with KG data
    user_prompt = json.dumps(kg_data, indent=2)
    
    print(f"Generating educational explanation from: {kg_json_path}")
    print(f"Using model: {model_name}")
    
    # Generate explanation
    response = create_llm_response(
        user_prompt,
        system_prompt,
        model_name=model_name,
        schema=EducationalExplanation,
        images_metadata=None  # No images needed for text generation
    )
    
    if response is not None:
        # Add timing estimates using the helper
        response = add_duration_estimates(response)
        
        # Save the response
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, "educational_explanation.json")
        with open(output_path, "w") as f:
            f.write(response.model_dump_json(indent=2))
        
        print(f"\nSuccess! Explanation generated.")
        print(f"Saved to: {output_path}")
        print(f"\nSummary:")
        print(f"   - Total segments: {len(response.video_segments)}")
        print(f"   - Narrative strategy: {response.video_narrative.narrative_strategy}")
        
        # Print segment info
        print(f"\nVideo Segments:")
        for seg in response.video_segments:
            duration = getattr(seg, 'estimated_duration_seconds', 0)
            script_words = len(seg.narration_script.split())
            print(f"   {seg.order + 1}. {seg.title}")
            print(f"      - Words: {script_words}")
            print(f"      - Duration: {duration}s (~{duration//60}m {duration%60}s)")
            print(f"      - Key message: {seg.key_message}")
        
        total_duration = sum(
            getattr(seg, 'estimated_duration_seconds', 0) 
            for seg in response.video_segments
        )
        print(f"\nTotal estimated video duration: {total_duration}s (~{total_duration//60}m {total_duration%60}s)")
    
    return response


def add_duration_estimates(explanation: EducationalExplanation) -> EducationalExplanation:
    """
    Add estimated durations to video segments after generation.
    
    Args:
        explanation: Generated explanation without durations
    
    Returns:
        Explanation with duration estimates added
    """
    config = SpeechTiming()
    
    # Add duration to each segment
    for segment in explanation.video_segments:
        duration = TimingEstimator.estimate_speaking_duration(
            segment.narration_script,
            config.words_per_minute
        )
        # Add transition buffer
        duration += config.transition_buffer_seconds
        # Store as attribute (will be added to model)
        segment.estimated_duration_seconds = duration
    
    return explanation


def main(
    kg_json_path: Optional[str] = None,
    model_name: str = "openai/gpt-5"
):
    """
    Generate educational explanation from Knowledge Graph.
    
    Args:
        kg_json_path: Path to the high-level methodology KG JSON file 
                     (default: uses output from breakdown_generator)
        model_name: LLM model to use (default: openai/gpt-5)
    
    Examples:
        # Use default path (output from breakdown_generator)
        python -m research_viz.manim_generator.explanation_generator
        
        # Or specify custom path
        python -m research_viz.manim_generator.explanation_generator \
            --kg-json-path ./path/to/custom_kg.json
    """
    # Default to breakdown_generator output if not specified
    if kg_json_path is None:
        kg_json_path = os.path.join(
            os.path.dirname(__file__), 
            "output", 
            "high_level_methodology_kg.json"
        )
        print(f"Using default KG path: {kg_json_path}")
    
    if not os.path.exists(kg_json_path):
        print(f"Error: KG file not found: {kg_json_path}")
        print(f"\nPlease run breakdown_generator first to generate the KG:")
        print(f"  python -m research_viz.manim_generator.breakdown_generator --pdf-dir ./papers")
        return
    
    create_educational_explanation(kg_json_path, model_name)


if __name__ == "__main__":
    tyro.cli(main)
