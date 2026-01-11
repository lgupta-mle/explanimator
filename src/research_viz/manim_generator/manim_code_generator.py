"""
Generate executable Manim code from animation requirements using RAG.

This script loads animation requirements and generates Python code that implements
all scenes with proper Manim classes, guided by retrieved documentation examples.
"""

from typing import List, Optional
import tyro
import os
import json
from pathlib import Path
from research_viz.utils.llm_utils import create_llm_response
from research_viz.schemas.animation_schemas import (
    AnimationRequirements,
    AnimationScene,
    SegmentAnimationPlan
)
from research_viz.preprocessing.manim_db import ManimDocRetriever
from research_viz.manim_generator.manim_code_validator import ManimCodeValidator
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class ManimSceneCode(BaseModel):
    """Generated code for a single Manim scene."""
    scene_id: str = Field(..., description="Scene identifier from specification")
    class_name: str = Field(..., description="PascalCase class name for the scene")
    imports: List[str] = Field(..., description="Required imports")
    code: str = Field(..., description="Complete Scene class code")


class ManimSegmentCode(BaseModel):
    """Generated code for all scenes in a segment."""
    segment_id: str
    scenes: List[ManimSceneCode]
    shared_helpers: Optional[str] = None


class GeneratedManimCode(BaseModel):
    """Complete Manim code for all segments."""
    file_header: str
    segments: List[ManimSegmentCode]
    complete_code: str


class ManimCodeGenerator:
    """Generate Manim code using RAG-enhanced LLM."""

    def __init__(
        self,
        retriever: ManimDocRetriever,
        model_name: str = "openai/gpt-5",
        context_token_budget: int = 10000,
        max_retries: int = 3,
        enable_validation: bool = True
    ):
        """
        Args:
            retriever: ManimDocRetriever for RAG
            model_name: LLM model to use
            context_token_budget: Max tokens for RAG context
            max_retries: Maximum attempts to fix validation errors
            enable_validation: Enable runtime validation and retry loop
        """
        self.retriever = retriever
        self.model_name = model_name
        self.context_token_budget = context_token_budget
        self.max_retries = max_retries
        self.enable_validation = enable_validation
        # Enable both Python validation AND actual Manim rendering validation
        self.validator = ManimCodeValidator(
            enable_runtime_validation=enable_validation,
            enable_manim_rendering=enable_validation  # Actually run manim render to validate
        )

    def generate_scene_code(
        self,
        scene: AnimationScene,
        segment_context: str
    ) -> Optional[ManimSceneCode]:
        """
        Generate code for a single animation scene with validation and retry.

        Process:
        1. Retrieve relevant Manim docs via RAG
        2. Assemble context within token budget
        3. Build prompt with scene spec + RAG context
        4. LLM generates code
        5. Validate code (syntax + runtime checks)
        6. If errors, retry with error feedback (up to max_retries)
        7. Return structured output
        """
        print(f"  Generating code for: {scene.scene_id}")

        # Step 1: Retrieve documentation
        retrieval_results = self.retriever.retrieve_for_scene(
            scene,
            top_k=20,
            rerank_top_k=10
        )

        # Step 2: Assemble context
        rag_context = self.retriever.assemble_context(
            retrieval_results,
            max_tokens=self.context_token_budget
        )

        # Step 3: Build prompt
        system_prompt = self._load_system_prompt()
        user_prompt = self._build_user_prompt(scene, segment_context, rag_context)

        # Step 4: Iterative generation with validation
        previous_code = None
        previous_errors = None

        for attempt in range(self.max_retries):
            try:
                # If this is a retry, add error feedback to prompt
                if attempt > 0 and previous_errors:
                    error_feedback = self._build_error_feedback_prompt(
                        previous_code,
                        previous_errors,
                        attempt
                    )
                    current_user_prompt = f"{user_prompt}\n\n{error_feedback}"
                    print(f"    Retry {attempt}/{self.max_retries-1} - Fixing {len(previous_errors)} errors")
                else:
                    current_user_prompt = user_prompt

                # Generate code
                response = create_llm_response(
                    current_user_prompt,
                    system_prompt,
                    model_name=self.model_name,
                    schema=ManimSceneCode
                )

                # Step 5: Validate if enabled
                if self.enable_validation and response:
                    full_code = self._assemble_full_code([response])
                    is_valid, errors = self.validator.validate(full_code)

                    if is_valid:
                        if attempt > 0:
                            print(f"    ✓ Fixed! Code validated successfully")
                        return response
                    else:
                        # Validation failed - prepare for retry
                        previous_code = response.code
                        previous_errors = errors

                        if attempt == self.max_retries - 1:
                            # Last attempt failed
                            print(f"    ✗ Validation failed after {self.max_retries} attempts:")
                            for error in errors[:5]:  # Show first 5 errors
                                print(f"      - {error}")
                            print(f"    Proceeding with code despite errors...")
                            return response
                        # Continue to next retry
                        continue
                else:
                    # Validation disabled or no response
                    return response

            except Exception as e:
                print(f"    Error generating code (attempt {attempt+1}): {e}")
                if attempt == self.max_retries - 1:
                    return None

        return None

    def generate_segment_code(
        self,
        segment_plan: SegmentAnimationPlan
    ) -> ManimSegmentCode:
        """Generate code for all scenes in a segment."""
        print(f"\nSegment: {segment_plan.segment_title}")

        segment_context = f"""
Segment Title: {segment_plan.segment_title}
Full Narration: {segment_plan.full_narration[:500]}...
Duration: {segment_plan.estimated_duration} seconds
"""

        scene_codes = []
        for scene in segment_plan.scenes:
            scene_code = self.generate_scene_code(scene, segment_context)
            if scene_code:
                scene_codes.append(scene_code)
            else:
                print(f"    WARNING: Failed to generate code for {scene.scene_id}")

        return ManimSegmentCode(
            segment_id=segment_plan.segment_id,
            scenes=scene_codes
        )

    def generate_complete_code(
        self,
        requirements: AnimationRequirements
    ) -> GeneratedManimCode:
        """Generate complete Manim code for all segments."""
        print(f"\n{'='*80}")
        print(f"GENERATING MANIM CODE")
        print(f"Paper: {requirements.paper_title}")
        print(f"Total Segments: {requirements.total_segments}")
        print(f"{'='*80}")

        segment_codes = []
        for segment_plan in requirements.segment_plans:
            segment_code = self.generate_segment_code(segment_plan)
            segment_codes.append(segment_code)

        # Assemble into complete file
        complete_code = self._assemble_complete_code(segment_codes, requirements)

        return GeneratedManimCode(
            file_header=self._generate_file_header(requirements),
            segments=segment_codes,
            complete_code=complete_code
        )

    def _load_system_prompt(self) -> str:
        """Load system prompt for code generation."""
        prompt_path = Path(__file__).parent / "prompts" / "manim_code_generation_prompt.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _build_user_prompt(
        self,
        scene: AnimationScene,
        segment_context: str,
        rag_context: str
    ) -> str:
        """Build user prompt with scene spec and RAG context."""
        scene_json = scene.model_dump_json(indent=2)

        return f"""
# ANIMATION SCENE TO IMPLEMENT

## Segment Context
{segment_context}

## Scene Specification (JSON)
```json
{scene_json}
```

## Requirements

Generate a complete Manim Scene class that implements this animation scene specification.

Key Requirements:
1. Study the documentation examples below to learn Manim class names and patterns
2. Create all shapes specified in the scene
3. Execute all animations in order with correct timing
4. Implement any mathematical animations with LaTeX formulas
5. Use only Manim classes you see demonstrated in the examples below
6. Follow the coding patterns from the examples

---

{rag_context}

---

## Task

Now generate the complete Manim Scene code as a JSON object matching the ManimSceneCode schema:
{{
  "scene_id": "{scene.scene_id}",
  "class_name": "descriptive_class_name_in_PascalCase",
  "imports": ["from manim import *"],
  "code": "complete Scene class code here"
}}

Generate the code now.
"""

    def _fetch_error_fix_context(self, errors: List[str]) -> str:
        """
        Use RAG to fetch relevant documentation for fixing any type of error.

        Extracts key terms from error messages and queries documentation.
        """
        # Extract meaningful terms from error messages
        search_terms = []

        for error in errors:
            # Extract quoted terms (often variable/class/constant names)
            import re
            quoted_terms = re.findall(r"'([^']+)'", error)
            search_terms.extend(quoted_terms)

            # Extract key error indicators
            error_lower = error.lower()
            if "undefined" in error_lower:
                search_terms.append("constants")
            if "not found" in error_lower:
                search_terms.append("classes")
            if "api misuse" in error_lower or "self.play" in error_lower:
                search_terms.append("play animation")
            if "construct" in error_lower:
                search_terms.append("Scene construct method")

        # Build search query from extracted terms
        if search_terms:
            query = "Manim " + " ".join(search_terms[:5])  # Limit to 5 terms
        else:
            query = "Manim Scene class animation examples"

        # Query RAG with OpenAI embeddings (same as indexing)
        try:
            # Get embedding for query using OpenAI
            query_embedding = self.retriever._get_embedding(query)

            results = self.retriever.collection.query(
                query_embeddings=[query_embedding],
                n_results=5
            )

            if results and results['documents'] and results['documents'][0]:
                docs = []
                for doc in results['documents'][0][:3]:  # Top 3 results
                    docs.append(doc[:600])  # First 600 chars of each

                docs_text = "\n\n---\n\n".join(docs)
                return f"""
## RELEVANT DOCUMENTATION FOR FIXING ERRORS

{docs_text}

Study the above examples to understand correct Manim usage and fix the errors.
"""
        except Exception as e:
            print(f"      Warning: Could not fetch error fix context: {e}")

        return ""

    def _build_error_feedback_prompt(
        self,
        previous_code: str,
        errors: List[str],
        attempt: int
    ) -> str:
        """Build a prompt to fix validation errors with RAG-retrieved fix guidance."""
        errors_list = "\n".join(f"  {i+1}. {error}" for i, error in enumerate(errors[:10]))

        # Fetch relevant documentation for fixing these errors
        fix_context = self._fetch_error_fix_context(errors)

        return f"""
## VALIDATION ERRORS FOUND - FIX REQUIRED (Attempt {attempt})

The previous code had validation errors. Please fix them:

**Errors:**
{errors_list}

{fix_context}

**Instructions:**
- Study the documentation examples above to see correct usage
- Only use classes, methods, and constants demonstrated in the examples
- Fix ALL errors listed above
- Make sure imports are correct: from manim import *

**Previous Code Fragment (first 2000 chars):**
```python
{previous_code[:2000]}...
```

Please regenerate the COMPLETE Scene class with ALL errors fixed. Base your fixes on the documentation examples above.
"""

    def _assemble_full_code(self, scene_codes: List[ManimSceneCode]) -> str:
        """Assemble full executable code for validation."""
        # Header
        code_parts = ["from manim import *\nimport numpy as np\n\n"]

        # Add all scene classes
        for scene_code in scene_codes:
            code_parts.append(scene_code.code)
            code_parts.append("\n\n")

        return "".join(code_parts)

    def _generate_file_header(self, requirements: AnimationRequirements) -> str:
        """Generate standard imports and header."""
        return f'''"""
Generated Manim Animation Code

Paper: {requirements.paper_title}
Auto-generated from animation requirements using RAG-guided code generation.

To render a specific scene:
    manim -pql generated_manim_code.py <SceneClassName>

To render all scenes:
    manim -pql generated_manim_code.py -a
"""

from manim import *
import numpy as np

'''

    def _assemble_complete_code(
        self,
        segment_codes: List[ManimSegmentCode],
        requirements: AnimationRequirements
    ) -> str:
        """Assemble all scene codes into executable Python file."""
        parts = [self._generate_file_header(requirements)]

        for segment in segment_codes:
            parts.append(f"\n{'#'*80}\n")
            parts.append(f"# SEGMENT: {segment.segment_id}\n")
            parts.append(f"{'#'*80}\n\n")

            if segment.shared_helpers:
                parts.append(segment.shared_helpers)
                parts.append("\n\n")

            for scene in segment.scenes:
                parts.append(f"# Scene: {scene.scene_id}\n")
                parts.append(scene.code)
                parts.append("\n\n")

        parts.append(f"\n{'#'*80}\n")
        parts.append("# END OF GENERATED CODE\n")
        parts.append(f"{'#'*80}\n")

        return "".join(parts)


def main(
    requirements_path: Optional[str] = None,
    output_path: Optional[str] = None,
    model_name: str = "openai/gpt-5",
    context_token_budget: int = 10000,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db"
):
    """
    Generate Manim code from animation requirements.

    Args:
        requirements_path: Path to animation_requirements.json
        output_path: Path to save generated code
        model_name: LLM model to use (default: openai/gpt-5)
        context_token_budget: Max tokens for RAG context (default: 10000)
        chroma_path: Path to ChromaDB storage

    Examples:
        # Basic usage
        python -m research_viz.manim_generator.manim_code_generator

        # Custom settings
        python -m research_viz.manim_generator.manim_code_generator \\
            --model-name "openai/gpt-4" \\
            --context-token-budget 15000
    """
    # Default paths
    if requirements_path is None:
        requirements_path = "src/research_viz/manim_generator/output/animation_requirements.json"

    if output_path is None:
        output_path = "src/research_viz/manim_generator/output/generated_manim_code.py"

    # Validate requirements file exists
    if not os.path.exists(requirements_path):
        print(f"ERROR: {requirements_path} not found")
        print(f"Please run animation_requirements_generator.py first")
        return

    # Validate ChromaDB exists
    if not os.path.exists(chroma_path):
        print(f"ERROR: {chroma_path} not found")
        print(f"Please run build_manim_index.py first to create the documentation index")
        return

    # Load requirements
    print(f"Loading animation requirements from: {requirements_path}")
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements_data = json.load(f)
    requirements = AnimationRequirements.model_validate(requirements_data)

    # Initialize retriever
    print(f"Initializing RAG retriever...")
    print(f"  ChromaDB path: {chroma_path}")
    print(f"  Context budget: {context_token_budget} tokens")
    retriever = ManimDocRetriever(chroma_path=chroma_path)

    # Initialize generator
    generator = ManimCodeGenerator(
        retriever=retriever,
        model_name=model_name,
        context_token_budget=context_token_budget
    )

    # Generate code
    generated_code = generator.generate_complete_code(requirements)

    # Save code
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(generated_code.complete_code)

    # Summary
    total_scenes = sum(len(seg.scenes) for seg in generated_code.segments)
    print(f"\n{'='*80}")
    print(f"SUCCESS!")
    print(f"{'='*80}")
    print(f"Generated code saved to: {output_path}")
    print(f"Total segments: {len(generated_code.segments)}")
    print(f"Total scenes: {total_scenes}")
    print(f"\nTo render animations:")
    print(f"  cd {Path(output_path).parent}")
    print(f"  manim -pql {Path(output_path).name} <SceneClassName>")
    print(f"\nTo render all scenes:")
    print(f"  manim -pql {Path(output_path).name} -a")


if __name__ == "__main__":
    tyro.cli(main)
