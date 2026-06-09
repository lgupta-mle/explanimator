# PRD: Authentication & Billing

**Priority:** 3 of 3
**Blocked by:** `prd-job-infrastructure`

## Introduction

With the pipeline optimized (PRD 1) and job infrastructure deployed (PRD 2), this PRD adds user authentication, a token-based billing system, and rate limiting so Anvaya can operate as a paid self-serve SaaS.

The frontend already has a Tokens page (`anvaya_website/src/pages/Tokens.tsx`) showing a token meter UI and a "Each generation consumes one token" message. This PRD provides the backend to power that UI.

## Goals

- Users can sign up, sign in, and manage their account
- Token-based usage system where difficulty determines cost
- Stripe integration for purchasing tokens
- Rate limiting to prevent abuse
- Free trial tier to drive adoption

## User Stories

### US-001: Supabase auth setup
**Description:** As a developer, I want Supabase configured as auth provider for the API.

**Acceptance Criteria:**
- [ ] Supabase project created with email/password + Google OAuth + GitHub OAuth enabled
- [ ] `SUPABASE_URL` and `SUPABASE_ANON_KEY` env vars in config
- [ ] Supabase client initialized in API server
- [ ] `pytest` passes

### US-002: JWT validation middleware for FastAPI
**Description:** As a developer, I want a FastAPI middleware that validates Supabase JWTs on protected endpoints.

**Acceptance Criteria:**
- [ ] `middleware/auth.py` with `get_current_user()` dependency
- [ ] Validates JWT signature using Supabase public key
- [ ] Extracts user_id from token claims
- [ ] Returns 401 on missing/invalid/expired token
- [ ] `pytest` passes with mock JWT tests

### US-003: Protect job endpoints with auth
**Description:** As a developer, I want job submission and access restricted to authenticated users who own the job.

**Acceptance Criteria:**
- [ ] POST `/api/jobs` requires valid auth token
- [ ] GET `/api/jobs/{job_id}` requires auth and job.user_id matches current user
- [ ] GET `/api/jobs` returns only current user's jobs
- [ ] Unauthenticated requests return 401; wrong user returns 403
- [ ] `pytest` passes

### US-004: User profile table and signup hook
**Description:** As a developer, I want a user_profiles table created automatically when a user signs up.

**Acceptance Criteria:**
- [ ] Alembic migration adds `user_profiles` table (id, tokens, stripe_customer_id, created_at)
- [ ] `id` references Supabase `auth.users(id)`
- [ ] On first authenticated API request, auto-create profile if not exists (upsert pattern)
- [ ] Default token balance: 3 (free trial)
- [ ] `pytest` passes

### US-005: Token balance and deduction
**Description:** As a developer, I want token balance checked and deducted atomically when a job is submitted.

**Acceptance Criteria:**
- [ ] Token cost: hard=1, medium=3, easy=5. Additional languages beyond English: +1 each
- [ ] Token deduction in same DB transaction as job creation (`SELECT FOR UPDATE` on user row)
- [ ] Returns 402 with `{"error": "insufficient_tokens", "required": X, "balance": Y}` if balance too low
- [ ] `pytest` passes

### US-006: Token refund on job failure
**Description:** As a developer, I want tokens refunded when a job fails after all retries are exhausted.

**Acceptance Criteria:**
- [ ] Celery `on_failure` callback triggers token refund
- [ ] Refund in DB transaction: increment balance + create token_event with reason `job_failed_refund`
- [ ] No refund for user errors (corrupt PDF, unsupported format) — only infrastructure/pipeline failures
- [ ] `pytest` passes

### US-007: Token balance and history API
**Description:** As a user, I want to see my token balance and usage history.

**Acceptance Criteria:**
- [ ] GET `/api/tokens` returns `{"balance": N, "history": [...]}`
- [ ] History includes: amount, reason, job_id, timestamp (most recent first, paginated)
- [ ] Alembic migration adds `token_events` table (id, user_id, amount, job_id, reason, stripe_session_id, created_at)
- [ ] `pytest` passes

### US-008: Stripe Checkout session creation
**Description:** As a user, I want to start a Stripe Checkout to buy token packs.

**Acceptance Criteria:**
- [ ] POST `/api/tokens/purchase` accepts `package` param: `small` (5/$5), `medium` (20/$15), `large` (50/$30)
- [ ] Creates Stripe Checkout session with line items
- [ ] Returns checkout URL for frontend redirect
- [ ] Creates/reuses Stripe customer ID stored on user profile
- [ ] `pytest` passes with mocked Stripe

### US-009: Stripe webhook handler
**Description:** As a developer, I want successful Stripe payments to automatically credit tokens.

**Acceptance Criteria:**
- [ ] POST `/api/webhooks/stripe` validates webhook signature
- [ ] On `checkout.session.completed`: credits tokens to user, creates token_event with reason `purchase`
- [ ] Idempotent: duplicate webhook events don't double-credit (check stripe_session_id uniqueness)
- [ ] Returns 200 to Stripe on success
- [ ] `pytest` passes with mocked webhook payloads

### US-010: Concurrent job rate limit
**Description:** As an operator, I want users limited to 3 concurrent jobs to ensure fair resource allocation.

**Acceptance Criteria:**
- [ ] On job submission, count user's jobs with status in (`queued`, `processing`, `stage:*`)
- [ ] If >= 3, return 429 with `{"error": "rate_limited", "retry_after": 60, "active_jobs": 3}`
- [ ] Check happens before token deduction (don't charge then reject)
- [ ] `pytest` passes

### US-011: Daily job rate limit
**Description:** As an operator, I want users limited to 10 jobs per 24-hour window.

**Acceptance Criteria:**
- [ ] Count user's jobs created in last 24h
- [ ] If >= 10, return 429 with `{"error": "daily_limit", "retry_after": seconds_until_reset}`
- [ ] Rate limit state uses Redis counter with 24h TTL (shared Redis from PRD 2)
- [ ] Admin override: configurable per-user limit in user_profiles table
- [ ] `pytest` passes

## Functional Requirements

- FR-1: All job submission endpoints require valid auth token
- FR-2: Token deduction happens in a database transaction with job creation
- FR-3: Failed jobs (after all retries exhausted) refund tokens automatically
- FR-4: Stripe webhooks are idempotent (duplicate events don't double-credit)
- FR-5: Rate limit checks happen before token deduction (don't charge then reject)
- FR-6: Admin API for: granting tokens, viewing user stats, overriding rate limits

## Non-Goals (Out of Scope)

- Subscription/recurring billing (token packs only for v1)
- Team/organization accounts
- Admin dashboard UI (admin API only; use Supabase dashboard for user management)
- Refund flow via Stripe (manual for v1)
- Usage-based pricing tied to actual API cost (flat token cost for v1)
- SSO / SAML enterprise auth

## Technical Considerations

### Auth architecture

```
Frontend (React) -> Supabase Auth SDK -> Supabase (JWT)
                                           |
API (FastAPI) <- JWT validation middleware <- Supabase public key
                                           |
                                    PostgreSQL (user record, tokens, jobs)
```

Supabase handles auth complexity (OAuth, email verification, password reset). FastAPI validates JWTs and links to internal user records.

### Token transaction safety

```python
# Atomic: deduct + create job in one transaction
with db.transaction():
    user = db.get_user_for_update(user_id)  # SELECT FOR UPDATE
    if user.tokens < job_cost:
        raise InsufficientTokens()
    user.tokens -= job_cost
    job = db.create_job(user_id, params)
    db.create_token_event(user_id, -job_cost, job.id, "job_created")
```

### Database schema additions

```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    tokens INTEGER NOT NULL DEFAULT 3,
    stripe_customer_id TEXT,
    daily_limit_override INTEGER,  -- NULL = use default (10)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE token_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id),
    amount INTEGER NOT NULL,
    job_id UUID REFERENCES jobs(id),
    reason TEXT NOT NULL,
    stripe_session_id TEXT UNIQUE,  -- uniqueness prevents double-credit
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_token_events_user ON token_events(user_id, created_at DESC);
```

### Pricing rationale

| Difficulty | Segments | Est. API cost | Token cost | Price at $1/token |
|-----------|----------|--------------|-----------|-------------------|
| Hard | 2-3 | ~$0.15-0.30 | 1 | $1.00 |
| Medium | 4-6 | ~$0.40-0.80 | 3 | $3.00 |
| Easy | 10-14 | ~$1.00-1.50 | 5 | $5.00 |

Bulk discounts: 5/$5 (break-even), 20/$15 (healthy margin), 50/$30 (volume discount).

### Feedback loop commands

```bash
# Run after every story
python -m pytest tests/ -v
```

## Success Metrics

- Signup to first video: <3 min (free trial, no credit card)
- Token purchase conversion: >10% of trial users
- Payment success rate: >95%
- Token accounting accuracy: 100% (no orphaned debits without jobs)
- Rate limit false positive rate: <1%

## Open Questions

1. **Token pricing:** $1/token or lower? Need per-job cost data from PRD 1's metrics to set sustainable pricing.
2. **Refund policy:** Auto-refund on all failures, or only infrastructure failures (not corrupt PDFs)?
3. **Free tier abuse:** Email verification sufficient, or need IP/fingerprint signals?
4. **Stripe region:** US Stripe account, or Stripe Atlas for international?
5. **Token expiration:** Should purchased tokens expire? (Recommendation: no expiry for v1.)
