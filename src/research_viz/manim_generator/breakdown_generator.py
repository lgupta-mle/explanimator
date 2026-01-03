"""
Converts the parsed research paper pdf into a scene description that has information about:
    - Entity relationships within methodology section
    - Intuitive step by step explanation of the methodology
"""

from typing import Dict, Any, Optional, List
import tyro
import os
import json
from research_viz.utils.llm_utils import create_llm_response
from research_viz.manim_generator.kg_schemas import (
    HighLevelKnowledgeGraph,
    LowLevelKnowledgeGraph
)


def extract_images_metadata(parsed_paper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract image metadata with captions from parsed paper.

    Args:
        parsed_paper: Dictionary containing parsed paper data

    Returns:
        List of dictionaries with keys: 'path', 'caption', 'figure_number'
    """
    images_metadata = []

    if "figures" not in parsed_paper or "items" not in parsed_paper["figures"]:
        print("No images in paper directory!")
        return None

    for figure in parsed_paper["figures"]["items"]:
        # Only include figures that have actual image files
        if not figure.get("has_image_file", False):
            continue

        # Get the saved image path
        image_path = figure.get("saved_as")
        if not image_path or not os.path.exists(image_path):
            print(f"Image not found at {image_path}")
            continue

        images_metadata.append({
            "path": image_path,
            "caption": figure.get("caption", ""),
            "figure_number": figure.get("figure_number", "")
        })

    return images_metadata

def create_high_level_methodology_kg(
    parsed_paper: Dict[str, Any],
    model_name: str = "openai/gpt-5"
) -> Optional[HighLevelKnowledgeGraph]:
    """
    Creates a knowledge graph for the methodology section of the parsed paper.
    Uses the parsed paper's methodology and introduction section along with images to build a high level conceptual knowledge graph.

    Args:
        parsed_paper: Dictionary containing parsed paper data with figures metadata
        model_name: Model to use for generation

    Returns:
        HighLevelKnowledgeGraph instance or None if generation fails
    """
    system_prompt = open(os.path.join(os.path.dirname(__file__), "prompts", "high_kg_prompt.txt")).read()
    prepared_usr_prompt = json.dumps(parsed_paper, indent=4)

    # Extract images with captions
    images_metadata = extract_images_metadata(parsed_paper)

    response = create_llm_response(
        prepared_usr_prompt,
        system_prompt,
        model_name=model_name,
        schema=HighLevelKnowledgeGraph,
        images_metadata=images_metadata
    )

    if response is not None:
        # Save the response to a file
        os.makedirs(os.path.join(os.path.dirname(__file__), "output"), exist_ok=True)
        with open(os.path.join(os.path.dirname(__file__), "output", "high_level_methodology_kg.json"), "w") as f:
            f.write(response.model_dump_json(indent=2))

    return response

def create_low_level_methodology_kg(
    parsed_paper: Dict[str, Any],
    high_level_kg: HighLevelKnowledgeGraph,
    component_id: str,
    model_name: str = "openai/gpt-5"
) -> Optional[LowLevelKnowledgeGraph]:
    """
    Creates a low-level atomic knowledge graph for a specific component from the high-level KG.
    Uses the parsed paper's methodology section along with images to build atomic-level details.

    Args:
        parsed_paper: Dictionary containing parsed paper data with figures metadata
        high_level_kg: Previously generated high-level knowledge graph
        component_id: ID of the component to decompose from high_level_kg
        model_name: Model to use for generation

    Returns:
        LowLevelKnowledgeGraph instance or None if generation fails
    """
    system_prompt = open(os.path.join(os.path.dirname(__file__), "prompts", "low_kg_prompt.txt")).read()

    # Find the component in high_level_kg
    component = next(
        (c for c in high_level_kg.high_level_components if c.id == component_id),
        None
    )

    if component is None:
        raise ValueError(f"Component with id '{component_id}' not found in high-level KG")

    # Prepare input for low-level KG generation
    low_level_input = {
        "high_level_component": {
            "id": component.id,
            "name": component.name,
            "description": component.description
        },
        "methodology_text": parsed_paper.get("methodology", ""),
        "equations": [],  # Could extract from parsed_paper if available
        "visual_hints": component.visual_reference.location_in_figure if component.visual_reference else ""
    }

    prepared_usr_prompt = json.dumps(low_level_input, indent=4)

    # Extract images with captions
    images_metadata = extract_images_metadata(parsed_paper)

    response = create_llm_response(
        prepared_usr_prompt,
        system_prompt,
        model_name=model_name,
        schema=LowLevelKnowledgeGraph,
        images_metadata=images_metadata
    )

    if response is not None:
        # Save the response to a file
        os.makedirs(os.path.join(os.path.dirname(__file__), "output"), exist_ok=True)
        with open(os.path.join(os.path.dirname(__file__), "output", f"low_level_kg_{component_id}.json"), "w") as f:
            f.write(response.model_dump_json(indent=2))

    return response


def generate_methodology_breakdown(
    high_level_methodology_kg: HighLevelKnowledgeGraph,
    low_level_methodology_kgs: Dict[str, LowLevelKnowledgeGraph],
    parsed_paper: Dict[str, Any],
    model_name: str = "openai/gpt-5"
) -> dict:
    """
    Generate an intuitive step by step breakdown of the methodology section of the parsed paper using the knowledge graph as additional context.

    Args:
        high_level_methodology_kg: High-level architectural knowledge graph
        low_level_methodology_kgs: Dictionary mapping component_id to low-level KG
        parsed_paper: Original parsed paper data
        model_name: Model to use for generation

    Returns:
        Dictionary containing the methodology breakdown
    """
    pass


def main(model_name: str = "openai/gpt-5", paper_name: str = "attention_is_all_you_need"):
    """
    Main function to generate knowledge graphs from a parsed paper.

    Args:
        model_name: Model to use (default: openai/gpt-5)
    """
    # Read parsed paper output from ./output_grobid_marker/
    base_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..')
    parsed_paper = json.load(open(os.path.join(base_dir, "output_grobid_marker", paper_name, f"{paper_name}_extraction_results.json")))

    # Add images_dir to parsed_paper
    parsed_paper["images_dir"] = os.path.join(base_dir, "output_grobid_marker", paper_name, "images")

    # Generate high-level knowledge graph
    high_level_kg = create_high_level_methodology_kg(parsed_paper, model_name)

    if high_level_kg is None:
        print("Failed to generate high-level knowledge graph")
        return

    # Generate low-level knowledge graphs for novel components
    low_level_kgs = {}
    for component in high_level_kg.high_level_components:
        if component.novel_contribution:
            print(f"Generating low-level KG for component: {component.name}")
            low_kg = create_low_level_methodology_kg(
                parsed_paper,
                high_level_kg,
                component.id,
                model_name
            )
            if low_kg is not None:
                low_level_kgs[component.id] = low_kg

    # Generate methodology breakdown
    methodology_breakdown = generate_methodology_breakdown(
        high_level_kg,
        low_level_kgs,
        parsed_paper,
        model_name
    )

    print(f"Generated KGs for {len(low_level_kgs)} components")

if __name__ == "__main__":
    tyro.cli(main)