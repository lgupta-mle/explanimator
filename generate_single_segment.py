"""
Generate Manim code for a single segment with improved validation.
"""

import json
from pathlib import Path
from research_viz.schemas.animation_schemas import AnimationRequirements
from research_viz.preprocessing.manim_db import ManimDocRetriever
from research_viz.manim_generator.manim_code_generator import ManimCodeGenerator

# Configuration
SEGMENT_INDEX = 0  # 0 = first segment (Introduction & Problem)
REQUIREMENTS_PATH = "src/research_viz/manim_generator/output/animation_requirements.json"
OUTPUT_PATH = "src/research_viz/manim_generator/output/generated_segment_1.py"
CHROMA_PATH = "data/manim_docs/vector_db/chroma_db"

print(f"\n{'='*80}")
print("GENERATING CODE FOR SINGLE SEGMENT")
print(f"{'='*80}\n")

# Load requirements
print(f"Loading animation requirements from: {REQUIREMENTS_PATH}")
with open(REQUIREMENTS_PATH, 'r') as f:
    requirements_data = json.load(f)

requirements = AnimationRequirements.model_validate(requirements_data)

# Get the specified segment
segment = requirements.segment_plans[SEGMENT_INDEX]

print(f"\nSegment: {segment.segment_title}")
print(f"Scenes: {len(segment.scenes)}")
print(f"Duration: {segment.estimated_duration}s\n")

# Initialize RAG retriever
print("Initializing RAG retriever...")
retriever = ManimDocRetriever(chroma_path=CHROMA_PATH)

# Initialize code generator with validation enabled
print("Initializing code generator with validation...")
print("  - Max retries: 3")
print("  - Validation: Enabled")
print("  - RAG context: 10K tokens\n")

generator = ManimCodeGenerator(
    retriever=retriever,
    model_name="openai/gpt-5",
    context_token_budget=10000,
    max_retries=3,
    enable_validation=True
)

print(f"{'='*80}")
print(f"GENERATING CODE")
print(f"{'='*80}\n")

# Generate code for the segment
segment_code = generator.generate_segment_code(segment)

print(f"\n{'='*80}")
print("ASSEMBLING FILE")
print(f"{'='*80}\n")

# Create complete file
file_parts = []

# Header
file_parts.append(f'''"""
Generated Manim Animation Code - Segment 1

Paper: {requirements.paper_title}
Segment: {segment.segment_title}
Scenes: {len(segment_code.scenes)}

To render a specific scene:
    cd src/research_viz/manim_generator/output
    manim -pql generated_segment_1.py <SceneClassName>

To render all scenes:
    manim -pql generated_segment_1.py -a
"""

from manim import *
import numpy as np

''')

# Add segment header
file_parts.append(f"\n{'#'*80}\n")
file_parts.append(f"# SEGMENT: {segment.segment_id}\n")
file_parts.append(f"# {segment.segment_title}\n")
file_parts.append(f"{'#'*80}\n\n")

# Add all scene codes
for scene in segment_code.scenes:
    file_parts.append(f"# Scene: {scene.scene_id}\n")
    file_parts.append(scene.code)
    file_parts.append("\n\n")

# Write to file
complete_code = "".join(file_parts)
Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(complete_code)

print(f"Code saved to: {OUTPUT_PATH}")
print(f"Total scenes: {len(segment_code.scenes)}")
print(f"File size: {len(complete_code)} characters")

# Final validation
print(f"\n{'='*80}")
print("FINAL VALIDATION")
print(f"{'='*80}\n")

from research_viz.manim_generator.manim_code_validator import ManimCodeValidator
validator = ManimCodeValidator(enable_runtime_validation=True)

is_valid, errors = validator.validate(complete_code)

if is_valid:
    print("SUCCESS: All code passed validation!")
else:
    print(f"WARNING: {len(errors)} validation errors found:")
    for i, error in enumerate(errors[:10], 1):
        print(f"  {i}. {error}")

print(f"\n{'='*80}")
print("GENERATION COMPLETE")
print(f"{'='*80}\n")

print(f"Scene classes generated:")
for scene in segment_code.scenes:
    print(f"  - {scene.class_name}")

print(f"\nTo render:")
print(f"  cd src/research_viz/manim_generator/output")
print(f"  manim -pql generated_segment_1.py {segment_code.scenes[0].class_name}")
print()
