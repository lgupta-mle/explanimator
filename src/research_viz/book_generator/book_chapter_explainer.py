"""
Book Chapter Explainer: generates a 3B1B-style explanation for one chapter (or part).

Extends the existing generate_explanation_from_pdf pipeline with:
- Series bible injection (enforces consistent running example + notation)
- Rolling context window (previous chapter's final narration)
- series_bible_adherence judge criterion
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from research_viz.schemas.explanation_schemas import SeriesBible
from research_viz.config.difficulty import DifficultyConfig
from research_viz.manim_generator.pdf_explanation_generator import (
    create_pdf_llm_response,
    load_prompt,
    _build_difficulty_prompt_section,
    JudgeResult,
    CriteriaScores,
)
from research_viz.utils.llm_utils import call_openrouter


# ---------------------------------------------------------------------------
# Bible injection helpers
# ---------------------------------------------------------------------------

def bible_fingerprint(bible: SeriesBible) -> str:
    """Short hash of the bible's key fields so we can detect stale explanation caches."""
    payload = f"{bible.series_running_example}|{sorted(bible.notation_glossary.items())}"
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _truncate_at_word_boundary(text: str, max_chars: int = 800) -> str:
    """Return the last `max_chars` characters of text, trimmed to a word boundary."""
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    first_space = tail.find(' ')
    if first_space != -1 and first_space < 50:
        tail = tail[first_space + 1:]
    return tail


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
    tail = _truncate_at_word_boundary(prev_narration.strip(), 800)
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
    model_name: str = "google/gemini-2.5-pro",
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
# Two-stage digest extraction helpers
# ---------------------------------------------------------------------------

def extract_chapter_digest(
    chapter_pdf_path: str,
    digest_cache_path: str,
    extraction_model: str = "google/gemini-2.5-flash",
) -> Optional[str]:
    """
    Stage 1: Extract a structured chapter digest from the PDF using a cheap model.
    Returns the digest markdown text, or None on failure. Caches to disk.
    """
    if Path(digest_cache_path).exists():
        print(f"    Loading cached chapter digest: {digest_cache_path}")
        return Path(digest_cache_path).read_text(encoding="utf-8")

    print(f"    Extracting chapter digest with {extraction_model} ...")
    system_prompt = load_prompt("chapter_digest_prompt")
    user_prompt = (
        "Extract a comprehensive chapter digest from this PDF chapter. "
        "Preserve all mathematical detail and precision exactly."
    )

    try:
        response = create_pdf_llm_response(
            pdf_path=chapter_pdf_path,
            prompt=user_prompt,
            system_prompt=system_prompt,
            model_name=extraction_model,
            schema=None,
        )
    except Exception as exc:
        print(f"    Digest extraction failed: {exc}")
        return None

    digest_text = response.content
    if not digest_text or not digest_text.strip():
        print(f"    Digest extraction: blank content returned")
        return None

    print(f"    Digest extracted ({len(digest_text):,} chars)")
    Path(digest_cache_path).parent.mkdir(parents=True, exist_ok=True)
    Path(digest_cache_path).write_text(digest_text, encoding="utf-8")
    return digest_text


def _create_text_llm_response(
    text_content: str,
    prompt: str,
    system_prompt: str,
    model_name: str,
    schema=None,
) -> dict:
    """Call OpenRouter with plain text content (no PDF attachment). Used for Stage 2."""
    combined_prompt = f"{text_content}\n\n---\n\n{prompt}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": combined_prompt},
    ]
    return call_openrouter(messages, model_name, schema)


# ---------------------------------------------------------------------------
# Main chapter explanation generator
# ---------------------------------------------------------------------------

def generate_chapter_explanation(
    chapter_pdf_path: str,
    chapter_title: str,
    chapter_id: str,
    output_path: str,
    bible: SeriesBible,
    model_name: str = "google/gemini-2.5-pro",
    extraction_model: str = "google/gemini-2.5-flash",
    max_judge_attempts: int = 3,
    difficulty_config: Optional[DifficultyConfig] = None,
    prev_chapter_narration: Optional[str] = None,
) -> Optional[dict]:
    """
    Generate a 3B1B-style explanation for a single book chapter (or chapter part).

    Uses a two-stage pipeline:
      Stage 1: extraction_model extracts a structured chapter digest from the PDF (cached).
      Stage 2: model_name generates the 3B1B explanation from the digest text.
    If Stage 1 fails, falls back to sending the full PDF directly to model_name.

    Args:
        chapter_pdf_path: Path to the sub-PDF containing only this chapter's pages.
        chapter_title: Display title for the chapter (e.g. "Chapter 3: Backpropagation").
        chapter_id: Stable chapter identifier (e.g. "ch_03") used in the bible.
        output_path: Path to save the resulting explanation JSON.
        bible: Series bible enforcing consistency across all chapter videos.
        model_name: LLM model for explanation generation (Stage 2).
        extraction_model: Cheap model for chapter digest extraction (Stage 1).
        max_judge_attempts: Max attempts to pass the quality + bible-adherence check.
        difficulty_config: Optional difficulty setting.
        prev_chapter_narration: Last ~200 words of the previous chapter's narration for continuity.

    Returns:
        The explanation dict, or None on failure.
    """
    difficulty_label = difficulty_config.level if difficulty_config else "medium (default)"
    print(f"\n  Chapter: {chapter_title}")
    print(f"  Chapter ID: {chapter_id}")
    print(f"  Model: {model_name} | Extraction: {extraction_model} | Difficulty: {difficulty_label}")

    system_prompt = load_prompt("book_chapter_explanation_prompt")

    # --- Stage 1: Extract chapter digest (cheap model, cached) ---
    digest_cache_path = str(Path(output_path).parent / "digest.md")
    digest = extract_chapter_digest(chapter_pdf_path, digest_cache_path, extraction_model)
    if digest is None:
        print("    Digest extraction failed — falling back to direct PDF for explanation generation")

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
5. Cover ALL key definitions and core concepts from the chapter — do not skip any.
   If you have fewer segments than concepts, combine related concepts into the same segment.

Output format — JSON with:
- paper_title (use the chapter title: "{chapter_title}")
- opening_question
- why_it_matters
- running_example (copy exactly from the series bible: "{bible.series_running_example}")
- segments

Each segment needs:
- segment_id, title, order
- intuition: core_insight, visual_metaphor, metaphor_example, starting_question, intuitive_walkthrough, key_visuals, transformations_to_show
- technical:
  - intuition_to_math_bridge
  - key_equations: a LIST (one entry per distinct symbolic relationship), each with:
    - latex_formula, what_it_means, visualizable_aspect
    - derivation_steps: ordered list, each step with latex_formula, from_previous (justification),
      new_symbol_introduced (symbol + plain meaning on first appearance), example_substitution
      (running example's numbers plugged in WITH the computed result), visualizable_action
  - equation_build_order: ordered list of equation ids describing how equations appear on screen
  - running_example_walkthrough: one numeric thread carried through the segment's equations
  - shape_intuitions, mathematical_insight
- narration_script
"""

    if difficulty_config:
        base_user_prompt += _build_difficulty_prompt_section(difficulty_config)

    previous_feedback = None
    previous_content: Optional[str] = None
    user_prompt = base_user_prompt

    for attempt in range(max_judge_attempts):
        print(f"\n  Attempt {attempt + 1}/{max_judge_attempts}")

        from research_viz.schemas.explanation_schemas import EducationalExplanation3B1B

        if previous_feedback and previous_content:
            # Revision step: work from the prior explanation JSON + judge feedback
            # instead of regenerating blind from the digest — lets the model fix
            # exactly what was flagged rather than drifting on a fresh attempt.
            print("    Revising prior explanation from feedback...")
            revise_prompt = f"""Below is your previous chapter explanation attempt and the feedback on why it failed.
Produce a revised explanation in the SAME JSON schema that addresses ALL the feedback.

PREVIOUS EXPLANATION:
```json
{previous_content}
```

FEEDBACK:
{previous_feedback}

Output the revised explanation as JSON only, no other commentary.
"""
            try:
                response = call_openrouter(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": revise_prompt},
                    ],
                    model_name,
                    EducationalExplanation3B1B,
                )
            except Exception as exc:
                print(f"    LLM call failed: {exc}")
                continue

            if "choices" not in response or not response["choices"]:
                print(f"    Error: invalid response: {response.get('error', response)}")
                continue
            content = response["choices"][0]["message"]["content"]
        elif digest is not None:
            print("    Stage 2: generating explanation from chapter digest...")
            try:
                response = _create_text_llm_response(
                    text_content=digest,
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model_name=model_name,
                    schema=EducationalExplanation3B1B,
                )
            except Exception as exc:
                print(f"    LLM call failed: {exc}")
                continue

            # call_openrouter returns the raw JSON dict
            if "choices" not in response or not response["choices"]:
                print(f"    Error: invalid response: {response.get('error', response)}")
                continue
            content = response["choices"][0]["message"]["content"]
        else:
            print("    Generating explanation from chapter PDF (fallback)...")
            try:
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

            # create_pdf_llm_response returns an LLMResponse object
            content = response.content

        if not content or not content.strip():
            print(f"    Error: blank content returned")
            continue

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
                previous_content = content
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
                # Fingerprint so downstream caches can detect bible changes
                parsed["_bible_fingerprint"] = bible_fingerprint(bible)
            result = parsed or {"raw_content": content}
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"    Saved to: {output_path}")
            return result

        print(f"    FAILED quality check")
        previous_content = content
        if judge_result.feedback:
            print(f"    Feedback: {judge_result.feedback[:200]}...")
            previous_feedback = judge_result.feedback
        else:
            previous_feedback = (
                "The judge failed this explanation (score=0) without detailed feedback. "
                "Common causes: a technical segment has an empty or null `derivation_steps` "
                "or `equation_build_order`, fewer than the required `key_equations`, an "
                "equation symbol used without being defined via `new_symbol_introduced` or "
                "`what_it_means`, or no `example_substitution` with a computed numeric result. "
                "Review every technical segment against these requirements and fix any gaps."
            )

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
    return _truncate_at_word_boundary(narration, max_chars)
