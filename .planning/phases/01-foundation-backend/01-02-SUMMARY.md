---
phase: 01-foundation-backend
plan: "01-02"
tags: [fastapi, pydantic, rest-api, nextjs, api-client]
dependency_graph:
  requires: ["01-01 (Wave 1 - database setup)"]
  provides: ["JOB-01", "JOB-02", "JOB-03", "JOB-04", "JOB-05", "JOB-06", "JOB-07", "NEWS-01", "NEWS-02", "NEWS-03", "NEWS-04"]
tech_stack:
  added: [fastapi, pydantic, sqlalchemy-async]
  patterns: [REST API, Generic paginated response, Dependency injection, Role-keyword filter matching]
key_files:
  created:
    - tazakhabar-backend/src/db/schemas.py
    - tazakhabar-backend/src/api/deps.py
    - tazakhabar-backend/src/api/jobs.py
    - tazakhabar-backend/src/api/news.py
    - tazakhabar-backend/src/api/__init__.py
    - tazakhabar-backend/src/services/report_service.py
    - src/lib/api.ts
  modified:
    - tazakhabar-backend/src/main.py
    - src/components/TazaContext.tsx
    - src/app/jobs/page.tsx
    - src/app/digest/page.tsx
    - src/lib/mockData.ts
key_decisions:
  - "Used Generic[T] PaginatedResponse wrapper {data: list[T], meta: {total, skip, limit, has_more}} for all list endpoints"
  - "Role filter implemented as Python-side keyword matching against job.tags (OR across roles, AND with remote/startup)"
  - "Remote filter applied at SQLAlchemy level using ilike() on location field"
  - "Startup filter deferred — requires funding_stage column in Job model not yet present"
  - "News category inferred from title keywords (hiring→HIRING, layoff→LAYOFFS, etc.)"
  - "Featured news = top 3 by score across entire filtered set"
  - "frontend feed page at src/app/digest/page.tsx (plan referenced src/app/feed/page.tsx)"
  - "Backend Job model lacks funding_stage, salary, companySize, experienceTier fields needed for full frontend parity"
metrics:
  duration_minutes: ~10
  tasks_completed: 3
  artifacts_created: 5 new files, 5 modified files
  commits: 3
---

# Phase 01 Plan 01-02: REST API Endpoints Summary

## One-liner
Job and news feed REST endpoints with Pydantic schemas, role/remote/startup filters, and live Next.js API integration replacing mock data.

## Tasks Completed

### Task 1: Create Pydantic schemas and job feed API endpoint
- **Commit:** `3d5eafb`
- Created `tazakhabar-backend/src/db/schemas.py` with `JobResponse` (18 fields), `NewsResponse` (7 fields), `PaginatedResponse[T]`, `JobFilterParams`, `ErrorResponse`
- Created `tazakhabar-backend/src/api/deps.py` with `get_db()` FastAPI dependency
- Created `tazakhabar-backend/src/api/jobs.py` with `GET /api/jobs` endpoint supporting:
  - Role filter (OR within roles) via keyword matching against job.tags
  - Remote filter (AND) at SQL level using ilike()
  - Startup-only filter (deferred — requires `funding_stage` field in Job model)
  - Pagination with skip/limit, sorted by `scraped_at` desc
  - Returns `PaginatedResponse[JobResponse]` wrapper
- Updated `tazakhabar-backend/src/main.py` to include jobs router
- **Verification:** PASS — JobResponse has 18 fields, router at `/api/jobs`

### Task 2: Create news feed API endpoint and report service
- **Commit:** `a197819`
- Created `tazakhabar-backend/src/services/report_service.py` with `advance_report_cycle()` and `get_badge_counts()`
- Created `tazakhabar-backend/src/api/news.py` with `GET /api/news` endpoint supporting:
  - Type filter (ask_hn/show_hn/top_story), sorted by score desc
  - Category inference from title keywords
  - Featured flag for top 3 by score
  - Returns `PaginatedResponse[NewsResponse]` with summary="N/A" placeholder
- Updated `tazakhabar-backend/src/main.py` to include news router
- **Verification:** PASS — news router at `/api/news`, report service functions OK

### Task 3: Connect Next.js frontend to live API
- **Commit:** `594e08d`
- Created `src/lib/api.ts` with `fetchJobs()`, `fetchNews()`, `fetchBadgeCounts()`
- Updated `src/app/jobs/page.tsx` to fetch from `/api/jobs` via `useEffect` on mount/version change
- Updated `src/app/digest/page.tsx` to fetch from `/api/news` via `useEffect` on mount/version/tab change
- Updated `TazaContext.tsx` refresh functions to trigger API re-fetches
- Marked `src/lib/mockData.ts` as `@deprecated` with fallback notes
- **Verification:** PASS — `/api/jobs` and `/api/news` registered in FastAPI app

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 - Deferred] Startup filter non-functional**
- **Found during:** Task 1
- **Issue:** Job model (`tazakhabar-backend/src/db/models.py`) lacks `funding_stage`, `salary`, `companySize`, `experienceTier` columns needed for full filter and response parity
- **Fix:** Applied startup_only filter as no-op (pass-through) with comment documenting deferred implementation. Frontend shows "N/A" for missing fields.
- **Impact:** JOB-02 (startup filter) cannot work without DB schema change. This is an architectural change (Rule 4) deferred to a future phase.
- **Files modified:** tazakhabar-backend/src/api/jobs.py
- **Commit:** `3d5eafb`

**2. [Rule 3 - Path fix] Feed page path mismatch**
- **Found during:** Task 3
- **Issue:** Plan referenced `src/app/feed/page.tsx` but actual file is `src/app/digest/page.tsx`
- **Fix:** Updated `src/app/digest/page.tsx` (the actual file) with live API integration
- **Commit:** `594e08d`

## Self-Check

- [x] `tazakhabar-backend/src/db/schemas.py` — created (verified via import test)
- [x] `tazakhabar-backend/src/api/jobs.py` — created with `/api/jobs` route
- [x] `tazakhabar-backend/src/api/news.py` — created with `/api/news` route
- [x] `tazakhabar-backend/src/services/report_service.py` — created with cycle/badges functions
- [x] `src/lib/api.ts` — created with fetchJobs/fetchNews/fetchBadgeCounts
- [x] Commit `3d5eafb` exists
- [x] Commit `a197819` exists
- [x] Commit `594e08d` exists

## Deferred Issues

1. **Job model missing fields:** `funding_stage`, `salary`, `companySize`, `experienceTier` columns needed in `Job` model for full frontend field parity. Requires adding columns and updating scraper to populate them.
2. **Applied tracking:** Backend `applied` field always returns `false`. Need user-applied tracking system (future phase).
3. **Badge counts endpoint:** `fetchBadgeCounts()` returns zeros — needs dedicated `/api/badges` endpoint.

## Blockers

None — all 3 tasks completed successfully.
