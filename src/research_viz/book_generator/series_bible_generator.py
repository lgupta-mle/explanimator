"""
Series Bible Generator: one LLM call over TOC + chapter snippets → SeriesBible.

The series bible defines the shared running example and notation glossary
that ALL chapter videos must use to stay consistent.
"""

import json
from typing import Optional

from research_viz.schemas.explanation_schemas import SeriesBible
from research_viz.utils.llm_utils import call_openrouter
from research_viz.book_generator.book_decomposer import extract_toc_text


_SYSTEM_PROMPT = """\
You are an expert educational content designer specialising in producing \
3Blue1Brown-style video series from technical books on any mathematical, \
scientific, or engineering topic.

Your job is to read a book's Table of Contents and chapter snippets, then \
produce a "series bible" that ALL chapter videos in the series must follow. \
The bible ensures every video feels like part of a coherent series rather \
than isolated episodes.

Be concrete and specific — vague bibles produce inconsistent videos.\
"""

_USER_PROMPT_TEMPLATE = """\
Below is the Table of Contents and opening snippets from a book.
Based on this, produce a series bible as a JSON object.

{toc_text}

---

Produce a JSON object with these fields:

- book_title (string): The full title of the book.

- series_running_example (string): ONE concrete, tangible example that can be \
carried through EVERY chapter video. It must be rich enough to illustrate \
concepts from any chapter. For a deep-learning book this might be \
"training a 2-layer MLP to classify handwritten MNIST digits". \
For a biomedical book this might be "tracking glucose levels in a \
Type-2 diabetic patient over 24 hours". Choose something maximally \
illustrative of the book's domain.

- notation_glossary (object): A mapping of mathematical symbol → plain-English \
meaning for the 10–20 most important symbols used across the book \
(e.g. {{"W": "weight matrix", "sigma": "activation function", \
"nabla": "gradient operator"}}). Prioritise symbols that appear in \
multiple chapters.

- visual_style_notes (string): 1–3 sentences describing a consistent visual \
style for all videos (e.g. colour palette, whether to use dark/light \
background, animation style). Keep it brief but concrete.

- chapter_briefs (object): A mapping of chapter_id → one-sentence description \
of what that chapter covers. Use chapter_id format "ch_01", "ch_02", etc. \
matching the order chapters appear in the book.

Output ONLY valid JSON. No markdown fences, no extra text.
"""


def generate_series_bible(
    pdf_path: str,
    model_name: str = "google/gemini-2.5-pro",
    snippet_pages: int = 2,
    toc_cache_path: Optional[str] = None,
) -> Optional[SeriesBible]:
    """
    Generate a SeriesBible from a book PDF.

    Only reads the TOC and the first `snippet_pages` pages of each chapter —
    not the full book text. This is cheap and fast.

    Args:
        pdf_path: Path to the book PDF.
        model_name: LLM model to use.
        snippet_pages: How many pages per chapter to include in the prompt.
        toc_cache_path: Optional path to the LLM-extracted TOC JSON cache.

    Returns:
        SeriesBible instance, or None on failure.
    """
    print(f"  Extracting TOC and chapter snippets from: {pdf_path}")
    toc_text = extract_toc_text(pdf_path, snippet_pages=snippet_pages, toc_cache_path=toc_cache_path)
    print(f"  TOC + snippets: {len(toc_text)} chars (~{len(toc_text)//4} tokens)")

    user_prompt = _USER_PROMPT_TEMPLATE.format(toc_text=toc_text)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for attempt in range(3):
        print(f"  Calling LLM ({model_name}) for series bible (attempt {attempt + 1}/3)...")
        response = call_openrouter(messages, model_name, SeriesBible)

        if "error" in response:
            print(f"  Series bible LLM error: {response['error']}")
            continue

        choices = response.get("choices", [])
        if not choices:
            print(f"  Series bible: no choices in response: {response}")
            continue

        content = choices[0]["message"]["content"]

        if not content:
            msg = choices[0].get("message", {})
            finish = choices[0].get("finish_reason", "unknown")
            refusal = msg.get("refusal")
            print(f"  Series bible: empty content (finish_reason={finish!r}, refusal={refusal!r})")
            print(f"  Full message: {msg}")
            continue

        try:
            bible = SeriesBible.model_validate_json(content)
            print(f"  Series bible generated:")
            print(f"    Book: {bible.book_title}")
            print(f"    Running example: {bible.series_running_example[:100]}...")
            print(f"    Notation symbols: {list(bible.notation_glossary.keys())}")
            print(f"    Chapter briefs: {len(bible.chapter_briefs)} chapters")
            return bible
        except Exception as e:
            # Fallback: try raw JSON parse
            try:
                data = json.loads(content)
                bible = SeriesBible(**data)
                return bible
            except Exception as e2:
                print(f"  Failed to parse series bible: {e} / {e2}")
                print(f"  Raw content: {content[:500]}")
                continue

    print(f"  Series bible generation failed after 3 attempts")
    return None
