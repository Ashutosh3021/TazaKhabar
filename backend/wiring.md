# TazaKhabar Backend — Wiring & Deployment Guide

This document explains how the FastAPI backend is wired: startup order, data pipelines, APIs, database, and how to deploy it.

---

## 1. High-level architecture

```mermaid
flowchart TB
    subgraph clients [Clients]
        FE[Next.js frontend]
        NB[Jupyter notebooks]
    end

    subgraph api [FastAPI - src/main.py]
        ROUTERS[API routers]
        LIFE[lifespan startup/shutdown]
    end

    subgraph data_in [Data ingestion]
        CSV[jobs_output.csv]
        WATCH[Notebook CSV watcher]
        SCHED[APScheduler]
        HN[HN scrapers]
    end

    subgraph core [Core services]
        DB[(PostgreSQL / SQLite)]
        LLM[llm_service]
        EMB[embedding_service]
        TREND[trend_service]
        RESUME[resume_service]
    end

    FE -->|HTTP + CORS| ROUTERS
    NB -->|writes CSV / push_to_app| CSV
    NB -->|POST /api/notebooks/sync| ROUTERS
    LIFE --> DB
    LIFE --> EMB
    LIFE --> WATCH
    LIFE --> SCHED
    CSV --> WATCH
    WATCH --> DB
    SCHED --> HN
    HN --> DB
    ROUTERS --> DB
    ROUTERS --> LLM
    ROUTERS --> EMB
    ROUTERS --> TREND
    ROUTERS --> RESUME
```

**Entry point:** `uvicorn src.main:app` (run from `backend/` directory).

---

## 2. Repository layout (`backend/`)

| Path | Role |
|------|------|
| `src/main.py` | FastAPI app, lifespan, router registration, `/health` |
| `src/config.py` | Settings from `.env` (Pydantic) |
| `src/api/` | HTTP route handlers (thin layer) |
| `src/services/` | Business logic (LLM, trends, CSV, resume, digest, etc.) |
| `src/db/` | SQLAlchemy models, async engine, sessions |
| `src/scrapers/` | Hacker News scrapers (Algolia + Firebase) |
| `src/scheduler.py` | APScheduler cron jobs |
| `src/middleware/` | Request logging |
| `NoteBooks/` | Jupyter pipelines + CSV outputs |
| `NoteBooks/push_to_app.py` | Call sync API from notebooks |
| `requirements.txt` | Python dependencies |
| `.env` | Secrets (copy from `.env.example`) |
| `logs/` | `tazakhabar.log` (created at runtime) |

---

## 3. Startup sequence (lifespan)

When Uvicorn loads `src.main:app`, this runs **once** before accepting traffic:

| Step | What happens | Module |
|------|----------------|--------|
| 1 | Load `.env` → `settings` | `config.py` |
| 2 | Create DB tables if missing | `db/database.py` → `create_all_tables()` |
| 3 | Load sentence-transformers embedding model (CPU) | `embedding_service.py` |
| 4 | Sync `NoteBooks/jobs_output.csv` → `jobs` table | `notebook_sync_service.py` |
| 5 | Start background CSV watcher (every 15s default) | `notebook_sync_service.py` |
| 6 | Start APScheduler (HN scrapers + trends + embeddings) | `scheduler.py` |

On shutdown: scheduler stops, CSV watcher task cancelled.

**Health check:** `GET /health` → `{"status": "healthy", ...}` (used by Railway/containers).

---

## 4. Data pipelines

### 4A. Notebook pipeline (primary for AmbitionBox jobs)

Intended workflow for local / manual job collection:

```text
scrapper.ipynb
    └── company_data.csv          (company list — NOT loaded to DB)

job_scraper.ipynb
    └── jobs_output.csv           (append while scraping)
            │
            ├── Auto: notebook watcher (every NOTEBOOK_SYNC_INTERVAL_SEC)
            ├── Auto: backend startup sync
            └── Manual: push_to_app.sync_jobs_to_app()
                    or POST /api/notebooks/sync
            │
            ▼
        jobs table (report_version = "2")
```

- **Incremental sync:** only new CSV rows are imported after the first run (state in `NoteBooks/.notebook_sync_state.json`).
- **Upsert key:** `title` + `company` + `apply_link`.

### 4B. Hacker News pipeline (scheduler + notebook)

```text
tazakhabar_scraper.ipynb  OR  APScheduler (every 2h)
    │
    ├── Who Is Hiring  → jobs table
    ├── Top Stories    → news table
    ├── Ask HN         → news table
    └── Show HN        → news table

Daily midnight UTC: compute_keyword_frequencies + LLM observation → trends, observations tables
Daily 03:00 UTC: embeddings backfill for jobs/news
```

Manual trigger: `POST /api/scrape/run` or `POST /api/notebooks/sync-hn`.

### 4C. Report versions (jobs & news)

| `report_version` | Meaning |
|------------------|---------|
| `"2"` | Staging — new scrapes / CSV imports land here first |
| `"1"` | Live — promoted feed after user refresh |
| `"archived"` | Old live data; purged after 7 days |

- **Jobs API** (`GET /api/jobs`) reads **`"1"` and `"2"`** so both staging and live appear in the app.
- **News API** reads **`"1"`** (live).
- **`POST /api/refresh`** runs `advance_report_cycle()`: `1→archived`, `2→1`, badge counts reset.

---

## 5. Database

### Engine (`src/db/database.py`)

- **Async SQLAlchemy 2.0** via `create_async_engine` + `async_sessionmaker`.
- **Drivers:**
  - Local: `sqlite+aiosqlite:///./tazakhabar.db`
  - Production (Supabase): `postgresql+asyncpg://...`
- Bare `postgresql://` in `.env` is auto-upgraded to `postgresql+asyncpg://` in `config.py`.
- Supabase pooler (port 6543): `statement_cache_size=0` on asyncpg connections.

### Main tables (`src/db/models.py`)

| Table | Purpose |
|-------|---------|
| `jobs` | Job listings (HN + CSV); `tags` stored as JSON/JSONB |
| `news` | HN stories (ask/show/top) |
| `trends` | Weekly keyword counts |
| `trend_predictions` | W+2 / W+4 predictions |
| `users` | Profiles, ATS fields, resume text |
| `observations` | LLM market observation paragraph |
| `embeddings` | Vectors for digest / personalization |
| `reports` | Report swap audit |

### Sessions in routes

- Prefer `Depends(get_db)` from `src/api/deps.py` (yields `AsyncSession`).
- Some code uses `async_session()` context manager directly (scheduler, notebooks sync).

---

## 6. API map

All routes are prefixed as below. Interactive docs: `http://localhost:8000/docs`.

| Prefix | Purpose |
|--------|---------|
| `GET /`, `GET /health` | Root info & health |
| `/api/jobs` | Paginated job feed (filters, personalization) |
| `/api/news` | News feed |
| `/api/trends` | Trending keywords, predictions, compute trigger |
| `/api/badge` | New jobs/news counts since last refresh |
| `/api/refresh` | Promote report v2 → v1 |
| `/api/observation` | Latest market observation text |
| `/api/resume` | `POST /analyse` — PDF/TXT ATS + suggestions |
| `/api/profile` | User profile CRUD |
| `/api/digest` | Personalized news digest |
| `/api/qa` | Career bot (chat, market velocity, matches) |
| `/api/csv` | CSV stats; `POST /load-jobs` (= notebook sync) |
| `/api/notebooks` | **`POST /sync`**, `GET /status`, `POST /sync-hn` |
| `/api/scrape` | `POST /run` — all HN scrapers now |
| `/api/embeddings` | `POST /backfill` |

**Frontend header:** many endpoints accept `X-User-ID` for logged-in behavior.

---

## 7. External services

| Service | Used for | Config |
|---------|----------|--------|
| **Supabase Postgres** | Primary DB in production | `DATABASE_URL` |
| **Supabase Storage** | Resume file upload | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| **Groq / OpenRouter** | LLM (QA chat, ATS, summaries, observations) | `GROQ_API_KEY`, `OPENROUTER_API_KEY` |
| **sentence-transformers** | Local embeddings (`all-MiniLM-L6-v2`) | Bundled at startup |
| **Hacker News** | Algolia + Firebase APIs | No key (scrapers) |

---

## 8. Background jobs (scheduler)

| Job ID | Schedule (UTC) | Action |
|--------|----------------|--------|
| `who_is_hiring` | Every 2 hours | Scrape HN hiring → `jobs` |
| `top_stories` | Every 2 hours | Top stories → `news` |
| `ask_hn` | Every 2 hours | Ask HN → `news` |
| `show_hn` | Every 2 hours | Show HN → `news` |
| `compute_trends` | Daily 00:00 | Trends + observation LLM |
| `embeddings_backfill` | Daily 03:00 | Missing embeddings |

Scheduler only runs while the **backend process** is up (not in serverless cold starts unless you use a always-on worker).

---

## 9. Local deployment

### Prerequisites

- Python **3.10+**
- `backend/.env` filled from `.env.example`
- For Postgres: `asyncpg` installed (`pip install -r requirements.txt`)

### Commands

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edit .env — at minimum DATABASE_URL and API keys

mkdir logs -Force
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend connection

Set in the Next.js app:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Ensure `ALLOWED_ORIGINS` in backend `.env` includes your frontend URL.

### Notebook workflow (jobs)

1. Start backend (above).
2. Run `NoteBooks/scrapper.ipynb` → `company_data.csv`.
3. Run `NoteBooks/job_scraper.ipynb` → `jobs_output.csv` (syncs automatically or via `push_to_app`).
4. Open app — jobs appear on `/api/jobs`.

### HN data without notebooks

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/notebooks/sync-hn"
```

---

## 10. Production deployment (e.g. Railway, VPS, Docker)

### Checklist

1. **Environment variables** — set all secrets in the host dashboard (never commit `.env`).
2. **DATABASE_URL** — use `postgresql+asyncpg://` (Supabase pooler: port `6543`, add SSL if required).
3. **Process** — long-running worker, not ephemeral serverless, if you need:
   - APScheduler
   - Notebook CSV watcher
   - In-memory embedding model
4. **Start command:**

   ```bash
   cd backend && uvicorn src.main:app --host 0.0.0.0 --port $PORT
   ```

5. **Health check path:** `/health`
6. **CORS:** set `ALLOWED_ORIGINS` to your production frontend URL(s).
7. **Logs:** stdout + `logs/tazakhabar.log` — mount volume or use platform log drain.
8. **Notebooks / CSV:** production usually **does not** run Jupyter on the same box; either:
   - Run notebooks locally and rely on DB being shared (Supabase), or
   - Upload `jobs_output.csv` and call `POST /api/notebooks/sync`, or
   - Use scheduled HN scrapers only.

### Supabase-specific

```env
DATABASE_URL=postgresql+asyncpg://USER:PASS@aws-REGION.pooler.supabase.com:6543/postgres
```

`config.py` normalizes bare `postgresql://` URLs. asyncpg uses `statement_cache_size=0` for PgBouncer transaction mode.

### Optional: disable notebook watcher in production

```env
NOTEBOOK_SYNC_ENABLED=false
```

Use HN scheduler + direct DB writes instead.

---

## 11. Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Async DB URL (`sqlite+aiosqlite` or `postgresql+asyncpg`) |
| `GROQ_API_KEY` | For QA/chat | Groq LLM |
| `OPENROUTER_API_KEY` | For ATS/summaries | OpenRouter / Gemini routes |
| `ALLOWED_ORIGINS` | Yes (prod) | Comma-separated CORS origins |
| `LOG_LEVEL` | No | Default `INFO` |
| `SUPABASE_URL` | For resume storage | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | For resume storage | Service role key |
| `NOTEBOOK_SYNC_ENABLED` | No | Default `true` — CSV polling |
| `NOTEBOOK_SYNC_INTERVAL_SEC` | No | Default `15` |
| `TAZA_API_URL` | No | Default `http://localhost:8000` — used by `push_to_app.py` |
| `SECRET_KEY` | Recommended | App signing |
| `SENTRY_DSN` | No | Error tracking |

See `backend/.env.example` for the full template.

---

## 12. Request flow examples

### Load jobs in the app

```text
Browser → GET /api/jobs?skip=0&limit=50
       → jobs.py → SQLAlchemy → jobs WHERE report_version IN ('1','2')
       → JSON paginated response
```

### Resume analysis

```text
Browser → POST /api/resume/analyse (multipart PDF)
       → resume_service.extract_text → analyze_resume_ats (LLM)
       → generate_suggested_additions (LLM + trends)
       → optional: save to users table + Supabase storage
```

### After notebook scrape

```text
job_scraper.ipynb saves jobs_output.csv
       → watcher detects mtime change (≤15s)
       → csv_loader_service.load_jobs_from_csv(start_row=N)
       → upsert into jobs
       → frontend poll /api/jobs sees new rows
```

---

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `psycopg2 is not async` | Sync Postgres URL/driver | Use `postgresql+asyncpg://`; `pip install asyncpg` |
| `array_to_string(jsonb...)` | Old SQL on JSON tags | Pull latest `qa.py` (uses `cast(tags, String)`) |
| 0 jobs in app | Empty DB or wrong report filter | Run notebook sync or `POST /api/notebooks/sync`; check CSV row count via `GET /api/csv/stats` |
| DuplicatePreparedStatement | Supabase pooler + asyncpg | Already handled via `statement_cache_size=0` |
| Scheduler not running | Process exited / serverless | Keep one long-lived Uvicorn worker |
| CORS errors | Origin not allowed | Add frontend URL to `ALLOWED_ORIGINS` |
| Notebook sync fails | Backend not running | Start Uvicorn before `push_to_app` |

---

## 14. Quick reference commands

```powershell
# Dev server
uvicorn src.main:app --reload --port 8000

# Sync notebook CSV now
Invoke-RestMethod -Method POST http://localhost:8000/api/notebooks/sync

# Run HN scrapers now
Invoke-RestMethod -Method POST http://localhost:8000/api/scrape/run

# Promote staging jobs to live feed
Invoke-RestMethod -Method POST http://localhost:8000/api/refresh

# CSV / sync status
Invoke-RestMethod http://localhost:8000/api/notebooks/status
```

---

*Last aligned with backend layout under `TazaKhabar/backend/` — update this file when adding routers, pipelines, or env vars.*
