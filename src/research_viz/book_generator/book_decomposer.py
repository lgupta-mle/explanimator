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
from typing import Dict, List, Optional, Tuple

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
    level: int          # 1 = chapter, 2 = section
    number: str         # "1", "2", "1.1", "A"
    title: str
    logical_page: int   # page number as printed in the book


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

_CHAPTER_PATTERN = re.compile(
    r"^(chapter|ch\.?|part|unit|lecture|module|section)\s*(\d+)",
    re.IGNORECASE,
)
_SECTION_PATTERN = re.compile(r"^(\d+)\.(\d+)(\.\d+)?")


def _toc_level_is_chapter(title: str, level: int) -> bool:
    """Heuristic: decide if a TOC entry is a top-level chapter."""
    if level == 1:
        return True
    if _CHAPTER_PATTERN.match(title.strip()):
        return True
    return False


def _toc_level_is_section(title: str, level: int) -> bool:
    """Heuristic: decide if a TOC entry is a section within a chapter."""
    if level == 2:
        return True
    if _SECTION_PATTERN.match(title.strip()):
        return True
    return False


# ---------------------------------------------------------------------------
# Page number map: printed page number → PDF 0-indexed page
# ---------------------------------------------------------------------------

_PAGE_NUM_RE = re.compile(r'\b(\d{1,4})\b')


def _build_page_number_map(doc: fitz.Document) -> Dict[int, int]:
    """
    Scan every PDF page's header and footer zone (top/bottom 7%) for a printed
    page number. Returns {printed_page: pdf_page_0idx}.

    Two-pass per block:
    1. Whole block is a pure integer (standalone number).
    2. Fallback: extract all 1-4 digit numbers from the block and take the last
       one — covers running titles like "The RL Problem   3".
    First occurrence of each printed number wins.
    """
    total = len(doc)
    page_map: Dict[int, int] = {}
    for pdf_idx in range(total):
        page = doc[pdf_idx]
        height = page.rect.height
        width = page.rect.width
        header_rect = fitz.Rect(0, 0, width, height * 0.07)
        footer_rect = fitz.Rect(0, height * 0.93, width, height)
        found = False
        for zone in (header_rect, footer_rect):
            if found:
                break
            blocks = page.get_text("blocks", clip=zone)
            for block in blocks:
                text = block[4].strip()
                # Pass 1: whole block is a number
                if text.isdigit():
                    num = int(text)
                    if 0 < num <= total * 2 and num not in page_map:
                        page_map[num] = pdf_idx
                    found = True
                    break
                # Pass 2: number embedded in running title — take last match
                matches = _PAGE_NUM_RE.findall(text)
                if matches:
                    num = int(matches[-1])
                    if 0 < num <= total * 2 and num not in page_map:
                        page_map[num] = pdf_idx
                    found = True
                    break
    return page_map


def _nearest_mapped_page(page_map: Dict[int, int], logical: int, total_pages: int) -> int:
    """Return the pdf page for `logical`, falling back to nearest mapped number."""
    if logical in page_map:
        return page_map[logical]
    # Search outward from logical page number
    for delta in range(1, 20):
        if (logical + delta) in page_map:
            return page_map[logical + delta]
        if (logical - delta) in page_map and logical - delta > 0:
            return page_map[logical - delta]
    return min(logical, total_pages - 1)


# ---------------------------------------------------------------------------
# LLM-based TOC extraction
# ---------------------------------------------------------------------------

_TOC_MODEL = "google/gemini-3.1-pro-preview"

_EXERCISE_SECTION_RE = re.compile(
    r'^(exercises?|problems?|practice\s+problems?|exercises?\s+and\s+problems?'
    r'|bibliographical\s+remarks?|further\s+reading|notes?\s+and\s+references?'
    r'|chapter\s+notes?|end-of-chapter|summary\s+and\s+exercises?)\s*$',
    re.IGNORECASE,
)

_TOC_SYSTEM_PROMPT = (
    "You are extracting a table of contents from the beginning of a book. "
    "Return ONLY a JSON array with no markdown formatting. "
    'Each entry must have: {"level": 1 or 2, "number": "1" or "1.1", "title": "...", "logical_page": 5}. '
    "level 1 = chapter/part/unit, level 2 = section/subsection. "
    "Only include entries whose page number is an arabic numeral (integer). "
    "Skip front matter with roman numeral page numbers (Preface, Foreword, Index, etc.). "
    "If no table of contents is present, return []."
)


def _extract_toc_with_llm(
    raw_text: str,
    model_name: str = _TOC_MODEL,
    cache_path: Optional[str] = None,
) -> List[TocEntry]:
    """Send the first N pages of raw text to an LLM and parse out TOC entries."""
    # Load from cache if available
    if cache_path and Path(cache_path).exists():
        print(f"  Loading TOC from cache: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [TocEntry(**e) for e in raw]

    print(f"  Calling {model_name} for TOC extraction...")
    content = create_llm_response(
        prepared_usr_prompt=f"Here is the beginning of the book:\n\n{raw_text}",
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
    model_name: str = _TOC_MODEL,
    cache_path: Optional[str] = None,
    book_config: Optional[BookConfig] = None,
) -> List[BookChapter]:
    """
    Extract chapter structure using:
    1. LLM to parse raw text from the first 15 pages → structured TOC entries
    2. PyMuPDF page number map to locate each chapter's exact PDF page
    """
    # Step 1: extract raw text from first 15 pages
    raw_text = "".join(
        doc[i].get_text("text") for i in range(min(15, total_pages))
    )
    if not raw_text.strip():
        return []

    # Step 2: LLM extracts TOC entries
    toc_entries = _extract_toc_with_llm(raw_text, model_name=model_name, cache_path=cache_path)
    if not toc_entries:
        print("  LLM found no TOC entries — will try heading detection")
        return []

    chapter_entries = [e for e in toc_entries if e.level == 1]
    section_entries = [e for e in toc_entries if e.level == 2]
    print(f"  LLM TOC: {len(chapter_entries)} chapters, {len(section_entries)} sections")

    if not chapter_entries:
        return []

    # Step 3: build printed page number → PDF page map
    print("  Building page number map from PDF footers/headers...")
    page_map = _build_page_number_map(doc)
    print(f"  Page map covers {len(page_map)} pages (range: {min(page_map) if page_map else '?'}–{max(page_map) if page_map else '?'})")

    # Step 4: build BookChapter objects
    chapter_entries.sort(key=lambda e: e.logical_page)
    chapters: List[BookChapter] = []

    for idx, ch_entry in enumerate(chapter_entries):
        ch_start = _nearest_mapped_page(page_map, ch_entry.logical_page, total_pages)
        if idx + 1 < len(chapter_entries):
            next_start = _nearest_mapped_page(page_map, chapter_entries[idx + 1].logical_page, total_pages)
            ch_end = max(ch_start, next_start - 1)
        else:
            ch_end = total_pages - 1

        # Parse chapter number from entry.number (handles "1", "I", "A", etc.)
        try:
            ch_num = int(ch_entry.number)
        except ValueError:
            ch_num = idx + 1

        ch_id = f"ch_{ch_num:02d}"

        # Find sections for this chapter
        ch_sections = [
            s for s in section_entries
            if s.number.startswith(f"{ch_entry.number}.")
            or (s.logical_page >= ch_entry.logical_page
                and (idx + 1 >= len(chapter_entries)
                     or s.logical_page < chapter_entries[idx + 1].logical_page))
        ]
        sections: List[BookSection] = []
        for s_idx, s_entry in enumerate(ch_sections):
            s_start = _nearest_mapped_page(page_map, s_entry.logical_page, total_pages)
            if s_idx + 1 < len(ch_sections):
                s_end = max(s_start, _nearest_mapped_page(page_map, ch_sections[s_idx + 1].logical_page, total_pages) - 1)
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
    """Remove exercise/bibliographical sections and trim ch_end accordingly."""
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

    Tries three strategies in order:
    1. Embedded PDF TOC metadata (doc.get_toc) — instant, no API call
    2. LLM TOC extraction + printed page number map — handles any format
    3. Font-size heading detection — last resort fallback

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

    # Strategy 2: LLM TOC extraction + page number map
    print("  No embedded TOC — using LLM TOC extraction + page number map")
    chapters = _chapters_from_text_toc(
        doc, total_pages, model_name=model_name, cache_path=toc_cache_path,
        book_config=book_config,
    )
    if chapters:
        doc.close()
        return chapters

    # Strategy 3: font-size heading detection
    print("  Falling back to font-size heading detection")
    chapters = _chapters_from_headings(doc)
    doc.close()
    return chapters


def _chapters_from_toc(
    doc: fitz.Document, toc: list, total_pages: int
) -> List[BookChapter]:
    """Build BookChapter list from an embedded PDF TOC."""
    # PyMuPDF TOC entries: [level, title, page_1indexed, ...]
    # Convert to 0-indexed pages
    entries = [(e[0], e[1].strip(), e[2] - 1) for e in toc]

    # Separate chapter-level and section-level entries
    chapter_entries: List[Tuple[str, int]] = []  # (title, start_page)
    for level, title, page in entries:
        if _toc_level_is_chapter(title, level):
            chapter_entries.append((title, max(0, page)))

    if not chapter_entries:
        # Treat all level-1 TOC entries as chapters
        chapter_entries = [
            (title, max(0, page))
            for level, title, page in entries
            if level == 1
        ]

    chapters: List[BookChapter] = []
    for idx, (ch_title, ch_start) in enumerate(chapter_entries):
        ch_end = (
            chapter_entries[idx + 1][1] - 1
            if idx + 1 < len(chapter_entries)
            else total_pages - 1
        )
        ch_id = f"ch_{idx + 1:02d}"

        # Find sections belonging to this chapter
        sections = _sections_for_chapter(
            doc, entries, ch_start, ch_end, ch_id, idx + 1
        )

        chapter_text = _extract_page_text(doc, ch_start, ch_end)
        token_count = _approx_tokens(chapter_text)

        chapters.append(
            BookChapter(
                chapter_id=ch_id,
                title=ch_title,
                chapter_number=idx + 1,
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
) -> List[BookSection]:
    """Extract sections within a chapter's page range from the TOC."""
    section_entries = [
        (level, title, page)
        for level, title, page in toc_entries
        if _toc_level_is_section(title, level)
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

def extract_toc_text(pdf_path: str, snippet_pages: int = 2) -> str:
    """
    Extract the Table of Contents as a structured text string, plus the first
    `snippet_pages` pages of each chapter. Used as input to the series bible.
    """
    doc = fitz.open(pdf_path)
    toc = doc.get_toc(simple=False)

    lines = ["=== TABLE OF CONTENTS ==="]
    for level, title, page in toc:
        indent = "  " * (level - 1)
        lines.append(f"{indent}{title} (p.{page})")

    lines.append("\n=== CHAPTER SNIPPETS ===")
    chapters = _chapters_from_toc(doc, [(e[0], e[1].strip(), e[2] - 1) for e in toc], len(doc)) if toc else _chapters_from_headings(doc)

    for ch in chapters:
        snippet_end = min(ch.start_page + snippet_pages - 1, ch.end_page)
        snippet_text = _extract_page_text(doc, ch.start_page, snippet_end)
        lines.append(f"\n--- {ch.title} ---")
        lines.append(snippet_text[:1500])  # cap per-chapter snippet

    doc.close()
    return "\n".join(lines)
