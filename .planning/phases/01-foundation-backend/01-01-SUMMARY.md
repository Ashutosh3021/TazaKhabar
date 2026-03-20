---
phase: 01-foundation-backend
plan: "01-01"
subsystem: database
tags: [fastapi, sqlalchemy, sqlite, aiosqlite, httpx, apscheduler, hacker-news, scraper]

# Dependency graph
requires: []
provides:
  - SQLite database at tazakhabar-backend/tazakhabar.db with 7 tables (jobs, news, trends, users, rate_limits, reports, embeddings)
  - SQLAlchemy 2.0 async models for all database tables
  - Async HN Firebase API client with parallel fetching
  - Who Is Hiring, Ask HN, Show HN, Top Stories scrapers
  - APScheduler integration with FastAPI lifespan
affects: [01-02, 01-03, frontend]

# Tech tracking
tech-stack:
  added: [fastapi, uvicorn, httpx, aiosqlite, sqlalchemy[asyncio], apscheduler, beautifulsoup4]
  patterns: [async context managers, APScheduler job scheduling, Algolia search integration, HN API consumption]

key-files:
  created:
    - tazakhabar-backend/src/db/models.py - SQLAlchemy models
    - tazakhabar-backend/src/db/database.py - Async session factory
    - tazakhabar-backend/src/scrapers/client.py - HN Firebase API client
    - tazakhabar-backend/src/scrapers/base_scraper.py - Shared scraper logic
    - tazakhabar-backend/src/scrapers/who_is_hiring.py - Job scraper
    - tazakhabar-backend/src/scrapers/ask_hn.py - Ask HN scraper
    - tazakhabar-backend/src/scrapers/show_hn.py - Show HN scraper
    - tazakhabar-backend/src/scrapers/top_stories.py - Top Stories scraper
    - tazakhabar-backend/src/scheduler.py - APScheduler integration
  modified:
    - tazakhabar-backend/src/main.py - Added lifespan with scheduler
    - tazakhabar-backend/src/config.py - Settings with origins_list
    - tazakhabar-backend/requirements.txt - Python dependencies
    - tazakhabar-backend/.env - Environment variables

key-decisions:
  - "Used aiosqlite for async SQLite access with SQLAlchemy 2.0"
  - "Algolia API for Who Is Hiring thread discovery (search by author:whoishiring)"
  - "Firebase API for HN items with asyncio.gather parallel fetching and semaphore limiting"
  - "APScheduler AsyncIOScheduler tied to FastAPI lifespan for graceful shutdown"

patterns-established:
  - "Async context managers for HTTP clients (httpx.AsyncClient)"
  - "Base scraper class with deduplication and bulk save operations"
  - "Report tracking for each scraper run (items_collected, new_items, status)"
  - "UUID primary keys for Postgres compatibility"

requirements-completed: [DB-01, DB-02, DB-03, DB-04, DB-05, DB-06, DB-07, DB-08, DB-09, DB-10, SCRP-01, SCRP-02, SCRP-03, SCRP-04, SCRP-05, SCRP-06, SCRP-07, SCRP-08]

# Metrics
duration: 45min
completed: 2026-03-20
---

# Phase 01-01: Foundation Backend Summary

**SQLite database with 7 SQLAlchemy 2.0 async models, async HN API client, and 4 scrapers (Who Is Hiring, Ask/Show HN, Top Stories) with APScheduler scheduling**

## Performance

- **Duration:** 45 min
- **Started:** 2026-03-20T17:15:00Z
- **Completed:** 2026-03-20T18:00:00Z
- **Tasks:** 3
- **Files modified:** 10 (8 new, 2 modified)

## Accomplishments
- Created tazakhabar-backend/ directory structure with FastAPI app
- Built SQLite database with SQLAlchemy 2.0 async models (Job, News, Trend, User, RateLimit, Report, Embedding)
- Implemented async HN Firebase API client with parallel fetching (asyncio.gather + semaphore)
- Created 4 HN scrapers: Who Is Hiring (Algolia discovery, comment parsing), Ask HN, Show HN, Top Stories
- Integrated APScheduler with FastAPI lifespan for graceful scheduler shutdown

## Task Commits

1. **Task 1: Backend directory structure, config, database models** - `e794a47` (part of existing commit)
2. **Task 2: HN API client with parallel fetching** - `c6faa33` (feat)
3. **Task 3: HN scrapers with APScheduler** - `c6faa33` (feat - combined with Task 2)

**Plan metadata:** `c6faa33` (feat(01-01): add FastAPI backend with HN scrapers and APScheduler)

## Files Created/Modified
- `tazakhabar-backend/src/db/models.py` - SQLAlchemy 2.0 async models (Job, News, Trend, User, RateLimit, Report, Embedding)
- `tazakhabar-backend/src/db/database.py` - Async SQLite session factory with engine and Base
- `tazakhabar-backend/src/scrapers/client.py` - Async HN Firebase API client with parallel fetching
- `tazakhabar-backend/src/scrapers/base_scraper.py` - Base scraper with deduplication and bulk saves
- `tazakhabar-backend/src/scrapers/who_is_hiring.py` - Who Is Hiring thread discovery and job parsing
- `tazakhabar-backend/src/scrapers/ask_hn.py` - Ask HN stories scraper
- `tazakhabar-backend/src/scrapers/show_hn.py` - Show HN stories scraper
- `tazakhabar-backend/src/scrapers/top_stories.py` - Top Stories scraper (score > 100)
- `tazakhabar-backend/src/scheduler.py` - APScheduler AsyncIOScheduler with job registration
- `tazakhabar-backend/src/main.py` - FastAPI lifespan with database creation and scheduler
- `tazakhabar-backend/requirements.txt` - Python dependencies (fixed google-genai version)
- `tazakhabar-backend/.env` - Environment variables with DATABASE_URL

## Decisions Made
- Used aiosqlite with SQLAlchemy 2.0 for async SQLite database access
- Algolia API for Who Is Hiring thread discovery (author:whoishiring filter)
- Firebase API for HN items with asyncio.gather + semaphore for parallel fetching
- APScheduler AsyncIOScheduler tied to FastAPI lifespan for graceful shutdown on SIGTERM
- Exponential backoff with jitter on 429 rate limit errors (3 retries, backoff_factor=0.5)
- Report version "2" for all new scraped data

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed google-genai version in requirements.txt**
- **Found during:** Task 1 (Dependency installation)
- **Issue:** google-genai==0.3.2 does not exist in PyPI
- **Fix:** Updated to google-genai==1.67.0
- **Files modified:** tazakhabar-backend/requirements.txt
- **Verification:** pip install succeeded
- **Committed in:** c6faa33 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed DATABASE_URL path in .env**
- **Found during:** Task 1 (Database verification)
- **Issue:** DATABASE_URL was `./tazakhabar-backend/tazakhabar.db` but running from tazakhabar-backend/ directory
- **Fix:** Changed to `./tazakhabar.db` (relative to working directory)
- **Files modified:** tazakhabar-backend/.env
- **Verification:** Database file created at correct location
- **Committed in:** c6faa33 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking issues)
**Impact on plan:** Both fixes required for basic functionality. No scope creep.

## Issues Encountered
- SQLite aiosqlite path resolution required .env adjustment
- google-genai package version doesn't exist in PyPI (used newer version)

## Next Phase Readiness
- Database schema complete and verified
- All scrapers importable and instantiable
- HNClient verified working with live HN API
- Ready for 01-02 (API endpoints) and 01-03 (Frontend API integration)

---
*Phase: 01-foundation-backend*
*Completed: 2026-03-20*
