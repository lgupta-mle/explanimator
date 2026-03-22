"""
Book Decomposer: extracts chapter and section structure from a book PDF.

Uses PyMuPDF (fitz) to:
1. Parse the embedded Table of Contents
2. Identify chapter/section page boundaries
3. Compute approximate token counts per chapter
4. Split oversized chapters at section boundaries
"""

import json
import re
from pathlib import Path
from statistics import median
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from pydantic import BaseModel

from research_viz.schemas.explanation_schemas import (
    BookChapter,
    BookChapterPart,
    BookSection,
)
from research_viz.config.book_config import BookConfig
from research_viz.utils.llm_utils import create_llm_response


# ---------------------------------------------------------------------------
# Internal schema for LLM-extracted TOC entries
# ---------------------------------------------------------------------------

class TocEntry(BaseModel):
    entry_type: str     # "part", "chapter", "section"
    number: str         # "1", "I", "1.1", "A", "" (empty if unnumbered)
    title: str
    logical_page: int   # page number as printed in the book

    @property
    def level(self) -> int:
        """Backward-compatible level mapping."""
        return {"part": 0, "chapter": 1, "section": 2}.get(self.entry_type, 1)


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    """Fast approximation: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


def _extract_page_text(doc: fitz.Document, start_page: int, end_page: int) -> str:
    """Extract and concatenate plain text from a page range (inclusive)."""
    parts = []
    for page_num in range(start_page, min(end_page + 1, len(doc))):
        parts.append(doc[page_num].get_text("text"))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# TOC parsing helpers
# ---------------------------------------------------------------------------

_BACK_MATTER_RE = re.compile(
    r'^(references?|bibliography|index|glossary|appendix|appendices'
    r'|foreword|preface|acknowledgements?|about\s+the\s+authors?)\s*$',
    re.IGNORECASE,
)


def _detect_chapter_level(
    entries: List[Tuple[int, str, int]],
) -> Tuple[int, int]:
    """Determine which TOC level represents chapters vs sections.

    Uses purely structural analysis — no assumptions about naming conventions.
    The key insight: if level-2 entries consistently have level-3 children,
    then level 1 is grouping (Parts) and level 2 is the chapter level.

    Returns ``(chapter_level, section_level)``.
    """
    levels = {l for l, _, _ in entries}
    if not levels:
        return (1, 2)
    max_depth = max(levels)

    if max_depth <= 2:
        return (1, 2)

    # For depth >= 3, check if level-2 entries have level-3 children
    l1_entries = [(t, p) for l, t, p in entries if l == 1]
    l2_entries = [(t, p) for l, t, p in entries if l == 2]
    l3_entries = [(t, p) for l, t, p in entries if l == 3]

    if not l2_entries or not l3_entries:
        return (1, 2)

    # Count how many L2 entries have at least one L3 child
    l2_with_children = 0
    for i, (_, p2) in enumerate(l2_entries):
        next_p2 = l2_entries[i + 1][1] if i + 1 < len(l2_entries) else float('inf')
        has_l3 = any(p2 <= p3 < next_p2 for _, p3 in l3_entries)
        if has_l3:
            l2_with_children += 1

    # If most L2 entries have L3 children, L2 is the chapter level
    # Secondary check: L1 should be few (grouping) vs L2 many (content)
    l2_ratio = l2_with_children / len(l2_entries)
    l1_few_l2_many = len(l2_entries) >= len(l1_entries) * 2

    if l2_ratio >= 0.5 and l1_few_l2_many:
        return (2, 3)  # L1=Parts, L2=Chapters, L3=Sections

    return (1, 2)  # Standard: L1=Chapters, L2=Sections


# ---------------------------------------------------------------------------
# Title-based chapter page detection
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    """Normalize a chapter title for fuzzy matching.

    Lowercases, collapses whitespace, and strips non-word punctuation
    (keeps periods for abbreviations like "Ch." or section numbers).
    """
    text = title.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s.]', '', text)
    return text


def _estimate_page_offset(doc: fitz.Document, sample_count: int = 10) -> Tuple[int, bool]:
    """Estimate the constant offset between printed page numbers and PDF page indices.

    Samples pages spread across the document and looks **only** for standalone
    digit blocks in the bottom 5 % of the page (footer zone).  This is
    intentionally conservative — it ignores running headers where chapter/
    section numbers could be confused with page numbers.

    Returns ``(offset, confident)`` where offset is ``pdf_page_idx -
    printed_page_number`` and confident indicates whether clean page numbers
    were actually found.
    """
    total = len(doc)
    if total == 0:
        return 0, False

    # Spread sample indices across the document (skip first/last few pages
    # which often have different formatting)
    step = max(1, total // (sample_count + 1))
    sample_indices = [step * (i + 1) for i in range(sample_count) if step * (i + 1) < total]
    if not sample_indices:
        sample_indices = list(range(min(total, sample_count)))

    offsets: List[int] = []
    for pdf_idx in sample_indices:
        page = doc[pdf_idx]
        height = page.rect.height
        width = page.rect.width
        footer_rect = fitz.Rect(0, height * 0.95, width, height)
        blocks = page.get_text("blocks", clip=footer_rect)
        for block in blocks:
            text = block[4].strip()
            if text.isdigit():
                num = int(text)
                if 0 < num <= total * 2:
                    offsets.append(pdf_idx - num)
                break  # one number per page is enough

    if not offsets:
        return 0, False
    return int(median(offsets)), True


def _calibrate_offset_from_first_chapter(
    doc: fitz.Document,
    first_chapter: "TocEntry",
    debug: bool = False,
) -> int:
    """Calibrate the page offset by finding the first chapter's heading in the PDF.

    Searches the entire document for the first chapter title using font-size
    scoring.  Returns ``found_pdf_page - logical_page`` as the offset.

    This is the fallback when ``_estimate_page_offset`` can't find standalone
    page numbers (e.g. books with page numbers embedded in running headers).
    """
    total = len(doc)
    norm_title = _normalize_title(first_chapter.title)
    if not norm_title:
        return 0

    best_page = -1
    best_score = -1

    for pdf_idx in range(total):
        page = doc[pdf_idx]
        page_height = page.rect.height
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if block.get("type") != 0:
                continue
            text_parts: List[str] = []
            max_size = 0.0
            top_y = block.get("bbox", [0, 0, 0, 0])[1]
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span["text"].strip()
                    if span_text:
                        text_parts.append(span_text)
                        max_size = max(max_size, span["size"])

            if not text_parts:
                continue
            raw = " ".join(text_parts)
            norm = _normalize_title(raw)
            if norm_title not in norm:
                continue

            # Score: strongly favor large headings over TOC listings or body text
            score = 0
            if max_size >= 18:    # likely a chapter heading
                score += 20
            elif max_size >= 14:  # large-ish heading
                score += 10
            if page_height > 0 and top_y < page_height * 0.4:
                score += 3

            # "Chapter N" label bonus
            ch_label = re.compile(
                rf'(chapter|ch\.?)\s*{re.escape(first_chapter.number)}',
                re.IGNORECASE,
            )
            if ch_label.search(raw):
                score += 5

            if debug:
                print(f"    [calibrate] page {pdf_idx}: score={score}  "
                      f"font={max_size:.1f}  text={raw[:80]!r}")

            if score > best_score:
                best_score = score
                best_page = pdf_idx

    if best_page >= 0 and best_score >= 10:
        offset = best_page - first_chapter.logical_page
        if debug:
            print(f"    [calibrate] Best match: page {best_page} (score={best_score}), "
                  f"offset = {best_page} - {first_chapter.logical_page} = {offset}")
        return offset
    return 0


def _find_chapter_page_by_title(
    doc: fitz.Document,
    title: str,
    chapter_number: str,
    logical_page_hint: int,
    search_radius: int = 20,
    debug: bool = False,
) -> Optional[int]:
    """Find the PDF page where a chapter begins by searching for its title text.

    Uses font-size analysis to distinguish headings from body-text mentions.
    ``logical_page_hint`` (0-indexed PDF page) narrows the search window.

    Returns a 0-indexed PDF page, or ``None`` if no confident match is found.
    """
    total = len(doc)
    norm_title = _normalize_title(title)
    if not norm_title:
        return None

    lo = max(0, logical_page_hint - search_radius)
    hi = min(total, logical_page_hint + search_radius + 1)

    # Compile chapter label regex once (constant across all pages)
    ch_label_re = re.compile(
        rf'(chapter|ch\.?)\s*{re.escape(chapter_number)}',
        re.IGNORECASE,
    )

    best_page: Optional[int] = None
    best_score = -1

    for pdf_idx in range(lo, hi):
        page = doc[pdf_idx]
        page_height = page.rect.height
        blocks = page.get_text("dict")["blocks"]

        # Single pass: collect font sizes AND per-block info simultaneously
        all_sizes: List[float] = []
        block_infos: List[Tuple[str, str, float, float]] = []  # (raw_text, norm_text, max_size, top_y)

        for block in blocks:
            if block.get("type") != 0:
                continue
            text_parts: List[str] = []
            max_size = 0.0
            top_y = block.get("bbox", [0, 0, 0, 0])[1]
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span["text"].strip()
                    if span_text:
                        text_parts.append(span_text)
                        size = span["size"]
                        all_sizes.append(size)
                        max_size = max(max_size, size)
            if text_parts:
                raw = " ".join(text_parts)
                block_infos.append((raw, _normalize_title(raw), max_size, top_y))

        if not all_sizes:
            continue
        median_size = sorted(all_sizes)[len(all_sizes) // 2]

        # Score each block that contains the title
        for raw_text, norm_block, block_max_size, block_top in block_infos:
            if norm_title not in norm_block:
                continue

            score = 10  # base: title matched

            if median_size > 0 and block_max_size >= median_size * 1.3:
                score += 5
            if page_height > 0 and block_top < page_height * 0.4:
                score += 3
            if ch_label_re.search(raw_text):
                score += 2

            score -= min(abs(pdf_idx - logical_page_hint), 10)

            if debug:
                print(f"    [title-search] page {pdf_idx}: score={score}  "
                      f"font={block_max_size:.1f} (median={median_size:.1f})  "
                      f"top={block_top:.0f}/{page_height:.0f}  "
                      f"text={raw_text[:80]!r}")

            if score > best_score:
                best_score = score
                best_page = pdf_idx

    # Require a minimum confidence threshold
    if best_score >= 5:
        return best_page
    return None


# ---------------------------------------------------------------------------
# TOC page detection (heuristic)
# ---------------------------------------------------------------------------

_TOC_HEADING_KEYWORDS = frozenset({
    "contents", "table of contents",
    "index", "indexes",
    "topics",
    "chapters",
    "outline",
})

_LINE_ENDS_WITH_NUMBER = re.compile(r'\d+\s*$')


def _detect_toc_pages(
    doc: fitz.Document,
    max_scan: int = 30,
) -> Optional[Tuple[int, int]]:
    """Find the start and end pages of the Table of Contents.

    Scans the first ``max_scan`` pages for a large-font heading that matches
    a known TOC keyword (e.g. "Contents", "Table of Contents", "Index").
    Then walks forward to find where the TOC ends (pages stop having lines
    that end with page numbers).

    Returns ``(toc_start, toc_end)`` as 0-indexed PDF page indices, or
    ``None`` if no TOC heading is found.
    """
    total = len(doc)
    toc_start: Optional[int] = None

    # Phase 1: Find the TOC heading page
    for page_idx in range(min(max_scan, total)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            max_size = 0.0
            text_parts: List[str] = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = span["text"].strip()
                    if t:
                        text_parts.append(t)
                        max_size = max(max_size, span["size"])
            if max_size >= 16:
                block_text = " ".join(text_parts).lower().strip()
                if block_text in _TOC_HEADING_KEYWORDS:
                    toc_start = page_idx
                    break
        if toc_start is not None:
            break

    if toc_start is None:
        return None

    # Phase 2: Find where the TOC ends
    # TOC pages have many lines ending with page numbers
    toc_end = toc_start
    for page_idx in range(toc_start, min(toc_start + 20, total)):
        text = doc[page_idx].get_text("text")
        lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
        numbered_lines = sum(1 for ln in lines if _LINE_ENDS_WITH_NUMBER.search(ln))
        if numbered_lines >= 3 or page_idx == toc_start:
            toc_end = page_idx
        else:
            break

    print(f"  TOC detected: pages {toc_start}–{toc_end} (PDF 0-indexed)")
    return (toc_start, toc_end)


# ---------------------------------------------------------------------------
# LLM-based TOC extraction
# ---------------------------------------------------------------------------

_TOC_MODEL = "google/gemini-3.1-pro-preview"

_EXERCISE_SECTION_RE = re.compile(
    r'^(exercises?|problems?|practice\s+problems?|exercises?\s+and\s+problems?'
    r'|end-of-chapter|summary\s+and\s+exercises?)\s*$',
    re.IGNORECASE,
)

_TOC_SYSTEM_PROMPT = (
    "You are extracting a structured table of contents from a book. "
    "Return ONLY a JSON array with no markdown formatting. "
    "Each entry must have: "
    '{"entry_type": "part"|"chapter"|"section", "number": "...", "title": "...", "logical_page": N}. '
    "\n\n"
    'entry_type "part": Grouping dividers that organize the book into sections '
    '(e.g., "Part I: Foundations", "Part II: Advanced Topics"). These are NOT '
    "content — they are just organizational labels. If a book's top-level "
    'divisions ARE the content (no further subdivision), label them "chapter".\n'
    'entry_type "chapter": The main content divisions of the book. These may be '
    'called "Chapter", "Part", "Unit", "Lecture", "Module", "Topic", or have no '
    "label at all — what matters is that they are the primary divisions "
    "containing the book's actual content.\n"
    'entry_type "section": Subdivisions within a chapter (e.g., "1.1 Overview", '
    '"2.3 Methods").\n'
    "\n"
    "RULES:\n"
    "- Use the PRINTED page number (as shown in the TOC), not the PDF page index.\n"
    "- Only include entries whose page number is an arabic numeral (integer).\n"
    "- Skip front matter with roman numeral page numbers (Preface, Contents page itself, etc.).\n"
    "- Skip back matter like References, Bibliography, Index, Glossary, Appendix.\n"
    "- If a chapter has no number, use an empty string for the number field.\n"
    "- If no table of contents is found in the text, return []."
)


def _extract_toc_with_llm(
    raw_text: str,
    model_name: str = _TOC_MODEL,
    cache_path: Optional[str] = None,
) -> List[TocEntry]:
    """Send TOC page text to an LLM and parse out structured TOC entries."""
    # Load from cache if available (with schema migration check)
    if cache_path and Path(cache_path).exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if raw and isinstance(raw[0], dict) and "level" in raw[0] and "entry_type" not in raw[0]:
            print(f"  Stale TOC cache (old schema without entry_type) — re-extracting...")
            Path(cache_path).unlink()
        else:
            print(f"  Loading TOC from cache: {cache_path}")
            return [TocEntry(**e) for e in raw]

    print(f"  Calling {model_name} for TOC extraction...")
    content = create_llm_response(
        prepared_usr_prompt=f"Here is the table of contents from a book:\n\n{raw_text}",
        system_prompt=_TOC_SYSTEM_PROMPT,
        model_name=model_name,
    )

    if not content:
        print("  Warning: LLM returned no content for TOC extraction")
        return []

    entries: List[TocEntry] = []
    try:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[^\n]*\n", "", content)
            content = re.sub(r"\n```$", "", content.strip())
        raw_list = json.loads(content)
        entries = [TocEntry(**e) for e in raw_list if isinstance(e, dict)]
    except Exception as exc:
        print(f"  Warning: could not parse LLM TOC response: {exc}")
        return []

    # Only cache non-empty results to avoid poisoning future runs
    if entries and cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump([e.model_dump() for e in entries], f, indent=2)
        print(f"  TOC cached to: {cache_path}")

    return entries


def _chapters_from_text_toc(
    doc: fitz.Document,
    total_pages: int,
    toc_page_range: Tuple[int, int],
    model_name: str = _TOC_MODEL,
    cache_path: Optional[str] = None,
    book_config: Optional[BookConfig] = None,
) -> List[BookChapter]:
    """
    Extract chapter structure using:
    1. Raw text from the detected TOC pages → LLM parses structured TOC entries
    2. Title-text search with font-size scoring to locate each chapter's PDF page
    """
    debug = book_config.debug_chapter_detection if book_config else False

    # Step 1: extract raw text from detected TOC pages
    toc_start, toc_end = toc_page_range
    raw_text = "".join(
        doc[i].get_text("text") for i in range(toc_start, min(toc_end + 1, total_pages))
    )
    if not raw_text.strip():
        return []

    # Step 2: LLM extracts TOC entries
    toc_entries = _extract_toc_with_llm(raw_text, model_name=model_name, cache_path=cache_path)
    if not toc_entries:
        print("  LLM found no TOC entries")
        return []

    chapter_entries = [e for e in toc_entries if e.entry_type == "chapter"]
    section_entries = [e for e in toc_entries if e.entry_type == "section"]
    part_entries = [e for e in toc_entries if e.entry_type == "part"]

    # Filter out back matter that the LLM may have labeled as "chapter"
    _BACK_MATTER_RE = re.compile(
        r'^(references?|bibliography|index|glossary|appendix|appendices|about\s+the\s+authors?)\s*$',
        re.IGNORECASE,
    )
    back_matter = [e for e in chapter_entries if _BACK_MATTER_RE.match(e.title.strip())]
    chapter_entries = [e for e in chapter_entries if not _BACK_MATTER_RE.match(e.title.strip())]

    excluded_parts = []
    if part_entries:
        excluded_parts.append(f"{len(part_entries)} parts")
    if back_matter:
        excluded_parts.append(f"{len(back_matter)} back matter ({', '.join(e.title for e in back_matter)})")
    excluded_str = f", excluded: {', '.join(excluded_parts)}" if excluded_parts else ""
    print(f"  LLM TOC: {len(chapter_entries)} chapters, {len(section_entries)} sections{excluded_str}")

    if not chapter_entries:
        return []

    # Step 3: estimate page offset (printed page → PDF page)
    page_offset, offset_confident = _estimate_page_offset(doc)
    if offset_confident:
        print(f"  Estimated page offset: {page_offset} (from standalone footer numbers)")
    else:
        print(f"  No standalone page numbers found — calibrating from first chapter heading...")
        page_offset = _calibrate_offset_from_first_chapter(
            doc, chapter_entries[0], debug=debug,
        )
        print(f"  Calibrated page offset: {page_offset} (from first chapter title match)")

    _page_cache: dict[Tuple[str, str, int, int], int] = {}

    def _resolve_page(title: str, chapter_number: str, logical_page: int,
                      search_radius: int = 20) -> int:
        """Resolve a logical page to a PDF page via title search, with fallback.

        Results are cached by (title, chapter_number, logical_page, search_radius)
        to avoid redundant PDF text extraction for adjacent chapter/section boundaries.
        """
        key = (title, chapter_number, logical_page, search_radius)
        if key in _page_cache:
            return _page_cache[key]
        hint = max(0, min(logical_page + page_offset, total_pages - 1))
        found = _find_chapter_page_by_title(
            doc, title, chapter_number, hint,
            search_radius=search_radius, debug=debug,
        )
        if found is not None:
            _page_cache[key] = found
            return found
        if debug:
            print(f"    [title-search] No match for {title!r}, using offset fallback → page {hint}")
        _page_cache[key] = hint
        return hint

    # Step 4: resolve Part divider page numbers (to cap chapter ranges)
    part_pages: List[int] = []
    for p in part_entries:
        hint = max(0, min(p.logical_page + page_offset, total_pages - 1))
        found = _find_chapter_page_by_title(
            doc, p.title, p.number, hint, search_radius=5, debug=debug,
        )
        page = found if found is not None else hint
        part_pages.append(page)
        if debug:
            print(f"  Part divider '{p.title}' → PDF page {page}")
    part_pages.sort()
    if part_pages:
        print(f"  Part divider pages: {part_pages}")

    # Step 5: build BookChapter objects
    chapter_entries.sort(key=lambda e: e.logical_page)
    chapters: List[BookChapter] = []

    for idx, ch_entry in enumerate(chapter_entries):
        ch_start = _resolve_page(ch_entry.title, ch_entry.number, ch_entry.logical_page)
        if idx + 1 < len(chapter_entries):
            next_entry = chapter_entries[idx + 1]
            next_start = _resolve_page(next_entry.title, next_entry.number, next_entry.logical_page)
            ch_end = max(ch_start, next_start - 1)
        else:
            ch_end = total_pages - 1

        # Cap chapter end at the first Part divider that falls within the range
        # (Part intro pages after the divider belong to the Part, not the chapter)
        for pp in part_pages:
            if ch_start < pp <= ch_end:
                ch_end = pp - 1
                break

        # Parse chapter number from entry.number (handles "1", "I", "A", etc.)
        try:
            ch_num = int(ch_entry.number)
        except ValueError:
            ch_num = idx + 1

        ch_id = f"ch_{ch_num:02d}"
        print(f"  Chapter {ch_num}: '{ch_entry.title}' → PDF pages {ch_start}–{ch_end}")

        # Find sections for this chapter (narrower search radius)
        ch_sections = [
            s for s in section_entries
            if s.number.startswith(f"{ch_entry.number}.")
            or (s.logical_page >= ch_entry.logical_page
                and (idx + 1 >= len(chapter_entries)
                     or s.logical_page < chapter_entries[idx + 1].logical_page))
        ]
        sections: List[BookSection] = []
        for s_idx, s_entry in enumerate(ch_sections):
            s_start = _resolve_page(s_entry.title, s_entry.number, s_entry.logical_page,
                                    search_radius=10)
            # Clamp section start within the chapter range
            s_start = max(ch_start, min(s_start, ch_end))
            if s_idx + 1 < len(ch_sections):
                s_next = _resolve_page(ch_sections[s_idx + 1].title,
                                       ch_sections[s_idx + 1].number,
                                       ch_sections[s_idx + 1].logical_page,
                                       search_radius=10)
                s_next = max(ch_start, min(s_next, ch_end))
                s_end = max(s_start, s_next - 1)
            else:
                s_end = ch_end
            sec_text = _extract_page_text(doc, s_start, s_end)
            sections.append(BookSection(
                section_id=s_entry.number,
                title=s_entry.title,
                start_page=s_start,
                end_page=s_end,
                token_count=_approx_tokens(sec_text),
            ))

        # Filter out exercise/bibliographical sections and trim chapter end
        if book_config is None or book_config.skip_exercises:
            sections, ch_end = _trim_exercise_sections(sections, ch_end)

        ch_text = _extract_page_text(doc, ch_start, ch_end)
        chapters.append(BookChapter(
            chapter_id=ch_id,
            title=ch_entry.title,
            chapter_number=ch_num,
            start_page=ch_start,
            end_page=ch_end,
            sections=sections,
            token_count=_approx_tokens(ch_text),
        ))

    return chapters


def _trim_exercise_sections(
    sections: List[BookSection],
    ch_end: int,
) -> Tuple[List[BookSection], int]:
    """Remove exercise sections and trim ch_end accordingly."""
    for i, sec in enumerate(sections):
        if _EXERCISE_SECTION_RE.match(sec.title.strip()):
            trimmed_end = max(sec.start_page - 1, sections[i - 1].end_page if i > 0 else ch_end)
            return sections[:i], trimmed_end
    return sections, ch_end


# ---------------------------------------------------------------------------
# Core decomposition
# ---------------------------------------------------------------------------

def extract_chapters(
    pdf_path: str,
    model_name: str = _TOC_MODEL,
    toc_cache_path: Optional[str] = None,
    book_config: Optional[BookConfig] = None,
) -> List[BookChapter]:
    """
    Extract chapter structure from a book PDF.

    Tries two strategies in order:
    1. Embedded PDF TOC metadata (doc.get_toc) — instant, no API call
    2. Detect TOC pages heuristically, then LLM extraction + title-text search

    Raises ValueError if no Table of Contents can be found.

    Args:
        pdf_path: Path to the book PDF.
        model_name: Model used for LLM TOC extraction (strategy 2).
        toc_cache_path: Optional path to cache/load the LLM TOC JSON result.
                        Defaults to <pdf_path>.toc.json next to the PDF.

    Returns a list of BookChapter objects with section structure and token counts.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # Default cache: <pdf_stem>.toc.json next to the PDF
    if toc_cache_path is None:
        toc_cache_path = str(Path(pdf_path).with_suffix(".toc.json"))

    # Strategy 1: embedded TOC metadata
    toc = doc.get_toc(simple=False)
    if toc:
        print("  Using embedded PDF TOC metadata")
        chapters = _chapters_from_toc(doc, toc, total_pages)
        doc.close()
        return chapters

    # Strategy 2: detect TOC pages, then LLM extraction + title-text search
    print("  No embedded TOC — detecting Table of Contents pages...")

    # Check if we have a valid cache (skip page detection if so)
    has_valid_cache = False
    if toc_cache_path and Path(toc_cache_path).exists():
        try:
            with open(toc_cache_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if raw and isinstance(raw[0], dict) and "entry_type" in raw[0]:
                has_valid_cache = True
        except Exception:
            pass

    if has_valid_cache:
        # Cache exists with new schema — we still need a toc_page_range for
        # the function signature, but it won't be used (cache is loaded).
        # Use a dummy range; _extract_toc_with_llm will return from cache.
        toc_page_range = (0, 0)
    else:
        toc_result = _detect_toc_pages(doc)
        if toc_result is None:
            doc.close()
            raise ValueError(
                "Could not find a Table of Contents in this book. "
                "Looked for headings like 'Contents', 'Table of Contents', "
                "'Index', 'Topics', 'Chapters', or 'Outline' in the first "
                "30 pages.\n"
                "Please ensure your book PDF has a clearly titled contents page."
            )
        toc_page_range = toc_result

    chapters = _chapters_from_text_toc(
        doc, total_pages,
        toc_page_range=toc_page_range,
        model_name=model_name,
        cache_path=toc_cache_path,
        book_config=book_config,
    )
    doc.close()

    if not chapters:
        raise ValueError(
            "Table of Contents was found but no chapters could be extracted. "
            "The LLM may have failed to parse the TOC structure. "
            "Try deleting the cache file and re-running."
        )

    return chapters


def _chapters_from_toc(
    doc: fitz.Document, toc: list, total_pages: int
) -> List[BookChapter]:
    """Build BookChapter list from an embedded PDF TOC.

    Uses structural analysis to determine which TOC level represents
    chapters vs sections vs grouping (Parts). No naming assumptions.
    """
    # PyMuPDF TOC entries: [level, title, page_1indexed, ...]
    # Convert to 0-indexed pages
    entries = [(e[0], e[1].strip(), e[2] - 1) for e in toc]

    # Detect which level represents chapters
    chapter_level, section_level = _detect_chapter_level(entries)
    print(f"  TOC structure: chapter_level={chapter_level}, section_level={section_level}")

    # Extract chapter entries at the detected level, filtering back matter and exercises
    chapter_entries: List[Tuple[str, int]] = [
        (title, max(0, page))
        for level, title, page in entries
        if level == chapter_level
        and not _BACK_MATTER_RE.match(title.strip())
        and not _EXERCISE_SECTION_RE.match(title.strip())
    ]

    if not chapter_entries:
        return []

    # Identify grouping divider pages (levels above chapter_level) to cap chapter ranges
    grouping_pages: List[int] = []
    if chapter_level > 1:
        for level, title, page in entries:
            if level < chapter_level:
                grouping_pages.append(max(0, page))
        grouping_pages.sort()
        if grouping_pages:
            print(f"  Grouping divider pages: {grouping_pages}")

    chapters: List[BookChapter] = []
    for idx, (ch_title, ch_start) in enumerate(chapter_entries):
        ch_end = (
            chapter_entries[idx + 1][1] - 1
            if idx + 1 < len(chapter_entries)
            else total_pages - 1
        )

        # Cap chapter end at the first grouping divider that falls within the range
        for gp in grouping_pages:
            if ch_start < gp <= ch_end:
                ch_end = gp - 1
                break

        ch_num = idx + 1
        ch_id = f"ch_{ch_num:02d}"

        # Find sections belonging to this chapter
        sections = _sections_for_chapter(
            doc, entries, ch_start, ch_end, ch_id, ch_num, section_level
        )

        chapter_text = _extract_page_text(doc, ch_start, ch_end)
        token_count = _approx_tokens(chapter_text)

        chapters.append(
            BookChapter(
                chapter_id=ch_id,
                title=ch_title,
                chapter_number=ch_num,
                start_page=ch_start,
                end_page=ch_end,
                sections=sections,
                token_count=token_count,
            )
        )

    return chapters


def _sections_for_chapter(
    doc: fitz.Document,
    toc_entries: list,
    ch_start: int,
    ch_end: int,
    ch_id: str,
    ch_number: int,
    section_level: int = 2,
) -> List[BookSection]:
    """Extract sections within a chapter's page range from the TOC."""
    section_entries = [
        (level, title, page)
        for level, title, page in toc_entries
        if level == section_level
        and ch_start <= page <= ch_end
    ]

    sections: List[BookSection] = []
    for s_idx, (_, s_title, s_start) in enumerate(section_entries):
        s_end = (
            section_entries[s_idx + 1][2] - 1
            if s_idx + 1 < len(section_entries)
            else ch_end
        )
        sec_text = _extract_page_text(doc, s_start, s_end)
        sections.append(
            BookSection(
                section_id=f"{ch_number}.{s_idx + 1}",
                title=s_title,
                start_page=s_start,
                end_page=s_end,
                token_count=_approx_tokens(sec_text),
            )
        )
    return sections


def _chapters_from_headings(doc: fitz.Document) -> List[BookChapter]:
    """
    Fallback: detect chapter boundaries via font-size based heading detection.
    Identifies the largest repeated font sizes as chapter headings.
    """
    total_pages = len(doc)

    # Collect all text spans with their font sizes
    heading_candidates: List[Tuple[int, str, float]] = []  # (page, text, size)
    for page_num in range(total_pages):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    size = span["size"]
                    if text and size > 14:
                        heading_candidates.append((page_num, text, size))

    if not heading_candidates:
        # Ultimate fallback: treat every 20 pages as a chapter
        chapter_starts = list(range(0, total_pages, 20))
        chapters = []
        for idx, start in enumerate(chapter_starts):
            end = chapter_starts[idx + 1] - 1 if idx + 1 < len(chapter_starts) else total_pages - 1
            text = _extract_page_text(doc, start, end)
            chapters.append(
                BookChapter(
                    chapter_id=f"ch_{idx + 1:02d}",
                    title=f"Chapter {idx + 1}",
                    chapter_number=idx + 1,
                    start_page=start,
                    end_page=end,
                    sections=[],
                    token_count=_approx_tokens(text),
                )
            )
        return chapters

    # Find the dominant large font size (chapter heading size)
    sizes = sorted({s for _, _, s in heading_candidates}, reverse=True)
    chapter_font_size = sizes[0]

    chapter_pages = sorted({
        page for page, text, size in heading_candidates
        if size >= chapter_font_size * 0.95
    })

    if not chapter_pages:
        chapter_pages = [0]

    chapters = []
    for idx, ch_start in enumerate(chapter_pages):
        ch_end = chapter_pages[idx + 1] - 1 if idx + 1 < len(chapter_pages) else total_pages - 1
        # Get the heading text for this chapter
        ch_title = next(
            (text for page, text, size in heading_candidates
             if page == ch_start and size >= chapter_font_size * 0.95),
            f"Chapter {idx + 1}"
        )
        text = _extract_page_text(doc, ch_start, ch_end)
        chapters.append(
            BookChapter(
                chapter_id=f"ch_{idx + 1:02d}",
                title=ch_title,
                chapter_number=idx + 1,
                start_page=ch_start,
                end_page=ch_end,
                sections=[],
                token_count=_approx_tokens(text),
            )
        )
    return chapters


# ---------------------------------------------------------------------------
# Chapter splitting
# ---------------------------------------------------------------------------

def split_chapter_if_needed(
    chapter: BookChapter,
    config: BookConfig,
) -> List[BookChapterPart]:
    """
    If a chapter exceeds max_tokens_per_chunk, split it at section boundaries.

    Returns a list of BookChapterPart objects. If the chapter fits in the budget,
    returns a single part covering the whole chapter.
    """
    if chapter.token_count <= config.max_tokens_per_chunk:
        return [
            BookChapterPart(
                part_id=f"{chapter.chapter_id}_part_1",
                chapter_id=chapter.chapter_id,
                part_number=1,
                title=chapter.title,
                start_page=chapter.start_page,
                end_page=chapter.end_page,
                sections=chapter.sections,
                token_count=chapter.token_count,
            )
        ]

    # Need to split — use section boundaries
    if not chapter.sections:
        # No sections available: fallback to page-based halving
        return _split_by_pages(chapter, config)

    return _split_by_sections(chapter, config)


def _split_by_sections(
    chapter: BookChapter, config: BookConfig
) -> List[BookChapterPart]:
    """Greedily pack sections into parts respecting the token budget."""
    parts: List[BookChapterPart] = []
    current_sections: List[BookSection] = []
    current_tokens = 0
    part_number = 1

    for section in chapter.sections:
        if (
            current_tokens + section.token_count > config.max_tokens_per_chunk
            and current_sections
        ):
            # Flush current part
            parts.append(_make_part(chapter, current_sections, part_number))
            part_number += 1
            current_sections = []
            current_tokens = 0

        current_sections.append(section)
        current_tokens += section.token_count

    # Flush remaining
    if current_sections:
        parts.append(_make_part(chapter, current_sections, part_number))

    # Retitle multi-part chapters
    if len(parts) > 1:
        for p in parts:
            p.title = f"{chapter.title}, Part {p.part_number}"

    return parts


def _make_part(
    chapter: BookChapter,
    sections: List[BookSection],
    part_number: int,
) -> BookChapterPart:
    return BookChapterPart(
        part_id=f"{chapter.chapter_id}_part_{part_number}",
        chapter_id=chapter.chapter_id,
        part_number=part_number,
        title=chapter.title,
        start_page=sections[0].start_page,
        end_page=sections[-1].end_page,
        sections=sections,
        token_count=sum(s.token_count for s in sections),
    )


def _split_by_pages(
    chapter: BookChapter, config: BookConfig
) -> List[BookChapterPart]:
    """Fallback page-based split when no section info is available."""
    total_pages = chapter.end_page - chapter.start_page + 1
    # Estimate pages per part based on token budget
    avg_tokens_per_page = max(1, chapter.token_count // total_pages)
    pages_per_part = max(1, config.max_tokens_per_chunk // avg_tokens_per_page)

    parts = []
    part_number = 1
    current_start = chapter.start_page

    while current_start <= chapter.end_page:
        current_end = min(current_start + pages_per_part - 1, chapter.end_page)
        parts.append(
            BookChapterPart(
                part_id=f"{chapter.chapter_id}_part_{part_number}",
                chapter_id=chapter.chapter_id,
                part_number=part_number,
                title=f"{chapter.title}, Part {part_number}",
                start_page=current_start,
                end_page=current_end,
                sections=[],
                token_count=(current_end - current_start + 1) * avg_tokens_per_page,
            )
        )
        current_start = current_end + 1
        part_number += 1

    return parts


# ---------------------------------------------------------------------------
# Sub-PDF extraction
# ---------------------------------------------------------------------------

def extract_sub_pdf(
    source_pdf_path: str,
    start_page: int,
    end_page: int,
    output_path: str,
) -> str:
    """
    Extract pages [start_page, end_page] (0-indexed, inclusive) from source PDF
    and save as a new PDF at output_path. Returns output_path.
    """
    doc = fitz.open(source_pdf_path)
    sub_doc = fitz.open()
    sub_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sub_doc.save(output_path)
    sub_doc.close()
    doc.close()
    return output_path


# ---------------------------------------------------------------------------
# TOC text extraction (for the series bible)
# ---------------------------------------------------------------------------

def extract_toc_text(
    pdf_path: str,
    snippet_pages: int = 2,
    toc_cache_path: Optional[str] = None,
) -> str:
    """
    Extract the Table of Contents as a structured text string, plus the first
    `snippet_pages` pages of each chapter. Used as input to the series bible.

    Uses extract_chapters() for accurate chapter page ranges (including page
    offset calibration and LLM-extracted TOC cache if available).
    """
    doc = fitz.open(pdf_path)

    # Build TOC listing from embedded PDF TOC for display
    toc = doc.get_toc(simple=False)
    lines = ["=== TABLE OF CONTENTS ==="]
    for level, title, page in toc:
        indent = "  " * (level - 1)
        lines.append(f"{indent}{title} (p.{page})")

    lines.append("\n=== CHAPTER SNIPPETS ===")

    # Use extract_chapters for accurate, calibrated page ranges
    try:
        chapters = extract_chapters(
            pdf_path,
            toc_cache_path=toc_cache_path,
        )
    except Exception:
        # Fallback: direct embedded TOC (less accurate but better than nothing)
        chapters = _chapters_from_toc(doc, toc, len(doc)) if toc else _chapters_from_headings(doc)

    for ch in chapters:
        snippet_end = min(ch.start_page + snippet_pages - 1, ch.end_page)
        snippet_text = _extract_page_text(doc, ch.start_page, snippet_end)
        lines.append(f"\n--- {ch.title} ---")
        lines.append(snippet_text[:1500])  # cap per-chapter snippet

    doc.close()
    return "\n".join(lines)
