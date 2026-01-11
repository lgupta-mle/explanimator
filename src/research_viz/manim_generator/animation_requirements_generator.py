"""
Generates precise animation requirements from educational explanations and knowledge graphs.

This script uses the output from explanation_generator as input.
API keys should be set in your .env file:
- OPENAI_API_KEY for OpenAI models
- OPENROUTER_API_KEY for OpenRouter models
"""

from typing import Dict, Any, Optional, List
import tyro
import os
import json
import glob
import re
from tqdm import tqdm
from research_viz.utils.llm_utils import create_llm_response
from research_viz.schemas.animation_schemas import (
    AnimationRequirements,
    SegmentAnimationPlan,
)
from research_viz.schemas.explanation_schemas import (
    EducationalExplanation,
    VideoSegment,
)
from dotenv import load_dotenv

load_dotenv()


def load_low_level_kgs(output_dir: str) -> Dict[str, Dict[str, Any]]:
    """
    Load all low-level KG JSON files from output directory.

    Args:
        output_dir: Path to output directory containing KG files

    Returns:
        Dictionary mapping component_id to parsed JSON data
    """
    kg_pattern = os.path.join(output_dir, "low_level_kg_comp_*.json")
    kg_files = glob.glob(kg_pattern)

    low_level_kgs = {}

    for kg_file in kg_files:
        filename = os.path.basename(kg_file)
        match = re.match(r"low_level_kg_(comp_\w+)\.json", filename)

        if match:
            component_id = match.group(1)

            with open(kg_file, 'r') as f:
                kg_data = json.load(f)
                low_level_kgs[component_id] = kg_data

    return low_level_kgs


def match_kgs_to_segment(
    segment: VideoSegment,
    low_level_kgs: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Find relevant KG data for a segment based on concepts_explained.

    Args:
        segment: VideoSegment from educational explanation
        low_level_kgs: All available low-level KGs

    Returns:
        Dictionary with matched KG data:
        {
            "matched_components": [component_ids],
            "kg_data": {component_id: kg_json},
            "formulas": [extracted LaTeX formulas],
            "visualization_hints": [suggestions]
        }
    """
    matched_components = []
    kg_data = {}
    formulas = []
    visualization_hints = []

    for concept_id in segment.concepts_explained:
        if concept_id.startswith("comp_"):
            if concept_id in low_level_kgs:
                matched_components.append(concept_id)
                kg_data[concept_id] = low_level_kgs[concept_id]

                kg_component = low_level_kgs[concept_id]

                if "atomic_operations" in kg_component:
                    for op in kg_component["atomic_operations"]:
                        if "mathematical_formula" in op and op["mathematical_formula"]:
                            formulas.append(op["mathematical_formula"])

                if "visualization_suggestions" in kg_component and kg_component["visualization_suggestions"]:
                    visualization_hints.extend(kg_component["visualization_suggestions"])

    return {
        "matched_components": matched_components,
        "kg_data": kg_data,
        "formulas": formulas,
        "visualization_hints": visualization_hints
    }


def parse_narration_into_phrases(
    narration_script: str,
    total_duration: int
) -> List[Dict[str, Any]]:
    """
    Split narration into timed phrases.

    Args:
        narration_script: Full narration text
        total_duration: Total segment duration in seconds

    Returns:
        List of dictionaries:
        [
            {
                "text": "sentence text",
                "start_time": 0.0,
                "duration": 3.5,
                "word_count": 25
            },
            ...
        ]
    """
    sentences = re.split(r'[.!?]+', narration_script)
    sentences = [s.strip() for s in sentences if s.strip()]

    phrases = []
    cumulative_time = 0.0
    words_per_minute = 150

    for sentence in sentences:
        word_count = len(sentence.split())
        duration = (word_count / words_per_minute) * 60

        phrases.append({
            "text": sentence,
            "start_time": cumulative_time,
            "duration": round(duration, 1),
            "word_count": word_count
        })

        cumulative_time += duration

    return phrases


def create_segment_animation_plan(
    segment: VideoSegment,
    matched_kg_data: Dict[str, Any],
    narration_phrases: List[Dict[str, Any]],
    model_name: str,
    prompt_path: str
) -> Optional[SegmentAnimationPlan]:
    """
    Generate animation plan for one segment using LLM.

    Args:
        segment: VideoSegment from educational explanation
        matched_kg_data: Matched KG data for this segment
        narration_phrases: Parsed narration phrases with timing
        model_name: Model to use for generation
        prompt_path: Path to the prompt file

    Returns:
        SegmentAnimationPlan instance or None if generation fails
    """
    with open(prompt_path, 'r') as f:
        system_prompt = f.read()

    user_prompt_data = {
        "segment": {
            "segment_id": segment.segment_id,
            "title": segment.title,
            "narration": segment.narration_script,
            "duration_seconds": segment.estimated_duration_seconds,
            "concepts": segment.concepts_explained
        },
        "kg_data": matched_kg_data,
        "narration_phrases": narration_phrases
    }

    user_prompt = json.dumps(user_prompt_data, indent=2)

    response = create_llm_response(
        user_prompt,
        system_prompt,
        model_name=model_name,
        schema=SegmentAnimationPlan,
        images_metadata=None
    )

    return response


def create_animation_requirements(
    explanation_path: str,
    kg_dir: str,
    model_name: str = "openai/gpt-5"
) -> Optional[AnimationRequirements]:
    """
    Generate complete animation requirements from educational explanation and KGs.

    Args:
        explanation_path: Path to educational_explanation.json
        kg_dir: Directory containing low_level_kg_comp_*.json files
        model_name: Model to use for generation

    Returns:
        AnimationRequirements instance or None if generation fails
    """
    with open(explanation_path, 'r') as f:
        explanation_data = json.load(f)

    low_level_kgs = load_low_level_kgs(kg_dir)

    prompt_path = os.path.join(
        os.path.dirname(__file__),
        "prompts",
        "animation_requirements_prompt.txt"
    )

    segment_plans = []
    for segment_data in tqdm(explanation_data["video_segments"], desc="Generating segment plans", total=len(explanation_data["video_segments"])):
        segment = VideoSegment.model_validate(segment_data)

        matched_kg = match_kgs_to_segment(segment, low_level_kgs)

        phrases = parse_narration_into_phrases(
            segment.narration_script,
            segment.estimated_duration_seconds or 60
        )

        plan = create_segment_animation_plan(
            segment, matched_kg, phrases, model_name, prompt_path
        )

        if plan:
            segment_plans.append(plan)

    if not segment_plans:
        return None

    requirements = AnimationRequirements(
        paper_title=explanation_data.get("paper_title", "Unknown"),
        total_segments=len(segment_plans),
        segment_plans=segment_plans,
        kg_files_used=list(low_level_kgs.keys())
    )

    output_path = os.path.join(kg_dir, "animation_requirements.json")
    with open(output_path, "w") as f:
        f.write(requirements.model_dump_json(indent=2))

    return requirements


def main(
    explanation_path: Optional[str] = None,
    kg_dir: Optional[str] = None,
    model_name: str = "openai/gpt-5"
):
    """
    Generate animation requirements from educational explanation and KGs.

    Args:
        explanation_path: Path to educational_explanation.json
                         (default: output/educational_explanation.json)
        kg_dir: Directory with low-level KGs
               (default: output/)
        model_name: LLM model to use (default: openai/gpt-5)

    Examples:
        python -m research_viz.manim_generator.animation_requirements_generator
    """
    if explanation_path is None:
        explanation_path = os.path.join(
            os.path.dirname(__file__),
            "output",
            "educational_explanation.json"
        )

    if kg_dir is None:
        kg_dir = os.path.join(os.path.dirname(__file__), "output")

    if not os.path.exists(explanation_path):
        print(f"Error: {explanation_path} not found")
        return

    requirements = create_animation_requirements(
        explanation_path, kg_dir, model_name
    )

    if requirements:
        print(f"Success! Generated {len(requirements.segment_plans)} segment plans")
        print(f"Saved to: {os.path.join(kg_dir, 'animation_requirements.json')}")


if __name__ == "__main__":
    tyro.cli(main)
