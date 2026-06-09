# PRD: Job Infrastructure & Deployment

**Priority:** 2 of 3
**Blocked by:** `prd-pipeline-optimization`
**Blocks:** `prd-auth-billing`

## Introduction

With the pipeline refactored for speed and configurability (PRD 1), this PRD covers the infrastructure needed to serve multiple users concurrently: an async job queue, cloud storage for artifacts, containerized deployment with autoscaling, and integration with the existing FastAPI backend on the `website` branch.

The frontend already has a Generation page that polls `/api/status/{job_id}` every 4 seconds and a Player page that loads results from `/api/result/{job_id}`. The API shell exists in `anvaya_website/apps/api/main.py` with endpoints for `/api/generate`, `/api/status`, `/api/result`, `/api/video`, `/api/jobs`, and `/api/health`. Currently the API runs pipeline jobs in-process with no queue — this PRD replaces that with proper async workers.

## Goals

- Process multiple video generation jobs concurrently via worker pool
- Store all artifacts in cloud storage accessible by any worker
- Deploy API + workers as containers with autoscaling
- Integrate with existing FastAPI endpoints (no frontend changes needed)
- Support 20 simultaneous jobs at launch

## User Stories

### US-001: StorageBackend abstract class and LocalStorage
**Description:** As a developer, I want a storage abstraction so pipeline code doesn't use `open()` directly, enabling future S3 swap.

**Acceptance Criteria:**
- [ ] `storage/backend.py` with `StorageBackend` ABC: `read(path)`, `write(path, data)`, `exists(path)`, `list(prefix)`, `delete(path)`, `get_url(path)`
- [ ] `LocalStorage` implementation using local filesystem (current behavior)
- [ ] All methods work with both binary and text data
- [ ] `pytest` passes

### US-002: S3Storage implementation
**Description:** As a developer, I want an S3 storage backend for production multi-worker artifact access.

**Acceptance Criteria:**
- [ ] `S3Storage` implementation using boto3
- [ ] `get_url()` returns pre-signed URL with configurable expiry (default 1h)
- [ ] Supports upload/download of large files (videos up to 500MB)
- [ ] Backend selected by `PipelineConfig.storage.backend` (`local` or `s3`)
- [ ] `pytest` passes with mocked S3

### US-003: Migrate pipeline to use StorageBackend
**Description:** As a developer, I want pipeline stages to read/write artifacts through StorageBackend instead of direct file I/O.

**Acceptance Criteria:**
- [ ] `pdf_explanation_generator.py` writes explanation JSON through storage backend
- [ ] `beat_sync_tts.py` writes audio files through storage backend
- [ ] `code_generator.py` writes scene code through storage backend
- [ ] `video_renderer.py` writes rendered/synced videos through storage backend
- [ ] `pdf_to_manim_pipeline.py` reads/writes all artifacts through storage backend
- [ ] Pipeline still works locally with `LocalStorage` (no behavior change)
- [ ] `pytest` passes

### US-004: PostgreSQL job metadata schema
**Description:** As a developer, I want a PostgreSQL schema for job metadata so job state persists across API restarts.

**Acceptance Criteria:**
- [ ] `db/models.py` with SQLAlchemy models: `Job` (id, user_id, status, difficulty, language, created_at, updated_at, error_summary, video_url)
- [ ] `db/migrations/` with Alembic initial migration
- [ ] Job statuses: `queued`, `processing`, `stage:explanation`, `stage:audio`, `stage:codegen`, `stage:render`, `completed`, `failed`
- [ ] `pytest` passes

### US-005: Celery task definition for pipeline job
**Description:** As a developer, I want the pipeline wrapped as a Celery task that workers can execute from a Redis queue.

**Acceptance Criteria:**
- [ ] `tasks/generate_video.py` with Celery task that runs the pipeline for a given job_id
- [ ] Task reads job params from PostgreSQL, runs pipeline, updates status at each stage transition
- [ ] On success: updates job status to `completed`, stores video URL
- [ ] On failure: updates job status to `failed` with error summary, uses PRD 1 checkpoints for retry
- [ ] Celery config in `celeryconfig.py` with Redis broker URL from env var
- [ ] `pytest` passes

### US-006: Job priority queue
**Description:** As an operator, I want hard-mode jobs processed before easy-mode jobs in the queue.

**Acceptance Criteria:**
- [ ] Celery priority queues: hard=high, medium=default, easy=low
- [ ] Job enqueue sets priority based on difficulty
- [ ] Under load, hard-mode jobs skip ahead of queued easy-mode jobs
- [ ] `pytest` passes

### US-007: Dead letter queue and job TTL
**Description:** As an operator, I want failed jobs moved to a dead letter queue and old jobs auto-expired.

**Acceptance Criteria:**
- [ ] Jobs that fail after 2 attempts (initial + 1 retry from checkpoint) move to DLQ
- [ ] DLQ jobs queryable via admin API endpoint
- [ ] Job TTL: auto-expire jobs older than 24h (configurable)
- [ ] `pytest` passes

### US-008: Update FastAPI to enqueue jobs
**Description:** As a developer, I want the existing FastAPI endpoint to enqueue Celery tasks instead of running the pipeline in-process.

**Acceptance Criteria:**
- [ ] POST `/api/jobs` accepts PDF upload or arXiv URL, difficulty, language
- [ ] Saves PDF to storage backend, creates job record in PostgreSQL, enqueues Celery task
- [ ] Returns job_id immediately with status `queued`
- [ ] Existing frontend Generation page works without modification
- [ ] `pytest` passes

### US-009: Job status and result endpoints
**Description:** As a developer, I want status and result endpoints reading from PostgreSQL.

**Acceptance Criteria:**
- [ ] GET `/api/jobs/{job_id}` returns status, current stage, estimated time remaining
- [ ] On completion, response includes video pre-signed URL from storage backend
- [ ] On failure, response includes stage name, error summary, whether retryable
- [ ] GET `/api/jobs` lists all jobs (paginated, most recent first)
- [ ] `pytest` passes

### US-010: arXiv URL handler
**Description:** As a user, I want to paste an arXiv link instead of uploading a PDF.

**Acceptance Criteria:**
- [ ] API accepts arXiv URL (e.g., `https://arxiv.org/abs/2301.00001`)
- [ ] Extracts paper ID, downloads PDF from `https://arxiv.org/pdf/{id}.pdf`
- [ ] Validates downloaded file is a valid PDF
- [ ] Stores PDF to storage backend, then enqueues job as normal
- [ ] `pytest` passes

### US-011: Dockerfile for pipeline worker
**Description:** As an operator, I want a Docker image for the pipeline worker with all system dependencies.

**Acceptance Criteria:**
- [ ] `Dockerfile.worker` with: Python 3.11+, Manim, LaTeX, ffmpeg, CJK fonts (Noto Sans CJK), Cairo, Pango
- [ ] Multi-stage build: system deps base layer + Python deps + app code
- [ ] Image builds successfully and can run a test pipeline job
- [ ] ChromaDB RAG index baked into image (read-only, ~50MB)
- [ ] Image size < 3GB

### US-012: Dockerfile for API server
**Description:** As an operator, I want a Docker image for the FastAPI API server.

**Acceptance Criteria:**
- [ ] `Dockerfile.api` with: Python 3.11+, FastAPI deps
- [ ] Lightweight image (no Manim/ffmpeg/LaTeX needed)
- [ ] Serves on port 8000
- [ ] Image size < 500MB

### US-013: docker-compose for local development
**Description:** As a developer, I want `docker-compose up` to spin up the full stack locally.

**Acceptance Criteria:**
- [ ] `docker-compose.yml` with services: api, worker, redis, postgres
- [ ] Volumes for local code mounting (hot reload for API)
- [ ] Environment variables for config profile (`dev`)
- [ ] `docker-compose up` starts all services and can process a job end-to-end

### US-014: Cloud deployment config
**Description:** As an operator, I want deployment configuration for ECS Fargate.

**Acceptance Criteria:**
- [ ] Terraform or CDK config for: ECS cluster, Fargate services (api + worker), ECR repos, ElastiCache Redis, RDS PostgreSQL, S3 bucket
- [ ] Worker autoscaling: scale up when queue depth > 5, scale down after 10 min idle
- [ ] API autoscaling: scale on request count
- [ ] Health check endpoints: API `/api/health`, worker heartbeat to Redis
- [ ] Deployment documented in README

## Functional Requirements

- FR-1: API server accepts PDF upload (max 50MB) or arXiv URL and enqueues a generation job
- FR-2: arXiv URL handler downloads PDF from arXiv before enqueuing
- FR-3: Job queue processes jobs FIFO with priority weighting (hard > medium > easy)
- FR-4: Workers use `PipelineConfig` and `LLMProvider` from PRD 1
- FR-5: Workers use `StorageBackend` for all artifact I/O
- FR-6: Job metadata (status, timestamps, error info) stored in PostgreSQL
- FR-7: Completed videos served via pre-signed S3 URL
- FR-8: Job status updates queryable via existing API endpoints
- FR-9: Failed jobs automatically retry once from last checkpoint; on second failure, move to DLQ

## Non-Goals (Out of Scope)

- Pipeline internals / speed optimization (PRD 1)
- Auth, billing, tokens, rate limiting (PRD 3)
- Frontend/UI changes (existing pages already support this API contract)
- Multi-region deployment
- Video CDN (use S3 pre-signed URLs for v1; evaluate CloudFront later)
- WebSocket push notifications (polling is sufficient for v1)

## Technical Considerations

### Recommended stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Job queue | **Celery + Redis** | Python-native, mature, simple setup. Workers import pipeline directly. |
| Broker | **Redis (ElastiCache)** | Celery broker + result backend. Also serves as cache. |
| Metadata DB | **PostgreSQL (RDS)** | Job status, user data (shared with PRD 3). |
| Artifact storage | **S3** | Pre-signed URLs, lifecycle policies for cleanup, cheap. |
| Compute | **ECS Fargate** | Serverless containers, no cluster management, autoscaling. |
| Container registry | **ECR** | Native ECS integration. |

Alternative for simpler start: **Railway** (managed containers + Redis + PostgreSQL) — migrate to ECS when exceeding Railway limits.

### Docker image considerations

The pipeline worker image will be large (~2GB) due to Manim (LaTeX, cairo, pango), ffmpeg, and CJK fonts. Use multi-stage build: base image with system deps changes rarely; Python layer on top for fast rebuilds. Fargate cold start with 2GB image: ~30-60s (acceptable since jobs take minutes).

### ChromaDB in multi-worker environment

Bake RAG index into Docker image (recommended for v1) — it's read-only, ~50MB. No extra service needed.

### Integration with existing API

The `website` branch API currently runs pipeline synchronously in-process. Changes: replace in-process call with Celery enqueue, replace in-memory job dict with PostgreSQL, replace local file serving with S3 pre-signed URLs. Same endpoint contract so frontend works unchanged.

### Feedback loop commands

```bash
# Run after every story
python -m pytest tests/ -v
# For Docker stories
docker build -f Dockerfile.worker -t anvaya-worker .
docker build -f Dockerfile.api -t anvaya-api .
docker-compose up --build
```

## Success Metrics

- Support 20 concurrent jobs without degradation
- Job enqueue to worker pickup: <5s (p95)
- Worker autoscale from 0 to 1: <90s
- Zero data loss on worker crash (checkpoint + S3 ensures resumability)
- API response time for status check: <100ms (p95)

## Open Questions

1. **Celery vs Temporal:** Celery is simpler but Temporal has better long-running workflow support. Worth the complexity for v1?
2. **S3 region:** Which AWS region? Closest to target users, or cheapest?
3. **Worker sizing:** 1 vCPU / 4GB RAM or 2 vCPU / 8GB? Manim is CPU-bound — need benchmarking.
4. **Queue visibility:** Flower dashboard from day 1, or CloudWatch logging sufficient?
5. **arXiv download:** API-side (simpler validation) or worker-side (avoids large queue payloads)?
