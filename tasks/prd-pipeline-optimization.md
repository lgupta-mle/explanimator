# PRD: Pipeline Optimization & Architecture Refactor

**Priority:** 1 of 3 (no external dependencies — start here)
**Blocks:** `prd-job-infrastructure`, `prd-auth-billing`

## Introduction

The Anvaya pipeline currently takes 40-60 minutes per video per language due to sequential LLM calls, cascaded ffmpeg re-encodes, no parallelization between independent stages, and hardcoded model references across 7+ files. This PRD covers the internal refactoring needed to hit target latencies (hard <5 min, medium <15 min, easy <30 min) and make the pipeline configurable, observable, and resumable — all without any infrastructure changes.

Everything here can be developed and tested locally on the current branch.

## Goals

- Reduce hard-mode end-to-end latency from ~15-20 min to <5 min
- Reduce medium-mode to <15 min, easy-mode to <30 min
- Centralize all configuration (models, concurrency, timeouts) — zero hardcoded defaults in business logic
- Abstract LLM providers so models can be swapped per stage per difficulty without code changes
- Add pipeline checkpointing so failed runs resume from last completed stage
- Replace 50+ print() calls with structured logging and per-stage timing metrics
- Enable model tiering by difficulty level for cost/speed optimization

## User Stories

### US-001: Create PipelineConfig Pydantic model
**Description:** As a developer, I want a single `PipelineConfig` Pydantic model that defines all pipeline parameters in one place.

**Acceptance Criteria:**
- [ ] `config/pipeline_config.py` with `PipelineConfig` Pydantic model
- [ ] Sections: `llm` (model names per stage), `audio` (TTS model, voice, max_workers), `video` (quality, sync_mode, max_speed_change), `manim` (timeout, max_workers), `translation` (model, max_workers)
- [ ] Loads from `config.yaml` in project root
- [ ] `ANVAYA_*` env var overrides (e.g., `ANVAYA_LLM__EXPLANATION_MODEL`)
- [ ] Config validated at startup; fails fast with actionable error on missing required values
- [ ] `pytest` passes

### US-002: Migrate hardcoded values to config
**Description:** As a developer, I want all hardcoded model names and concurrency values replaced with reads from `PipelineConfig`.

**Acceptance Criteria:**
- [ ] `pdf_explanation_generator.py` reads explanation, judge, prereq models from config (lines 23-24, 36, 274, 398, 464)
- [ ] `code_generator.py` reads code gen model + timeout + max_workers from config (lines 66, 162, 307, 345)
- [ ] `translator.py` reads translation model from config (line 9)
- [ ] `beat_sync_tts.py` reads TTS model + max_workers from config (lines 19, 124)
- [ ] `video_renderer.py` reads max_workers from config
- [ ] `llm_utils.py` reads default model from config (line 13)
- [ ] `constants.py` reads embedding model from config (line 4)
- [ ] Zero hardcoded model names or worker counts remain in business logic
- [ ] `pytest` passes

### US-003: Add config profiles for dev/staging/prod
**Description:** As a developer, I want separate config profiles so dev uses cheap models and prod uses quality models.

**Acceptance Criteria:**
- [ ] `config/dev.yaml`, `config/staging.yaml`, `config/prod.yaml`
- [ ] `ANVAYA_PROFILE` env var selects profile (default: `dev`)
- [ ] Dev profile uses cheapest/fastest models for iteration
- [ ] Prod profile uses current production models
- [ ] Profile-specific values override base `config.yaml`
- [ ] `pytest` passes

### US-004: Create LLMProvider abstract base class
**Description:** As a developer, I want an `LLMProvider` ABC so pipeline stages don't depend on OpenRouter directly.

**Acceptance Criteria:**
- [ ] `providers/llm_provider.py` with `LLMProvider` ABC defining `generate(messages, model, **kwargs) -> LLMResponse`
- [ ] `LLMResponse` dataclass with: `content`, `model`, `tokens_used` (input + output), `latency_ms`
- [ ] `OpenRouterProvider` implementation wrapping current `call_openrouter()` logic
- [ ] Provider instantiated from `PipelineConfig` at startup
- [ ] `pytest` passes

### US-005: Add retry with exponential backoff to LLMProvider
**Description:** As a developer, I want LLM calls to auto-retry on transient failures instead of crashing the pipeline.

**Acceptance Criteria:**
- [ ] `OpenRouterProvider.generate()` retries on 429, 500, 502, 503, timeout errors
- [ ] Exponential backoff: 1s, 2s, 4s (max 3 retries, configurable)
- [ ] Non-retryable errors (400, 401, 404) raise immediately
- [ ] Each retry logged with attempt number and wait time
- [ ] `pytest` passes with mock tests for retry behavior

### US-006: Migrate pipeline stages to use LLMProvider
**Description:** As a developer, I want all pipeline stages calling LLMs through the provider instead of `call_openrouter()` directly.

**Acceptance Criteria:**
- [ ] `pdf_explanation_generator.py` uses provider for explanation + judge + prereq calls
- [ ] `code_generator.py` uses provider for code generation calls
- [ ] `translator.py` uses provider for translation calls
- [ ] `call_openrouter()` in `llm_utils.py` removed or deprecated (only provider used)
- [ ] Token usage accumulated per pipeline run
- [ ] `pytest` passes

### US-007: Add token usage tracking per job
**Description:** As a developer, I want to know how many tokens and API calls each pipeline run consumes for cost tracking.

**Acceptance Criteria:**
- [ ] `LLMProvider` accumulates per-call stats: model, tokens_in, tokens_out, latency_ms
- [ ] Pipeline run produces a `run_metrics.json` with: total_tokens, total_cost_estimate, calls_per_stage, total_duration
- [ ] Cost estimate uses configurable per-model pricing table in config
- [ ] `pytest` passes

### US-008: Parallelize audio and code generation
**Description:** As a developer, I want audio generation and Manim code generation to run concurrently after the explanation is produced.

**Acceptance Criteria:**
- [ ] After explanation generation, TTS (beat_sync_tts) and code gen (code_generator) launch in parallel via `concurrent.futures`
- [ ] Both stages receive the explanation as input; neither depends on the other's output
- [ ] If one fails, the other is cancelled (fail-fast)
- [ ] Wall-clock time for both stages combined equals the slower of the two (not sum)
- [ ] `pytest` passes

### US-009: Single-pass ffmpeg filter chain
**Description:** As a developer, I want ffmpeg speed adjustment and audio merge done in one pass instead of two sequential re-encodes.

**Acceptance Criteria:**
- [ ] `video_renderer.py`: replace `adjust_video_speed()` + `extend_video_to_duration()` chain with single ffmpeg command using combined filter (`-vf "setpts=PTS*X,tpad=stop_duration=Y"`)
- [ ] Audio merge happens in same ffmpeg call (`-i video -i audio -c:v copy` when no speed change needed)
- [ ] Eliminates double re-encode: one ffmpeg invocation per scene, not two
- [ ] Output quality identical to current (visual diff test on sample video)
- [ ] `pytest` passes

### US-010: Pipeline-parallel render and sync
**Description:** As a developer, I want scene N+1 to start rendering while scene N is being synced with audio.

**Acceptance Criteria:**
- [ ] Replace sequential render-all-then-sync-all with producer-consumer pattern
- [ ] Render pool produces completed scenes; sync consumer processes them as they finish
- [ ] Overall wall-clock time reduced (render and sync overlap)
- [ ] Configurable render workers and sync workers in `PipelineConfig`
- [ ] `pytest` passes

### US-011: Increase translation worker pool
**Description:** As a developer, I want the translation fallback pool larger than 4 workers to reduce translation latency.

**Acceptance Criteria:**
- [ ] Translation worker count reads from `PipelineConfig.translation.max_workers` (default 10)
- [ ] `translator.py` fallback ThreadPoolExecutor uses configured value instead of hardcoded 4
- [ ] `pytest` passes

### US-012: Model tiering config per difficulty
**Description:** As a developer, I want `PipelineConfig` to support per-difficulty model overrides so hard-mode uses fast models.

**Acceptance Criteria:**
- [ ] Config structure: `llm.tiers.hard.explanation_model`, `llm.tiers.medium.explanation_model`, etc.
- [ ] If tier-specific model not set, falls back to base `llm.explanation_model`
- [ ] Pipeline reads model from tier based on current job's difficulty
- [ ] `pytest` passes

Current model map for tier planning:

| Stage | Current Model | Hard-mode candidate | Rationale |
|-------|--------------|-------------------|-----------|
| Explanation | `openai/gpt-5` | `deepseek/deepseek-v3.2` or `gemini-2.5-flash` | 2-3 segments need less nuance |
| Judge | `deepseek/deepseek-v3.2` | Skip entirely for hard | Binary checks on 2 segments not worth the latency |
| Prerequisites | `deepseek/deepseek-v3.2` | N/A (hard skips prereqs) | Hard mode has no prerequisites |
| Code gen | `anthropic/claude-sonnet-4.5` | `claude-haiku-4.5` or `deepseek-v3.2` | Fewer scenes, simpler animations |
| Translation | `deepseek/deepseek-v3.2` | Same (already fast) | Minimal text in hard mode |
| Embeddings | `text-embedding-3-large` | `text-embedding-3-small` | Test quality impact on RAG retrieval |

### US-013: Skip judge loop for hard mode
**Description:** As a developer, I want hard-mode to skip the judge feedback loop to save 1-2 LLM calls (~30s).

**Acceptance Criteria:**
- [ ] When difficulty is `hard`, `generate_with_feedback_loop()` skips judge evaluation
- [ ] Segment count validation still runs (retry if outside 2-3 range)
- [ ] Configurable via `PipelineConfig`: `llm.tiers.hard.skip_judge: true`
- [ ] `pytest` passes

### US-014: Hard-mode end-to-end latency validation
**Description:** As a developer, I want to verify hard-mode completes in <5 minutes on a typical paper.

**Acceptance Criteria:**
- [ ] Profiling script that runs hard-mode on a sample paper and reports per-stage timings
- [ ] Uses fast model tier (US-012) + parallel stages (US-008) + single-pass ffmpeg (US-009) + skip judge (US-013)
- [ ] Hard-mode (2-3 segments) completes end-to-end in <5 min for a 10-page paper
- [ ] Per-stage timing breakdown logged to `run_metrics.json`
- [ ] If >5 min, report identifies which stage is the bottleneck

### US-015: Checkpoint write on stage completion
**Description:** As a developer, I want each pipeline stage to write a checkpoint file when it completes successfully.

**Acceptance Criteria:**
- [ ] `pipeline/checkpoint.py` with `write_checkpoint(run_dir, stage_name, artifact_paths)` and `read_checkpoints(run_dir)`
- [ ] Checkpoint file: JSON with stage name, artifact file paths, SHA-256 hashes, timestamp
- [ ] Written to `{run_dir}/checkpoints/{stage_name}.json`
- [ ] `pytest` passes

### US-016: Resume pipeline from checkpoint
**Description:** As a developer, I want the pipeline to skip completed stages on re-run by validating checkpoint hashes.

**Acceptance Criteria:**
- [ ] On startup, pipeline reads checkpoint files from run directory
- [ ] For each completed stage, validates artifact hashes match checkpoint
- [ ] If hash matches, skips stage; if mismatch, re-runs from that stage forward
- [ ] `--force-restart` CLI flag ignores all checkpoints
- [ ] Partial audio resume: if beat 47/100 failed, only regenerate beats 47-100
- [ ] `pytest` passes

### US-017: Replace print() with structured logging
**Description:** As a developer, I want all print() statements replaced with Python `logging` calls.

**Acceptance Criteria:**
- [ ] Logger configured per module: `logging.getLogger(__name__)`
- [ ] All 50+ `print()` calls replaced with appropriate log level (info, warning, error, debug)
- [ ] Log format includes: timestamp, level, module, message
- [ ] No print() statements remain in `src/research_viz/`
- [ ] `pytest` passes

### US-018: Per-stage timing metrics
**Description:** As a developer, I want each pipeline stage to emit timing and resource usage on completion.

**Acceptance Criteria:**
- [ ] Each stage logs on completion: stage_name, duration_seconds, tokens_used, api_calls_count
- [ ] Error logs include: exception type, stage, artifact_id, whether recoverable
- [ ] All metrics aggregated into `run_metrics.json` per pipeline run
- [ ] `pytest` passes

## Functional Requirements

- FR-1: All pipeline config loaded from `PipelineConfig` Pydantic model at startup
- FR-2: All LLM calls go through `LLMProvider` abstraction with per-call token tracking
- FR-3: Pipeline stages execute as: explanation -> (audio + codegen in parallel) -> text translation -> render -> sync -> stitch
- FR-4: ffmpeg operations use single-pass filter chains (no cascaded re-encodes)
- FR-5: Each stage writes checkpoint on success; pipeline resumes from last checkpoint on retry
- FR-6: Hard-mode skips judge loop and uses fast model tier
- FR-7: All file I/O uses Path objects (preparation for storage abstraction in PRD 2)
- FR-8: Structured logging replaces all print() statements

## Non-Goals (Out of Scope)

- Cloud storage abstraction (PRD 2: Job Infrastructure)
- Job queue / async workers (PRD 2: Job Infrastructure)
- API server changes (PRD 2: Job Infrastructure)
- Containerization / Docker (PRD 2: Job Infrastructure)
- Auth, billing, tokens (PRD 3: Auth & Billing)
- Frontend/UI changes (separate `website` branch)
- Changing the Manim rendering engine itself
- Migrating away from ChromaDB (evaluate in PRD 2)

## Technical Considerations

### Implementation order (dependency graph)

```
US-001 (PipelineConfig model)
  -> US-002 (Migrate hardcoded values)
  -> US-003 (Config profiles)
  -> US-004 (LLMProvider ABC)
       -> US-005 (Retry + backoff)
       -> US-006 (Migrate stages to provider)
       -> US-007 (Token tracking)
  -> US-012 (Model tiering config)
       -> US-013 (Skip judge for hard)

US-008 (Parallel audio + codegen) — needs US-002 for configurable workers
US-009 (Single-pass ffmpeg) — independent
US-010 (Pipeline-parallel render/sync) — independent
US-011 (Translation worker pool) — needs US-002

US-015 (Checkpoint write) — independent
  -> US-016 (Resume from checkpoint)

US-017 (Structured logging) — independent
  -> US-018 (Per-stage timing)

US-014 (Hard-mode validation) — needs US-008, US-009, US-012, US-013
```

### Files that will change

| File | Changes |
|------|---------|
| `config/__init__.py` | Export new PipelineConfig |
| `config/constants.py` | Replace with config.yaml loading |
| `config/difficulty.py` | Add model tier references |
| `utils/llm_utils.py` | Replace with LLMProvider abstraction |
| `manim_generator/pdf_explanation_generator.py` | Use config + provider, add checkpoint writes |
| `manim_generator/code_generator.py` | Use config + provider, parallel retries |
| `manim_generator/pdf_to_manim_pipeline.py` | Parallel stages, checkpoint orchestration |
| `manim_generator/video_renderer.py` | Single-pass ffmpeg, pipeline parallelism |
| `audio_generator/beat_sync_tts.py` | Configurable workers, checkpoint resume |
| `translation/translator.py` | Use config + provider, larger worker pool |

### New files

| File | Purpose |
|------|---------|
| `config/pipeline_config.py` | PipelineConfig Pydantic model |
| `config.yaml` | Base default configuration |
| `config/dev.yaml` | Dev profile overrides |
| `config/prod.yaml` | Prod profile overrides |
| `providers/llm_provider.py` | LLMProvider ABC + OpenRouterProvider |
| `pipeline/checkpoint.py` | Checkpoint read/write/validate |

### Feedback loop commands

```bash
# Run after every story to validate
python -m pytest tests/ -v
```

## Success Metrics

- Hard-mode e2e latency p50 < 5 min, p95 < 8 min
- Medium-mode p50 < 15 min, easy-mode p50 < 30 min
- Pipeline failure rate measurable (currently unknown — logging enables this)
- Resume-from-checkpoint success rate > 90%
- Cost per video: hard < $0.50, medium < $1.00, easy < $1.50 (LLM + TTS)
- Zero hardcoded model names or concurrency values in business logic

## Open Questions

1. **Judge loop for hard mode:** Skip entirely or run with 1 attempt max? Skipping saves 1-2 LLM calls (~30s). Risk: lower quality explanations slip through.
2. **Model A/B testing:** How to systematically compare quality across model tiers? Options: automated judge scoring on held-out papers, or manual review dashboard.
3. **RAG caching:** Pre-fetch common Manim error patterns into a warm cache at startup to avoid per-retry embedding calls?
4. **Manim execution caching:** Cache scene execution results by code hash? `--disable_caching` is currently hardcoded in `code_generator.py:60`.
