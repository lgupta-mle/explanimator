"""
PDF-Direct Explanation Generator with LLM Judge Feedback Loop

Generates 3Blue1Brown-style educational explanations directly from PDF research papers.
Uses OpenRouter's native PDF processing and includes an LLM judge for quality verification.
"""

import base64
import logging
import os
import json
from pathlib import Path
from typing import Optional, Type, TypeVar
from pydantic import BaseModel, Field
import tyro
from dotenv import load_dotenv

from research_viz.config.pipeline_config import get_config, get_provider

logger = logging.getLogger(__name__)

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


def _build_response_format(schema: Optional[Type[T]]) -> Optional[dict]:
    """Build response_format dict from a Pydantic schema."""
    if schema is None:
        return None
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema.__name__,
            "schema": schema.model_json_schema(),
            "strict": False,
        },
    }


def call_llm_provider(
    messages: list,
    model_name: str,
    schema: Optional[Type[T]] = None,
    plugins: Optional[list] = None,
) -> "LLMResponse":
    """Call the LLM provider and return an LLMResponse.

    model_name is required — resolve via get_config().llm.get_model() before calling.
    """
    from research_viz.providers.llm_provider import LLMResponse  # noqa: F811

    kwargs: dict = {}
    if plugins:
        kwargs["plugins"] = plugins
    rf = _build_response_format(schema)
    if rf:
        kwargs["response_format"] = rf

    return get_provider().generate(messages, model_name, **kwargs)


def create_pdf_llm_response(
    pdf_path: str,
    prompt: str,
    system_prompt: str,
    model_name: str,
    schema: Optional[Type[T]] = None,
) -> "LLMResponse":
    """Call the LLM provider with native PDF processing.

    model_name is required — resolve via get_config().llm.get_model() before calling.
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
                        "file_data": data_url,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        },
    ]

    plugins = [{"id": "file-parser", "pdf": {"engine": "native"}}]

    return call_llm_provider(messages, model_name, schema, plugins)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt file from the prompts directory."""
    prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.txt"
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def judge_explanation(
    explanation_json: str,
    model_name: str,
) -> JudgeResult:
    """
    Use LLM judge to evaluate the explanation quality.

    model_name is required — resolve via get_config().llm.get_model() before calling.
    """
    judge_prompt = load_prompt("3b1b_judge_prompt")

    user_prompt = f"""
Evaluate this 3Blue1Brown-style explanation against the quality criteria:

```json
{explanation_json}
```

Provide your evaluation as a JSON object with score, criteria_scores, and feedback (only if score is 0).
"""

    messages = [
        {"role": "system", "content": judge_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        llm_response = call_llm_provider(messages, model_name, JudgeResult)
        content = llm_response.content

        if not content:
            logger.warning(f"    Judge returned empty content")
            return JudgeResult(score=0, criteria_scores={}, feedback="Empty response")

        try:
            return JudgeResult.model_validate_json(content)
        except Exception as e:
            import re
            json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', content, re.DOTALL)
            if json_match:
                try:
                    return JudgeResult.model_validate_json(json_match.group())
                except:
                    pass
            logger.error(f"    Judge parse error: {e}")
            return JudgeResult(score=0, criteria_scores={}, feedback=f"Parse error: {str(e)[:100]}")

    except Exception as e:
        logger.error(f"    Judge exception: {e}")
        return JudgeResult(score=0, criteria_scores={}, feedback=f"Exception: {str(e)[:100]}")


def _validate_segment_count(content: str, min_segments: int = 2, max_segments: int = 3) -> bool:
    """Check if explanation has between min and max segments."""
    try:
        data = json.loads(content)
        segments = data.get("segments", [])
        return min_segments <= len(segments) <= max_segments
    except (json.JSONDecodeError, TypeError):
        return False


def generate_with_feedback_loop(
    pdf_path: str,
    difficulty: str,
    model_name: Optional[str] = None,
    max_attempts: int = 3,
) -> Optional[dict]:
    """
    Generate explanation with LLM judge feedback loop.

    Process:
    1. Generate initial explanation from PDF
    2. Judge evaluates against quality criteria (skipped if tier has skip_judge=True)
    3. If score=0, regenerate with feedback
    4. Repeat until score=1 or max_attempts reached

    Args:
        difficulty: Required. Selects model tier and judge behavior.

    Returns:
        Final explanation dict or None on failure
    """
    cfg = get_config()
    if model_name is None:
        model_name = cfg.llm.get_model("explanation_model", difficulty)
    tier = cfg.llm.get_tier(difficulty)
    skip_judge = tier.skip_judge if tier else False
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

    previous_feedback = None

    for attempt in range(max_attempts):
        logger.info(f"Attempt {attempt + 1}/{max_attempts}")

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
        logger.info("  Generating explanation from PDF...")
        try:
            from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B
            llm_response = create_pdf_llm_response(
                pdf_path=pdf_path,
                prompt=user_prompt,
                system_prompt=system_prompt,
                model_name=model_name,
                schema=EducationalExplanation3B1B,
            )
        except ImportError:
            llm_response = create_pdf_llm_response(
                pdf_path=pdf_path,
                prompt=user_prompt,
                system_prompt=system_prompt,
                model_name=model_name,
                schema=None,
            )

        content = llm_response.content
        if not content:
            logger.error(f"  Empty response from LLM")
            continue

        logger.info(f"  Generated explanation ({len(content)} chars)")

        # Strip markdown code fences if present
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
            if stripped.endswith("```"):
                stripped = stripped[:-3]
            content = stripped.strip()

        if skip_judge:
            logger.info("  Skipping judge (skip_judge enabled for this tier)")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("  Failed to parse explanation as JSON")
                continue

        # Judge the explanation
        logger.info("  Judging explanation quality...")
        judge_model = cfg.llm.get_model("judge_model", difficulty)
        judge_result = judge_explanation(content, judge_model)

        logger.info(f"  Score: {judge_result.score}")
        logger.info(f"  Criteria: {judge_result.criteria_scores}")

        if judge_result.score == 1:
            logger.info("  PASSED quality check!")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw_content": content}

        # Failed - prepare feedback for next attempt
        logger.warning(f"  FAILED quality check")
        if judge_result.feedback:
            logger.info(f"  Feedback: {judge_result.feedback[:200]}...")
            previous_feedback = judge_result.feedback

    logger.error(f"Failed to pass quality check after {max_attempts} attempts")
    return None


def generate_explanation_from_pdf(
    pdf_path: str,
    output_path: str,
    difficulty: str,
    model_name: Optional[str] = None,
    max_judge_attempts: int = 3,
) -> Optional[dict]:
    """
    Generate a 3B1B-style educational explanation directly from a PDF.

    Args:
        pdf_path: Path to the research paper PDF
        output_path: Path to save the explanation JSON
        difficulty: Required. Selects model tier.
        model_name: Optional override for explanation model
        max_judge_attempts: Max attempts to pass quality check

    Returns:
        The generated explanation as a dict, or None on error
    """
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"Difficulty: {difficulty}")
    logger.info(f"Max judge attempts: {max_judge_attempts}")

    explanation = generate_with_feedback_loop(
        pdf_path=pdf_path,
        difficulty=difficulty,
        model_name=model_name,
        max_attempts=max_judge_attempts,
    )

    if explanation:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(explanation, f, indent=2)
        logger.info(f"Explanation saved to: {output_path}")
        if "paper_title" in explanation:
            logger.info(f"Paper: {explanation['paper_title']}")
        if "segments" in explanation:
            logger.info(f"Segments: {len(explanation['segments'])}")
        if "running_example" in explanation:
            logger.info(f"Running example: {explanation['running_example']}")

    return explanation


def main(
    pdf_path: str,
    difficulty: str = "medium",
    output_path: Optional[str] = None,
    model_name: Optional[str] = None,
    max_judge_attempts: int = 3
):
    """
    Generate 3Blue1Brown-style educational explanation from a PDF research paper.

    Args:
        pdf_path: Path to the research paper PDF
        difficulty: Difficulty tier (hard, medium, easy)
        output_path: Path to save the explanation JSON (default: same dir as PDF)
        model_name: Optional model override
        max_judge_attempts: Max attempts to pass quality check (default: 3)

    Examples:
        python -m research_viz.manim_generator.pdf_explanation_generator \\
            --pdf-path papers/attention.pdf --difficulty hard
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        return

    if output_path is None:
        pdf_stem = Path(pdf_path).stem
        output_path = f"src/research_viz/manim_generator/output/{pdf_stem}_explanation.json"

    generate_explanation_from_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        difficulty=difficulty,
        model_name=model_name,
        max_judge_attempts=max_judge_attempts,
    )


if __name__ == "__main__":
    tyro.cli(main)
