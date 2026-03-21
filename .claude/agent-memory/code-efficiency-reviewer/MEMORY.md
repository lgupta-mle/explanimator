# Code Efficiency Reviewer -- Project Memory

## Project: research-paper-graphviz
AI pipeline: PDF research papers --> 3Blue1Brown-style animated explainer videos.

## Architecture Overview
- **Orchestrator**: `src/research_viz/manim_generator/pdf_to_manim_pipeline.py` (~1220 lines)
- **Explanation gen**: `src/research_viz/manim_generator/pdf_explanation_generator.py` (LLM + judge loop)
- **TTS**: `src/research_viz/audio_generator/beat_sync_tts.py` (OpenAI TTS, beat-level sync)
- **Translation**: `src/research_viz/translation/translator.py` (DeepSeek via OpenRouter)
- **Text processor**: `src/research_viz/translation/manim_text_processor.py` (Manim Text() replacement)
- **LLM utils**: `src/research_viz/utils/llm_utils.py` (OpenRouter API calls)
- **Config**: `src/research_viz/config/difficulty.py` (easy/medium/hard dataclass configs)
- **Schemas**: `src/research_viz/schemas/` (explanation, language, animation, manim_docs)
- **RAG**: `src/research_viz/preprocessing/manim_db.py` (ChromaDB + text-embedding-3-large)
- **Prompts**: `src/research_viz/manim_generator/prompts/` (3 .txt prompt files, code gen is ~745 lines)

## Key Patterns
- All LLM calls go through `call_openrouter()` in llm_utils.py (raw requests, not async)
- Also has `create_llm_response()` using OpenAI SDK -- two different call paths exist
- Pipeline uses file-based caching (checks os.path.exists before regenerating)
- CLI via `tyro.cli(main)` in pipeline, `argparse` in beat_sync_tts
- Pydantic BaseModel for structured LLM output (ManimSceneCode, JudgeResult, etc.)
- Manim code gen uses execution-based feedback loop with RAG fallback
- Beat-level sync mode is a TODO stub that falls back to segment sync

## Known Architectural Issues (reviewed 2026-03-08)
- Entirely sequential pipeline -- no async/parallel execution
- Segment processing is serialized (both TTS and code gen)
- Beat-level TTS is serialized within segments
- Translation uses per-segment LLM calls instead of batching
- Free-form Manim code generation has high failure rate, retry loop is expensive
- Two different LLM call utilities (call_openrouter vs create_llm_response) -- duplication
- beat_sync_tts uses argparse while pipeline uses tyro -- inconsistent CLI patterns
- `beat_sync_tts.py` has verbose print output (decorative separators, per-beat stats)
- get_video_duration / get_audio_duration are near-identical (DRY violation)

## User Preferences
- No bloated print statements, summary statistics, or emojis in code
- Efficient and compact code style
- Prefers concrete actionable feedback over generic advice
