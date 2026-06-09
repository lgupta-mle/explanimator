# Development Notes: Difficulty Toggles + Multilingual Support

Branch: `feature/difficulty-multilingual`

This document covers the two features added to the pipeline and the subsequent bug-fix pass.

---

## 1. Feature Overview

### Difficulty Toggles

Three difficulty levels control segment count, narration length, beat sizing, and prerequisite inclusion:

| Level  | Segments | Narration words/segment | Beat words | Prerequisites |
|--------|----------|------------------------|------------|---------------|
| easy   | 10-14    | 350-600                | 10-30      | Yes (depth 3) |
| medium | 4-6      | 150-300                | 8-25       | No            |
| hard   | 2-3      | 80-180                 | 6-20       | No            |

Easy mode generates a prerequisite tree via a dedicated LLM call, then injects mandatory prerequisite segments into the explanation prompt. The judge gets difficulty-specific criteria (easy checks prerequisite coverage, hard checks conciseness).

Segment count is validated after generation; if outside the configured range the loop auto-retries with explicit feedback.

### Multilingual Support

11 languages supported via English-first strategy:

1. Explanation is always generated in English (LLM output quality)
2. Narration is translated via DeepSeek for TTS
3. Manim `Text()` strings are post-processed with translated text + font injection
4. CJK gets character-count-based beat splitting (3 chars ~ 1 English word) and font_size reduction
5. MathTex/LaTeX expressions are never translated

Supported: `en`, `es`, `fr`, `de`, `ja`, `zh`, `ko`, `hi`, `ar`, `ru`, `pt`

---

## 2. Output Folder Structure

Each difficulty + language combination gets its own subdirectory to prevent collisions:

```
src/research_viz/manim_generator/output/
  {pdf_stem}_{difficulty}_{language}/
    {pdf_stem}_explanation.json          # English explanation
    {pdf_stem}_explanation_{lang}.json   # Translated narration (non-English only)
    {pdf_stem}_animation.py             # Manim code (Text() translated for non-English)
    {pdf_stem}_scene_metadata.json      # Scene metadata for reuse
    audio_beats/
      beat_timeline.json                # Beat timing metadata
      seg_01_beat_1.wav                 # TTS audio files
      ...
    synced_scene_1.mp4                  # Individual synced videos
    final_video.mp4                     # Stitched output
```

Example directories:
- `output/Turing_Paper_medium_en/` - default
- `output/Turing_Paper_easy_es/` - easy Spanish
- `output/Turing_Paper_hard_ja/` - hard Japanese

The pipeline skips completed steps (explanation, audio, code, renders) so re-running the same command resumes where it left off.

---

## 3. CLI Usage

```bash
source .venv/bin/activate

# Default (medium, English, code-only)
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
    --pdf-path resources/Turing_Paper_1936-10-17.pdf

# Easy mode with full pipeline
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
    --pdf-path resources/Turing_Paper_1936-10-17.pdf \
    --difficulty easy --generate-audio --render-video

# Hard mode in Japanese
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
    --pdf-path resources/Turing_Paper_1936-10-17.pdf \
    --difficulty hard --language ja --generate-audio --render-video

# Reuse existing explanation with different settings
python -m research_viz.manim_generator.pdf_to_manim_pipeline \
    --explanation-path output/Turing_Paper_medium_en/Turing_Paper_explanation.json \
    --difficulty easy --language es

# Standalone explanation generation
python -m research_viz.manim_generator.pdf_explanation_generator \
    --pdf-path resources/Turing_Paper_1936-10-17.pdf --difficulty easy

# Standalone beat timeline generation
python -m research_viz.audio_generator.beat_sync_tts \
    --explanation-path output/.../explanation.json --language ja
```

### CLI Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--difficulty` | `easy`, `medium`, `hard` | `medium` | Controls segment count, narration length, prerequisites |
| `--language` | ISO 639-1 codes | `en` | Target language for narration and Manim text |
| `--generate-audio` | flag | `False` | Generate TTS audio |
| `--render-video` | flag | `False` | Render Manim scenes and stitch final video |
| `--tts-voice` | `nova`, `alloy`, `echo`, `fable`, `onyx`, `shimmer` | `nova` | OpenAI TTS voice |
| `--video-quality` | `l`, `m`, `h` | `l` | Manim render quality |
| `--sync-mode` | `segment`, `beat` | `segment` | Audio-video sync granularity |
| `--max-speed-change` | float | `0.3` | Max video speed adjustment (0.3 = 30%) |

---

## 4. Files Created

| File | Purpose |
|------|---------|
| `src/research_viz/config/__init__.py` | Exports DifficultyConfig, DIFFICULTY_CONFIGS |
| `src/research_viz/config/difficulty.py` | Dataclass with calibrated params per difficulty level |
| `src/research_viz/schemas/language_schemas.py` | LanguageConfig model + SUPPORTED_LANGUAGES dict |
| `src/research_viz/translation/__init__.py` | Exports NarrationTranslator, ManimTextProcessor |
| `src/research_viz/translation/translator.py` | LLM-based narration + display text translation |
| `src/research_viz/translation/manim_text_processor.py` | Regex-based Text() extraction, replacement, font injection |
| `tests/test_difficulty_config.py` | 6 tests for difficulty config |
| `tests/test_explanation_schemas.py` | 7 tests for Pydantic schemas |
| `tests/test_language_schemas.py` | 7 tests for language config |
| `tests/test_beat_splitting.py` | 9 tests for language-aware beat splitting |
| `tests/test_manim_text_processor.py` | 13 tests for text extraction/replacement/font injection |
| `tests/test_difficulty_prompts.py` | 7 tests for prompt building functions |

## 5. Files Modified

| File | Changes |
|------|---------|
| `src/research_viz/schemas/explanation_schemas.py` | Added PrerequisiteConcept, PrerequisiteTree models; added optional difficulty_level and prerequisite_tree fields to EducationalExplanation3B1B |
| `src/research_viz/manim_generator/pdf_explanation_generator.py` | Added generate_prerequisite_tree(), _build_difficulty_prompt_section(), _build_difficulty_judge_section(); modified generate_with_feedback_loop() and judge_explanation() for difficulty config; moved call_openrouter to llm_utils |
| `src/research_viz/manim_generator/pdf_to_manim_pipeline.py` | Added difficulty/language CLI args; added narration translation step (deep copy); added Manim Text() translation; run-specific output subdirectories |
| `src/research_viz/manim_generator/prompts/3b1b_explanation_prompt.txt` | Replaced hardcoded "4-6 segments" with generic narrative arc |
| `src/research_viz/manim_generator/prompts/manim_code_generation_prompt.txt` | Added "Multilingual Support" section |
| `src/research_viz/audio_generator/beat_sync_tts.py` | Added CJK character-count splitting; added language parameter through the chain; added --language to standalone CLI |
| `src/research_viz/utils/llm_utils.py` | Added call_openrouter() (moved from pdf_explanation_generator) |

---

## 6. Architecture Decisions

### English-first translation strategy

The explanation is always generated in English because LLM output quality is highest in English. Translation happens in two places:
1. **Narration translation** (Step 1b): a deep copy of the explanation is made; narration_script fields are translated for TTS. The original English explanation is preserved for Manim code generation.
2. **Manim Text() translation** (Step 3, after code gen): regex extracts strings from `Text()` calls (not MathTex/MarkupText/etc.), batch-translates them, and replaces in-place. Font parameters are injected for non-Latin scripts.

### Difficulty config as dataclass, not enum

`DifficultyConfig` is a `@dataclass` with calibrated numeric parameters. This avoids the need for switch statements everywhere -- each function just reads `config.min_segments` etc. The `DIFFICULTY_CONFIGS` dict maps string level names to instances.

### Balanced-paren Text() finder

Simple regex like `Text\([^)]+\)` breaks on nested parentheses (e.g. `Text("hello", color=RED.mix(BLUE, 0.5))`). The `_find_text_calls()` method uses depth counting to find the matching closing paren, which handles arbitrary nesting.

### call_openrouter in llm_utils

Originally defined in `pdf_explanation_generator.py`, which created an import inversion when `translator.py` needed it. Moved to `src/research_viz/utils/llm_utils.py` so both generator and translator modules import from a shared utility.

---

## 7. Bug Fixes Applied

These were identified during a code review and fixed in the same branch.

### Bugs

| # | Issue | Fix |
|---|-------|-----|
| 1 | In-place mutation of explanation dict during translation broke English-first strategy for Manim code gen | Use `copy.deepcopy(explanation)` for translation; keep original for code gen |
| 2 | `_TEXT_PATTERN` regex matched subclass names (MarkupText, BulletedText) | Added negative lookbehind `(?<!\w)Text\(` |
| 3 | `font_size=(\d+)` reduction was global, affecting MathTex and config values | Scoped to within Text() calls only via `_find_text_calls()` |
| 4 | Standalone `beat_sync_tts.py` CLI missing `--language` argument | Added `--language` arg and pass through to `generate_beat_timeline` |
| 5 | Font injection regex `Text\([^)]+\)` broke on nested parentheses | Replaced with balanced-paren depth-counting via `_find_text_calls()` |

### Design Issues

| # | Issue | Fix |
|---|-------|-----|
| 6 | Dead `DifficultyLevel` enum never referenced anywhere | Removed from explanation_schemas.py |
| 7 | `translator.py` imported `call_openrouter` from `pdf_explanation_generator` (import inversion) | Moved `call_openrouter` to `llm_utils.py`; updated all imports |
| 8 | `generate_with_feedback_loop` parsed JSON content twice (segment validation + final return) | Parse once into `parsed`, reuse for both |
| 9 | Two `NarrationTranslator` instances created in pipeline (narration + Manim text) | Create once before Step 1b, reuse in Step 3 |
| 10 | `generate_prerequisite_tree` silently swallowed exceptions, returning None | Raises `RuntimeError` on no LLM response; lets `json.JSONDecodeError` propagate |

### Efficiency

| # | Issue | Fix |
|---|-------|-----|
| 12 | Font injection and font_size regexes compiled on every call | Pre-compiled as class-level `_FONT_SIZE_PATTERN` |
| 13 | `list(set(texts))` lost ordering in display text dedup | Changed to `list(dict.fromkeys(texts))` |

---

## 8. Test Suite

49 tests, all passing. Run with:

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

| Test file | Count | Covers |
|-----------|-------|--------|
| test_difficulty_config.py | 6 | DifficultyConfig fields, ranges, prerequisites |
| test_explanation_schemas.py | 7 | Pydantic models, extra field rejection, optional fields |
| test_language_schemas.py | 7 | Language configs, CJK fonts, RTL, scripts |
| test_beat_splitting.py | 9 | English/CJK/Arabic splitting, min/max bounds, edge cases |
| test_manim_text_processor.py | 13 | Text extraction, translation, font injection, subclass exclusion, nested parens, font_size scoping |
| test_difficulty_prompts.py | 7 | Prompt building for each difficulty level |

---

## 9. Project File Tree

```
src/research_viz/
  config/
    __init__.py                          # Exports DifficultyConfig, DIFFICULTY_CONFIGS
    difficulty.py                        # Difficulty level dataclass + configs
  schemas/
    explanation_schemas.py               # Pydantic models for explanation structure
    language_schemas.py                  # LanguageConfig + SUPPORTED_LANGUAGES
    animation_schemas.py                 # (legacy)
    manim_docs_schemas.py                # RAG schemas
  translation/
    __init__.py                          # Exports NarrationTranslator, ManimTextProcessor
    translator.py                        # LLM translation (narration + display texts)
    manim_text_processor.py              # Regex Text() extraction/replacement/font injection
  manim_generator/
    pdf_explanation_generator.py         # PDF -> explanation with judge feedback loop
    pdf_to_manim_pipeline.py             # Main pipeline orchestrator
    prompts/
      3b1b_explanation_prompt.txt        # System prompt for explanation generation
      3b1b_judge_prompt.txt              # System prompt for judge evaluation
      manim_code_generation_prompt.txt   # System prompt for Manim code gen
  audio_generator/
    beat_sync_tts.py                     # Beat-synchronized TTS generation
  preprocessing/
    manim_db.py                          # ChromaDB RAG retriever
    manim_docs_scraper.py                # Manim docs scraping (one-time setup)
    manim_docs_chunker.py                # Doc chunking (one-time setup)
    manim_docs_embedder.py               # Embedding generation (one-time setup)
    build_manim_index.py                 # Build ChromaDB index (one-time setup)
  utils/
    llm_utils.py                         # Shared LLM utilities (call_openrouter, create_llm_response)

tests/
  test_difficulty_config.py
  test_explanation_schemas.py
  test_language_schemas.py
  test_beat_splitting.py
  test_manim_text_processor.py
  test_difficulty_prompts.py

data/manim_docs/vector_db/chroma_db/    # RAG vector database (pre-built)
```

---

## 10. Pipeline Data Flow

```
PDF
 |
 v
[pdf_explanation_generator.py]
 |  - Sends PDF + system prompt to LLM (OpenRouter)
 |  - Easy mode: generates prerequisite tree first
 |  - Judge feedback loop (up to 3 retries)
 |  - Validates segment count against difficulty config
 v
explanation.json (English)
 |
 +--> [translator.py] (if language != "en")
 |     - Deep copy of explanation
 |     - Translates narration_script per segment via DeepSeek
 |     - Saves {pdf_stem}_explanation_{lang}.json
 |
 +--> [beat_sync_tts.py]
 |     - Splits narration into beats (CJK-aware)
 |     - Generates TTS audio per beat (OpenAI)
 |     - Saves beat_timeline.json with durations
 |
 +--> [pdf_to_manim_pipeline.py] generate_all_scenes()
 |     - Uses ORIGINAL English explanation for code gen
 |     - LLM generates Manim code per segment
 |     - Execution feedback loop with RAG error recovery
 |
 +--> [manim_text_processor.py] (if language != "en")
 |     - Extracts Text() strings from generated code
 |     - Batch translates via translator
 |     - Replaces strings, injects fonts, reduces CJK font_size
 |
 v
{pdf_stem}_animation.py + audio_beats/ + final_video.mp4
```
