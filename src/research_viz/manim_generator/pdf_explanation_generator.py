"""
PDF-Direct Explanation Generator with LLM Judge Feedback Loop

Generates 3Blue1Brown-style educational explanations directly from PDF research papers.
Uses OpenRouter's native PDF processing and includes an LLM judge for quality verification.
"""

import base64
import os
import json
from pathlib import Path
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, Field
import tyro
from dotenv import load_dotenv

from research_viz.config.difficulty import DifficultyConfig, DIFFICULTY_CONFIGS
from research_viz.utils.llm_utils import call_openrouter

load_dotenv()

T = TypeVar('T', bound=BaseModel)


class CriteriaScores(BaseModel):
    """Individual criterion scores for the judge."""
    intuition_before_formulas: int = Field(0, description="1 if pass, 0 if fail")
    visual_metaphor_quality: int = Field(0, description="1 if pass, 0 if fail")
    running_example_consistency: int = Field(0, description="1 if pass, 0 if fail")
    animation_potential: int = Field(0, description="1 if pass, 0 if fail")
    math_intuition_connection: int = Field(0, description="1 if pass, 0 if fail")
    narration_quality: int = Field(0, description="1 if pass, 0 if fail")


class JudgeResult(BaseModel):
    """Result from the LLM judge evaluation."""
    score: int = Field(..., description="1 for pass, 0 for fail")
    criteria_scores: CriteriaScores = Field(default_factory=CriteriaScores, description="Individual criterion scores")
    feedback: Optional[str] = Field(None, description="Feedback if score is 0")


def encode_pdf_to_base64(pdf_path: str) -> str:
    """Encode a PDF file to base64 string."""
    with open(pdf_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def create_pdf_llm_response(
    pdf_path: str,
    prompt: str,
    system_prompt: str,
    model_name: str = "openai/gpt-5",
    schema: Optional[Type[T]] = None
) -> dict:
    """
    Call OpenRouter with native PDF processing.

    Best practices:
    - PDF placed BEFORE text in request
    - Native engine to avoid parsing costs
    """
    base64_pdf = encode_pdf_to_base64(pdf_path)
    data_url = f"data:application/pdf;base64,{base64_pdf}"

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "filename": Path(pdf_path).name,
                        "file_data": data_url
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }
    ]

    plugins = [{"id": "file-parser", "pdf": {"engine": "native"}}]

    return call_openrouter(messages, model_name, schema, plugins)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt file from the prompts directory."""
    prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.txt"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_prerequisite_tree(
    pdf_path: str,
    model_name: str = "openai/gpt-5"
) -> Optional[dict]:
    """Generate a prerequisite tree of mathematical concepts needed for easy mode."""
    from research_viz.schemas.explanation_schemas import PrerequisiteTree

    system_prompt = """You are a mathematics education expert. Given a research paper, identify ALL mathematical
and technical prerequisites a complete beginner would need to understand it. Build a tree from the paper's
core concepts down to fundamental prerequisites (up to 3 levels deep)."""

    user_prompt = """Analyze this research paper and generate a prerequisite tree.

For each concept in the paper, identify what someone needs to know BEFORE they can understand it,
and what they need to know before THAT, down to 3 levels.

depth_level meanings:
- 0: Core concept from the paper itself
- 1: Direct prerequisite (need this to understand a paper concept)
- 2: Prerequisite of a prerequisite
- 3: Foundational concept (basic math/CS that a beginner might not know)

Output JSON with: paper_title, root_concepts (list of main paper concepts),
prerequisites (list of PrerequisiteConcept with concept_name, why_needed, depth_level, parent_concept, estimated_explanation_time_seconds)."""

    response = create_pdf_llm_response(
        pdf_path=pdf_path,
        prompt=user_prompt,
        system_prompt=system_prompt,
        model_name=model_name,
        schema=PrerequisiteTree
    )

    if "choices" not in response or len(response["choices"]) == 0:
        raise RuntimeError(f"Prerequisite tree generation failed: no choices in LLM response. Response: {response}")

    content = response["choices"][0]["message"]["content"]
    try:
        tree = PrerequisiteTree.model_validate_json(content)
        return tree.model_dump()
    except Exception:
        # Fallback: try raw JSON parse (may lack Pydantic validation)
        return json.loads(content)


def _build_difficulty_prompt_section(difficulty_config: DifficultyConfig, prereq_tree: Optional[dict] = None) -> str:
    """Build difficulty-specific prompt section to append to the user prompt."""
    if difficulty_config.level == "easy":
        prereq_section = ""
        if prereq_tree and prereq_tree.get("prerequisites"):
            concepts = [p["concept_name"] for p in prereq_tree["prerequisites"]]
            prereq_section = f"""
MANDATORY PREREQUISITE SEGMENTS:
You MUST dedicate segments to explaining each of these prerequisites from scratch: {', '.join(concepts)}.
Do NOT assume the viewer knows ANY of these. Explain foundational concepts before building on them
(e.g., explain differentiation before chain rule, explain chain rule before backprop).
"""
        return f"""
DIFFICULTY: EASY (Complete Beginner)
- Create {difficulty_config.min_segments}-{difficulty_config.max_segments} segments.
- Each narration MUST be {difficulty_config.min_narration_words}-{difficulty_config.max_narration_words} words.
- Explain EVERY concept from first principles. Assume ZERO prior knowledge.
- Use extensive analogies and real-world examples.
{prereq_section}"""

    elif difficulty_config.level == "hard":
        return f"""
DIFFICULTY: HARD (Expert/PhD-level)
- Create {difficulty_config.min_segments}-{difficulty_config.max_segments} segments.
- Each narration MUST be {difficulty_config.min_narration_words}-{difficulty_config.max_narration_words} words.
- Assume PhD-level domain expertise. Skip ALL prerequisites.
- Focus exclusively on novel contributions and technical depth.
- Be concise and information-dense."""

    # Medium: no extra constraints (current default behavior)
    return ""


def _build_difficulty_judge_section(difficulty_config: DifficultyConfig) -> str:
    """Build difficulty-specific section for the judge prompt."""
    if difficulty_config.level == "easy":
        return """

ADDITIONAL CRITERION FOR EASY MODE:
- prerequisite_coverage: Are ALL identified prerequisites explained from scratch with their own visual metaphors?
  FAIL if any prerequisite is just mentioned without dedicated explanation."""

    elif difficulty_config.level == "hard":
        return """

NOTE FOR HARD MODE EVALUATION:
This is expert-level content. Do NOT penalize for skipping prerequisites or being terse.
Instead, check for conciseness, density, and focus on novel contributions."""

    return ""


def judge_explanation(
    explanation_json: str,
    model_name: str = "openai/gpt-5",
    difficulty_config: Optional[DifficultyConfig] = None
) -> JudgeResult:
    """
    Use LLM judge to evaluate the explanation quality.

    Returns:
        JudgeResult with score (0 or 1) and feedback if failed
    """
    judge_prompt = load_prompt("3b1b_judge_prompt")

    difficulty_section = ""
    if difficulty_config:
        difficulty_section = _build_difficulty_judge_section(difficulty_config)

    user_prompt = f"""
Evaluate this 3Blue1Brown-style explanation against the quality criteria:

```json
{explanation_json}
```
{difficulty_section}
Provide your evaluation as a JSON object with score, criteria_scores, and feedback (only if score is 0).
"""

    messages = [
        {"role": "system", "content": judge_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response = call_openrouter(messages, model_name, JudgeResult)

        if "error" in response:
            print(f"    Judge API error: {response['error']}")
            return JudgeResult(score=0, criteria_scores={}, feedback=f"API error: {response['error']}")

        if "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            try:
                return JudgeResult.model_validate_json(content)
            except Exception as e:
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', content, re.DOTALL)
                if json_match:
                    try:
                        return JudgeResult.model_validate_json(json_match.group())
                    except:
                        pass
                print(f"    Judge parse error: {e}")
                print(f"    Raw content: {content[:500]}...")
                return JudgeResult(score=0, criteria_scores={}, feedback=f"Parse error: {str(e)[:100]}")

        print(f"    Unexpected judge response: {response}")
        return JudgeResult(score=0, criteria_scores={}, feedback="Unexpected response format")

    except Exception as e:
        print(f"    Judge exception: {e}")
        return JudgeResult(score=0, criteria_scores={}, feedback=f"Exception: {str(e)[:100]}")


def generate_with_feedback_loop(
    pdf_path: str,
    model_name: str = "openai/gpt-5",
    max_attempts: int = 3,
    difficulty_config: Optional[DifficultyConfig] = None,
    prereq_tree: Optional[dict] = None
) -> Optional[dict]:
    """
    Generate explanation with LLM judge feedback loop.

    Process:
    1. Generate initial explanation from PDF
    2. Judge evaluates against quality criteria
    3. If score=0, regenerate with feedback
    4. Repeat until score=1 or max_attempts reached

    Returns:
        Final explanation dict or None on failure
    """
    system_prompt = load_prompt("3b1b_explanation_prompt")

    base_user_prompt = """
Analyze this research paper and create a complete 3Blue1Brown-style educational explanation.

Requirements:
1. Pick ONE concrete running example and use it throughout
2. For each major concept, provide BOTH intuition AND technical sections
3. Make the intuition visual and animatable
4. Connect the math to the intuition

Output format - JSON with:
- paper_title
- opening_question (the big question this paper addresses)
- why_it_matters (why should viewers care)
- running_example (the ONE example used throughout)
- segments (list of video segments, each with intuition and technical parts)

Each segment needs:
- segment_id, title, order
- intuition: core_insight, visual_metaphor, metaphor_example, starting_question, intuitive_walkthrough, key_visuals, transformations_to_show
- technical: intuition_to_math_bridge, key_equations (latex_formula, what_it_means, visualizable_aspect), shape_intuitions, mathematical_insight
- narration_script
"""

    # Append difficulty-specific instructions
    if difficulty_config:
        difficulty_section = _build_difficulty_prompt_section(difficulty_config, prereq_tree)
        base_user_prompt += difficulty_section

    previous_feedback = None

    for attempt in range(max_attempts):
        print(f"\nAttempt {attempt + 1}/{max_attempts}")

        # Build prompt with feedback if this is a retry
        if previous_feedback:
            user_prompt = f"""{base_user_prompt}

IMPORTANT - Previous attempt failed quality check. Fix these issues:

{previous_feedback}

Generate a revised explanation that addresses ALL the feedback above.
"""
        else:
            user_prompt = base_user_prompt

        # Generate explanation
        print("  Generating explanation from PDF...")
        try:
            from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B
            response = create_pdf_llm_response(
                pdf_path=pdf_path,
                prompt=user_prompt,
                system_prompt=system_prompt,
                model_name=model_name,
                schema=EducationalExplanation3B1B
            )
        except ImportError:
            print("  Error: ImportError")
            response = create_pdf_llm_response(
                pdf_path=pdf_path,
                prompt=user_prompt,
                system_prompt=system_prompt,
                model_name=model_name,
                schema=None
            )

        if "choices" not in response or len(response["choices"]) == 0:
            print(f"  Error: Invalid response from LLM: {response}")
            continue

        content = response["choices"][0]["message"]["content"]
        print(f"  Generated explanation ({len(content)} chars)")

        # Parse content once for reuse
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None

        # Validate segment count against difficulty config
        if difficulty_config and parsed:
            seg_count = len(parsed.get("segments", []))
            min_s, max_s = difficulty_config.min_segments, difficulty_config.max_segments
            if not (min_s <= seg_count <= max_s):
                print(f"  Segment count {seg_count} outside range [{min_s}, {max_s}], auto-retrying")
                previous_feedback = (
                    f"You generated {seg_count} segments but the requirement is {min_s}-{max_s}. "
                    f"Regenerate with exactly {min_s}-{max_s} segments."
                )
                continue

        # Judge the explanation
        print("  Judging explanation quality...")
        judge_result = judge_explanation(content, model_name, difficulty_config)

        print(f"  Score: {judge_result.score}")
        print(f"  Criteria: {judge_result.criteria_scores}")

        if judge_result.score == 1:
            print("  PASSED quality check!")
            if parsed is not None:
                if difficulty_config:
                    parsed["difficulty_level"] = difficulty_config.level
                if prereq_tree:
                    parsed["prerequisite_tree"] = prereq_tree
                return parsed
            return {"raw_content": content}

        # Failed - prepare feedback for next attempt
        print(f"  FAILED quality check")
        if judge_result.feedback:
            print(f"  Feedback: {judge_result.feedback[:200]}...")
            previous_feedback = judge_result.feedback

    print(f"\nFailed to pass quality check after {max_attempts} attempts")
    return None


def generate_explanation_from_pdf(
    pdf_path: str,
    output_path: str,
    model_name: str = "openai/gpt-5",
    max_judge_attempts: int = 3,
    difficulty_config: Optional[DifficultyConfig] = None
) -> Optional[dict]:
    """
    Generate a 3B1B-style educational explanation directly from a PDF.

    Args:
        pdf_path: Path to the research paper PDF
        output_path: Path to save the explanation JSON
        model_name: LLM model to use
        max_judge_attempts: Max attempts to pass quality check
        difficulty_config: Optional difficulty configuration

    Returns:
        The generated explanation as a dict, or None on error
    """
    difficulty_label = difficulty_config.level if difficulty_config else "medium (default)"
    print(f"PDF: {pdf_path}")
    print(f"Model: {model_name}")
    print(f"Difficulty: {difficulty_label}")
    print(f"Max judge attempts: {max_judge_attempts}")

    # Generate prerequisite tree for easy mode
    prereq_tree = None
    if difficulty_config and difficulty_config.include_prerequisite_segments:
        print("\nGenerating prerequisite tree for easy mode...")
        prereq_tree = generate_prerequisite_tree(pdf_path, model_name)
        if prereq_tree:
            print(f"  Found {len(prereq_tree.get('prerequisites', []))} prerequisites")
        else:
            print("  Warning: Failed to generate prerequisite tree, continuing without it")

    explanation = generate_with_feedback_loop(
        pdf_path=pdf_path,
        model_name=model_name,
        max_attempts=max_judge_attempts,
        difficulty_config=difficulty_config,
        prereq_tree=prereq_tree
    )

    if explanation:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(explanation, f, indent=2)
        print(f"\nExplanation saved to: {output_path}")
        if "paper_title" in explanation:
            print(f"Paper: {explanation['paper_title']}")
        if "segments" in explanation:
            print(f"Segments: {len(explanation['segments'])}")
        if "running_example" in explanation:
            print(f"Running example: {explanation['running_example']}")

    return explanation


def main(
    pdf_path: str,
    output_path: Optional[str] = None,
    model_name: str = "openai/gpt-5",
    max_judge_attempts: int = 3,
    difficulty: str = "medium"
):
    """
    Generate 3Blue1Brown-style educational explanation from a PDF research paper.

    Args:
        pdf_path: Path to the research paper PDF
        output_path: Path to save the explanation JSON (default: same dir as PDF)
        model_name: LLM model to use
        max_judge_attempts: Max attempts to pass quality check (default: 3)
        difficulty: Difficulty level - easy, medium, or hard (default: medium)

    Examples:
        python -m research_viz.manim_generator.pdf_explanation_generator \\
            --pdf-path papers/attention.pdf --difficulty easy

        python -m research_viz.manim_generator.pdf_explanation_generator \\
            --pdf-path papers/attention.pdf --difficulty hard
    """
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found: {pdf_path}")
        return

    if difficulty not in DIFFICULTY_CONFIGS:
        print(f"ERROR: Invalid difficulty '{difficulty}'. Choose from: easy, medium, hard")
        return

    difficulty_config = DIFFICULTY_CONFIGS[difficulty]

    if output_path is None:
        pdf_stem = Path(pdf_path).stem
        output_path = f"src/research_viz/manim_generator/output/{pdf_stem}_{difficulty}_en/{pdf_stem}_explanation.json"

    generate_explanation_from_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        model_name=model_name,
        max_judge_attempts=max_judge_attempts,
        difficulty_config=difficulty_config
    )


if __name__ == "__main__":
    tyro.cli(main)
