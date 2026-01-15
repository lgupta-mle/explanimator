"""
PDF to Manim Pipeline

Complete pipeline: PDF → 3B1B Explanation → Manim Code with execution feedback.
Uses RAG only when execution errors occur.
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
import tyro
from dotenv import load_dotenv

from research_viz.manim_generator.pdf_explanation_generator import (
    create_pdf_llm_response,
    call_openrouter,
    load_prompt,
    encode_pdf_to_base64
)
from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B, Segment3B1B

load_dotenv()


class ManimSceneCode(BaseModel):
    """Generated Manim scene code."""
    scene_id: str = Field(..., description="Scene identifier")
    class_name: str = Field(..., description="PascalCase class name")
    code: str = Field(..., description="Complete Scene class code with imports")


def load_code_gen_prompt() -> str:
    """Load the Manim code generation prompt."""
    prompt_path = Path(__file__).parent / "prompts" / "manim_code_generation_prompt.txt"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def execute_manim_scene(code: str, class_name: str) -> tuple[bool, str]:
    """
    Execute Manim code and return success status and output/errors.

    Returns:
        (success, output_or_error)
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ['manim', 'render', '-ql', '--disable_caching', temp_path, class_name],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            error_output = result.stderr or result.stdout
            return False, error_output

    except subprocess.TimeoutExpired:
        return False, "Timeout: Manim render took too long (>120s)"
    except Exception as e:
        return False, f"Exception: {str(e)}"
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


def fetch_rag_context_for_error(error_message: str, chroma_path: str = "data/manim_docs/vector_db/chroma_db") -> str:
    """Fetch RAG context to help fix an error."""
    if not os.path.exists(chroma_path):
        return ""

    try:
        from research_viz.preprocessing.manim_db import ManimDocRetriever
        retriever = ManimDocRetriever(chroma_path=chroma_path)

        # Extract key terms from error
        import re
        search_terms = []

        # Extract quoted terms
        quoted = re.findall(r"'([^']+)'", error_message)
        search_terms.extend(quoted[:5])

        # Extract class names (PascalCase)
        classes = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', error_message)
        search_terms.extend(classes[:3])

        # Build query
        if search_terms:
            query = "Manim " + " ".join(search_terms[:5])
        else:
            query = "Manim Scene animation error fix"

        # Query RAG
        query_embedding = retriever._get_embedding(query)
        results = retriever.collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )

        if results and results['documents'] and results['documents'][0]:
            docs = [doc[:800] for doc in results['documents'][0][:3]]
            return "\n\n---\n\n".join(docs)

    except Exception as e:
        print(f"    RAG error: {e}")

    return ""


def generate_scene_code(
    segment: dict,
    running_example: str,
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db"
) -> Optional[ManimSceneCode]:
    """
    Generate Manim code for a segment with execution-based feedback loop.

    Process:
    1. Generate code without RAG
    2. Execute with Manim
    3. If error, fetch RAG context and retry
    """
    system_prompt = load_code_gen_prompt()

    segment_id = segment.get('segment_id', 'scene')
    title = segment.get('title', 'Untitled')
    narration = segment.get('narration_script', '')
    intuition = segment.get('intuition', {})
    technical = segment.get('technical', {})

    base_prompt = f"""
Generate a Manim animation scene for this segment of a 3Blue1Brown-style educational video.

## Segment: {title}
## Running Example: {running_example}

### Intuition Section:
- Core Insight: {intuition.get('core_insight', '')}
- Visual Metaphor: {intuition.get('visual_metaphor', '')}
- Key Visuals to Show: {json.dumps(intuition.get('key_visuals', []), indent=2)}
- Transformations to Animate: {json.dumps(intuition.get('transformations_to_show', []), indent=2)}

### Technical Section:
- Math Bridge: {technical.get('intuition_to_math_bridge', '')}
- Key Equations: {json.dumps(technical.get('key_equations', []), indent=2)}

### Narration:
{narration[:1500]}

## Requirements:
1. Create a complete, executable Manim Scene class
2. Visualize the key visuals and transformations described
3. Include any relevant equations using MathTex (not Tex for math symbols)
4. Use smooth animations and 3Blue1Brown style (dark background, clear colors)
5. The scene should be 30-60 seconds of animation

Output a JSON object with:
- scene_id: "{segment_id}"
- class_name: A descriptive PascalCase name
- code: Complete Python code with imports (from manim import *)
"""

    previous_error = None

    for attempt in range(max_retries):
        print(f"    Attempt {attempt + 1}/{max_retries}")

        # Build prompt with error feedback if retry
        if previous_error:
            rag_context = fetch_rag_context_for_error(previous_error, chroma_path)
            prompt = f"""{base_prompt}

## PREVIOUS ATTEMPT FAILED - FIX THESE ERRORS:

Error output:
```
{previous_error[:2000]}
```

{f"## Relevant Manim Documentation:{chr(10)}{rag_context}" if rag_context else ""}

Fix the errors and regenerate the complete scene code.
"""
        else:
            prompt = base_prompt

        # Generate code
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response = call_openrouter(messages, model_name, ManimSceneCode)

        if "error" in response:
            print(f"      API error: {response['error']}")
            continue

        if "choices" not in response or len(response["choices"]) == 0:
            print(f"      Invalid response")
            continue

        content = response["choices"][0]["message"]["content"]

        try:
            scene_code = ManimSceneCode.model_validate_json(content)
        except Exception as e:
            # Try to extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*"code"[\s\S]*\}', content)
            if json_match:
                try:
                    scene_code = ManimSceneCode.model_validate_json(json_match.group())
                except:
                    print(f"      Parse error: {e}")
                    continue
            else:
                print(f"      Parse error: {e}")
                continue

        # Execute the code
        print(f"      Executing Manim...")
        success, output = execute_manim_scene(scene_code.code, scene_code.class_name)

        if success:
            print(f"      SUCCESS!")
            return scene_code
        else:
            print(f"      Execution failed")
            previous_error = output

    print(f"    Failed after {max_retries} attempts")
    return None


def generate_all_scenes(
    explanation: dict,
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
    chroma_path: str = "data/manim_docs/vector_db/chroma_db"
) -> List[ManimSceneCode]:
    """Generate Manim code for all segments in the explanation."""
    running_example = explanation.get('running_example', '')
    segments = explanation.get('segments', [])

    print(f"\nGenerating Manim code for {len(segments)} segments")
    print(f"Running example: {running_example[:100]}...")

    scene_codes = []
    for i, segment in enumerate(segments):
        print(f"\n[{i+1}/{len(segments)}] Segment: {segment.get('title', 'Untitled')}")
        scene_code = generate_scene_code(
            segment=segment,
            running_example=running_example,
            model_name=model_name,
            max_retries=max_retries,
            chroma_path=chroma_path
        )
        if scene_code:
            scene_codes.append(scene_code)

    return scene_codes


def assemble_complete_code(scene_codes: List[ManimSceneCode], paper_title: str) -> str:
    """Assemble all scene codes into a single executable file."""
    header = f'''"""
Generated Manim Animation: {paper_title}

3Blue1Brown-style educational video animation.
Generated from PDF using pdf_to_manim_pipeline.

To render a scene:
    manim -pql generated_animation.py <ClassName>

To render all:
    manim -pql generated_animation.py -a
"""

from manim import *
import numpy as np

'''

    parts = [header]
    for scene_code in scene_codes:
        parts.append(f"\n# {'='*70}")
        parts.append(f"# Scene: {scene_code.scene_id}")
        parts.append(f"# {'='*70}\n")
        parts.append(scene_code.code)
        parts.append("\n")

    return "\n".join(parts)


def run_pipeline(
    pdf_path: str,
    output_dir: str = "src/research_viz/manim_generator/output",
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3,
    skip_explanation: bool = False,
    explanation_path: Optional[str] = None
) -> Optional[str]:
    """
    Run the complete PDF to Manim pipeline.

    Args:
        pdf_path: Path to the research paper PDF
        output_dir: Directory for output files
        model_name: LLM model to use
        max_retries: Max retries for code generation per segment
        skip_explanation: If True, use existing explanation file
        explanation_path: Path to existing explanation JSON (if skip_explanation=True)

    Returns:
        Path to generated Manim code file, or None on failure
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pdf_stem = Path(pdf_path).stem

    # Step 1: Generate or load explanation
    if skip_explanation and explanation_path:
        print(f"Loading existing explanation: {explanation_path}")
        with open(explanation_path, 'r') as f:
            explanation = json.load(f)
    else:
        print(f"Generating explanation from PDF: {pdf_path}")
        from research_viz.manim_generator.pdf_explanation_generator import generate_explanation_from_pdf
        explanation_output = f"{output_dir}/{pdf_stem}_explanation.json"
        explanation = generate_explanation_from_pdf(
            pdf_path=pdf_path,
            output_path=explanation_output,
            model_name=model_name,
            max_judge_attempts=3
        )
        if not explanation:
            print("Failed to generate explanation")
            return None

    # Step 2: Generate Manim code for all segments
    scene_codes = generate_all_scenes(
        explanation=explanation,
        model_name=model_name,
        max_retries=max_retries
    )

    if not scene_codes:
        print("No scenes generated successfully")
        return None

    # Step 3: Assemble and save
    paper_title = explanation.get('paper_title', pdf_stem)
    complete_code = assemble_complete_code(scene_codes, paper_title)

    output_path = f"{output_dir}/{pdf_stem}_animation.py"
    with open(output_path, 'w') as f:
        f.write(complete_code)

    print(f"\n{'='*70}")
    print(f"SUCCESS!")
    print(f"{'='*70}")
    print(f"Generated {len(scene_codes)} scenes")
    print(f"Output: {output_path}")
    print(f"\nTo render:")
    print(f"  manim -pql {output_path} <ClassName>")

    return output_path


def main(
    pdf_path: Optional[str] = None,
    explanation_path: Optional[str] = None,
    output_dir: str = "src/research_viz/manim_generator/output",
    model_name: str = "anthropic/claude-sonnet-4.5",
    max_retries: int = 3
):
    """
    Generate Manim animation from a PDF research paper.

    Args:
        pdf_path: Path to PDF (generates new explanation)
        explanation_path: Path to existing explanation JSON (skips PDF processing)
        output_dir: Output directory
        model_name: LLM model to use
        max_retries: Max retries per segment

    Examples:
        # From PDF (full pipeline)
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --pdf-path papers/attention.pdf

        # From existing explanation
        python -m research_viz.manim_generator.pdf_to_manim_pipeline \\
            --explanation-path output/attention_explanation.json
    """
    if explanation_path and os.path.exists(explanation_path):
        run_pipeline(
            pdf_path=explanation_path,  # Not used but required
            output_dir=output_dir,
            model_name=model_name,
            max_retries=max_retries,
            skip_explanation=True,
            explanation_path=explanation_path
        )
    elif pdf_path and os.path.exists(pdf_path):
        run_pipeline(
            pdf_path=pdf_path,
            output_dir=output_dir,
            model_name=model_name,
            max_retries=max_retries,
            skip_explanation=False
        )
    else:
        print("ERROR: Provide either --pdf-path or --explanation-path")
        print("  --pdf-path: Path to research paper PDF")
        print("  --explanation-path: Path to existing explanation JSON")


if __name__ == "__main__":
    tyro.cli(main)
