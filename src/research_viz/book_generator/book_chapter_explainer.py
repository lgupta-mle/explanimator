"""
Book Chapter Explainer: generates a 3B1B-style explanation for one chapter (or part).

Extends the existing generate_explanation_from_pdf pipeline with:
- Series bible injection (enforces consistent running example + notation)
- Rolling context window (previous chapter's final narration)
- series_bible_adherence judge criterion
"""

import json
from pathlib import Path
from typing import Optional

from research_viz.schemas.explanation_schemas import SeriesBible
from research_viz.config.difficulty import DifficultyConfig, DIFFICULTY_CONFIGS
from research_viz.manim_generator.pdf_explanation_generator import (
    create_pdf_llm_response,
    judge_explanation,
    load_prompt,
    _build_difficulty_prompt_section,
    JudgeResult,
    CriteriaScores,
)
from research_viz.utils.llm_utils import call_openrouter


# ---------------------------------------------------------------------------
# Bible injection helpers
# ---------------------------------------------------------------------------

def _build_bible_section(bible: SeriesBible, chapter_id: str) -> str:
    """Build the series bible block injected into every chapter prompt."""
    glossary_lines = "\n".join(
        f"  {sym}: {meaning}"
        for sym, meaning in bible.notation_glossary.items()
    )
    chapter_brief = bible.chapter_briefs.get(chapter_id, "")
    chapter_context = f"\nThis chapter: {chapter_brief}" if chapter_brief else ""

    return f"""
=== SERIES BIBLE (MANDATORY — DO NOT DEVIATE) ===
Book: {bible.book_title}

RUNNING EXAMPLE: You MUST use this exact running example throughout all segments:
  "{bible.series_running_example}"
Do not introduce a different example. Adapt this example to illustrate each concept in this chapter.

ESTABLISHED NOTATION (use these definitions — do NOT redefine them):
{glossary_lines}

VISUAL STYLE: {bible.visual_style_notes}
{chapter_context}
=== END SERIES BIBLE ===
"""


def _build_rolling_context_section(prev_narration: Optional[str]) -> str:
    """Build the rolling context block from the previous chapter's narration tail."""
    if not prev_narration:
        return ""
    tail = prev_narration.strip()[-800:]  # last ~200 words
    return f"""
=== CONTINUITY CONTEXT (previous chapter ended with) ===
{tail}
=== END CONTINUITY CONTEXT ===

Build naturally from this context. You may reference concepts introduced above
as already-known to the viewer.
"""


# ---------------------------------------------------------------------------
# Judge with bible adherence
# ---------------------------------------------------------------------------

def judge_chapter_explanation(
    explanation_json: str,
    bible: SeriesBible,
    model_name: str = "google/gemini-2.5-pro-preview",
    difficulty_config: Optional[DifficultyConfig] = None,
) -> JudgeResult:
    """
    Judge a chapter explanation against standard criteria PLUS series bible adherence.
    """
    from research_viz.manim_generator.pdf_explanation_generator import _build_difficulty_judge_section

    judge_prompt = load_prompt("3b1b_judge_prompt")
    difficulty_section = _build_difficulty_judge_section(difficulty_config) if difficulty_config else ""

    bible_criterion = f"""

ADDITIONAL CRITERION — series_bible_adherence:
  PASS if the explanation uses the established running example:
    "{bible.series_running_example}"
  FAIL if the explanation introduces a different unrelated example OR
  contradicts established notation from the series bible.
"""

    user_prompt = f"""
Evaluate this 3Blue1Brown-style chapter explanation against the quality criteria:

```json
{explanation_json}
```
{difficulty_section}
{bible_criterion}
Provide your evaluation as a JSON object with score, criteria_scores, and feedback (only if score is 0).
"""

    messages = [
        {"role": "system", "content": judge_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = call_openrouter(messages, model_name, JudgeResult)
        if "error" in response:
            return JudgeResult(score=0, criteria_scores=CriteriaScores(), feedback=f"API error: {response['error']}")

        choices = response.get("choices", [])
        if choices:
            content = choices[0]["message"]["content"]
            try:
                return JudgeResult.model_validate_json(content)
            except Exception:
                import re
                m = re.search(r'\{[^{}]*"score"[^{}]*\}', content, re.DOTALL)
                if m:
                    try:
                        return JudgeResult.model_validate_json(m.group())
                    except Exception:
                        pass
        return JudgeResult(score=0, criteria_scores=CriteriaScores(), feedback="Unexpected judge response")
    except Exception as e:
        return JudgeResult(score=0, criteria_scores=CriteriaScores(), feedback=f"Exception: {str(e)[:100]}")


# ---------------------------------------------------------------------------
# Main chapter explanation generator
# ---------------------------------------------------------------------------

def generate_chapter_explanation(
    chapter_pdf_path: str,
    chapter_title: str,
    chapter_id: str,
    output_path: str,
    bible: SeriesBible,
    model_name: str = "google/gemini-2.5-pro-preview",
    max_judge_attempts: int = 3,
    difficulty_config: Optional[DifficultyConfig] = None,
    prev_chapter_narration: Optional[str] = None,
) -> Optional[dict]:
    """
    Generate a 3B1B-style explanation for a single book chapter (or chapter part).

    Args:
        chapter_pdf_path: Path to the sub-PDF containing only this chapter's pages.
        chapter_title: Display title for the chapter (e.g. "Chapter 3: Backpropagation").
        chapter_id: Stable chapter identifier (e.g. "ch_03") used in the bible.
        output_path: Path to save the resulting explanation JSON.
        bible: Series bible enforcing consistency across all chapter videos.
        model_name: LLM model to use.
        max_judge_attempts: Max attempts to pass the quality + bible-adherence check.
        difficulty_config: Optional difficulty setting.
        prev_chapter_narration: Last ~200 words of the previous chapter's narration for continuity.

    Returns:
        The explanation dict, or None on failure.
    """
    difficulty_label = difficulty_config.level if difficulty_config else "medium (default)"
    print(f"\n  Chapter: {chapter_title}")
    print(f"  Chapter ID: {chapter_id}")
    print(f"  Model: {model_name} | Difficulty: {difficulty_label}")

    system_prompt = load_prompt("book_chapter_explanation_prompt")

    bible_section = _build_bible_section(bible, chapter_id)
    rolling_context = _build_rolling_context_section(prev_chapter_narration)

    base_user_prompt = f"""
Analyze this book chapter and create a complete 3Blue1Brown-style educational explanation.

{bible_section}
{rolling_context}

Requirements:
1. Use the series running example established in the bible above — do NOT invent a different one.
2. For each major concept, provide BOTH intuition AND technical sections.
3. Make the intuition visual and animatable.
4. Connect the math/theory to the running example concretely.

Output format — JSON with:
- paper_title (use the chapter title: "{chapter_title}")
- opening_question
- why_it_matters
- running_example (copy exactly from the series bible: "{bible.series_running_example}")
- segments

Each segment needs:
- segment_id, title, order
- intuition: core_insight, visual_metaphor, metaphor_example, starting_question, intuitive_walkthrough, key_visuals, transformations_to_show
- technical: intuition_to_math_bridge, key_equations (latex_formula, what_it_means, visualizable_aspect), shape_intuitions, mathematical_insight
- narration_script
"""

    if difficulty_config:
        base_user_prompt += _build_difficulty_prompt_section(difficulty_config)

    previous_feedback = None

    for attempt in range(max_judge_attempts):
        print(f"\n  Attempt {attempt + 1}/{max_judge_attempts}")

        if previous_feedback:
            user_prompt = f"""{base_user_prompt}

IMPORTANT — Previous attempt failed quality check. Fix these issues:
{previous_feedback}

Generate a revised explanation addressing ALL feedback above.
"""
        else:
            user_prompt = base_user_prompt

        print("    Generating explanation from chapter PDF...")
        try:
            from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B
            response = create_pdf_llm_response(
                pdf_path=chapter_pdf_path,
                prompt=user_prompt,
                system_prompt=system_prompt,
                model_name=model_name,
                schema=EducationalExplanation3B1B,
            )
        except Exception as exc:
            print(f"    LLM call failed: {exc}")
            continue

        if "choices" not in response or not response["choices"]:
            print(f"    Error: invalid response: {response.get('error', response)}")
            continue

        content = response["choices"][0]["message"]["content"]
        print(f"    Generated ({len(content)} chars)")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None

        # Validate segment count
        if difficulty_config and parsed:
            seg_count = len(parsed.get("segments", []))
            min_s, max_s = difficulty_config.min_segments, difficulty_config.max_segments
            if not (min_s <= seg_count <= max_s):
                print(f"    Segment count {seg_count} outside [{min_s}, {max_s}], retrying")
                previous_feedback = (
                    f"You generated {seg_count} segments but the requirement is {min_s}-{max_s}. "
                    f"Regenerate with exactly {min_s}-{max_s} segments."
                )
                continue

        # Judge with bible adherence
        print("    Judging explanation quality + bible adherence...")
        judge_result = judge_chapter_explanation(content, bible, model_name, difficulty_config)
        print(f"    Score: {judge_result.score}")

        if judge_result.score == 1:
            print("    PASSED!")
            if parsed is not None:
                if difficulty_config:
                    parsed["difficulty_level"] = difficulty_config.level
                parsed["chapter_id"] = chapter_id
                parsed["book_title"] = bible.book_title
                parsed["series_running_example"] = bible.series_running_example
            result = parsed or {"raw_content": content}
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"    Saved to: {output_path}")
            return result

        print(f"    FAILED quality check")
        if judge_result.feedback:
            print(f"    Feedback: {judge_result.feedback[:200]}...")
            previous_feedback = judge_result.feedback

    print(f"\n  Failed to pass quality check after {max_judge_attempts} attempts for: {chapter_title}")
    return None


def extract_narration_tail(explanation: dict, max_chars: int = 800) -> str:
    """
    Extract the tail of the last segment's narration script from an explanation dict.
    Used as rolling context for the next chapter.
    """
    segments = explanation.get("segments", [])
    if not segments:
        return ""
    last_segment = sorted(segments, key=lambda s: s.get("order", 0))[-1]
    narration = last_segment.get("narration_script", "")
    return narration[-max_chars:] if len(narration) > max_chars else narration
