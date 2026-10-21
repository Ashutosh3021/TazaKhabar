# TazaKhabar — Rearch Fix Plan

Status: proposed. Owner: you. Reviews findings come from the cold-eyes design review of
this repo (code + README/DESIGN.md); this doc is the single list of what gets fixed and how.

## Decisions already made

1. **Scraping moves to GitHub Actions CI** (scheduled workflow). Render stops running
   scrapers and stops owning any scraped data → the Render free-tier storage-full and
   ephemeral-disk problems disappear by construction.
2. **Pyronites is the backend platform**: auth, tables, and file storage. Supabase is
   retired (storage, auth, SMTP usage). The SQLAlchemy/SQLite data layer is replaced by
   the `pyronites` client.

## Status (implemented)

| Phase | State | Where |
|---|---|---|
| A0 provisioning | done | `backend/scripts/pyro_provision.py`, project `tazakhabar`, 10 app tables + smoke test |
| A1 backend auth | done | `backend/src/api/auth.py`, `backend/src/auth_session.py`, `backend/src/api/deps.py` |
| A2 frontend auth | done | `src/app/auth/page.tsx`, `src/lib/api.ts`, `src/middleware.ts` |
| B data layer | done | `backend/src/db/pyro.py`, `backend/src/db/repos.py`, all services and endpoints converted |
| C CI scraping | done | `.github/workflows/scrape.yml`, `.github/workflows/embeddings.yml`, `render.yaml` |
| D freshness model | done | `report_version` removed, per-user badge in `backend/src/api/badge.py` |
| E hardening and docs | done | `README.md` rewritten, `.env.example` added, stale tests removed |

Verification scripts (all green against the live Pyronites backend):
`backend/scripts/check_auth_flow.py` (8 checks), `backend/scripts/check_api_flow.py` (16 checks),
`python -m src.cli check-pyronites`. A live scrape wrote 334 jobs and 16 news rows to
Pyronites through the CI code path.


## Target architecture

```
                    cron */2h + manual
GitHub Actions ────────────────────────────┐
 (scrapers, batch LLM, embeddings)         │  PYRONITES_KEY (write), LLM keys
                                           ▼
Browser ◀──HTTPS──▶ Vercel Next.js     Pyronites backend
   │                  │  session cookie     │  tables: profiles, jobs, news,
   │                  ▼                     │  trends, observations, embeddings,
   └────HTTPS────▶ Render FastAPI ──────────┘  rate_limits, scraper_state
                (stateless read/LLM API,      storage: resume files
                 auth proxy, no local disk)
```

- Render service becomes **stateless**: no SQLite, no APScheduler, no notebook watcher,
  no keep-alive requirement (sleeping is fine when the DB is remote).
- All writes from CI use Pyronites with a `read`/`write` key from GitHub Secrets.
- Auth identity is whatever Pyronites says the session is. `X-User-ID` dies.

---

## Findings → fixes

| # | Severity | Finding (evidence) | Fix | Phase |
|---|---|---|---|---|
| 1 | Critical | No auth at all: login page only sets React state (`src/app/auth/page.tsx:51`); identity is spoofable `X-User-ID` from localStorage (`src/lib/api.ts:39`); no Supabase SDK, no `middleware.ts` | Pyronites signup/login proxied through FastAPI, httpOnly session cookie, `require_user` dependency on every private endpoint, route-gating `src/middleware.ts` | A |
| 2 | Critical | Public LLM/mutation endpoints: `/api/qa/chat` has no rate limit (`qa.py:307-353`); `/api/scrape/run`, `/api/refresh`, `/api/csv/load-jobs` open; limits keyed on spoofable header (`llm_service.py:267`) | Auth-gate chat/resume/profile/digest; delete `/api/scrape/run` + `/api/refresh` (CI owns scraping, see Phase C/D); admin-token guard for CSV/notebook endpoints; rate limits keyed on verified user id + IP fallback | A/E |
| 3 | Critical | Ephemeral SQLite is system of record: `render.yaml` sets no `DATABASE_URL` → `config.py:33` default file on free-tier disk with `autoDeploy: true`; trends need 8 weeks of history | Pyronites tables replace SQLite (Phase B). Also switch Render to stdout-only logging (`main.py:29` FileHandler writes `logs/tazakhabar.log` to the same disk) | B |
| 4 | Critical | Dead freshness loop: badge counts `report_version=="1"` (`report_service.py:105`) but scrapers write `"2"` (`base_scraper.py:153`) → badge ≈ 0 → refresh banner gated on badge>0 (`TopNav.tsx:142`) never shows → news (`news.py:87`), digest (`digest_service.py:74`), trends (`trend_service.py:168`) read only `"1"` → stay empty on fresh DB; jobs read `"1"+"2"` (`jobs.py:172`) so UI is half-working; swap is global for all users | Delete `report_version` / Report 1-2 swap / `advance_report_cycle` entirely. Newness = per-user `feed_last_seen_at` on `profiles`; badge = `count where scraped_at > last_seen`; "Swap report" button becomes "Mark seen" (`POST /api/badge/seen`) | D |
| 5 | High | Trends computed over an arbitrary slice: `compute_keyword_frequencies` filters `report_version=="1"` (`trend_service.py:166-173`); archived rows excluded and purged after 7 days (`report_service.py:47-59`) → week-over-week % depends on when a human clicked swap; predictions train on noise | Count by date window (`scraped_at BETWEEN week_start/week_end`) over all rows; raw rows may only be purged after their counts are aggregated into `trends` (aggregation is the durable record) | D |
| 6 | High | RAG off in prod but advertised DONE: `render.yaml:19` sets `EMBEDDINGS_ENABLED=false`; digest silently falls back to score-sort (`digest_service.py:84`) | Compute embeddings in the CI job (CPU is fine for MiniLM; cache the model with `actions/cache`) and store as BLOB in Pyronites `embeddings`; if that doesn't land, edit README to stop claiming semantic RAG. Pick one | C |
| 7 | Medium | Doc/test drift: Supabase migration shown as done (README Stage 7) vs TODO (README:711); badge documented as 5-min poll with wrong field names (README:626, 697) vs actual 60s (`TopNav.tsx:50`); `Test/P1.py:90` imports non-existent `swap_reports`/`get_last_swap_time` and expects `int` from `advance_report_cycle` (returns dict); docs say Railway, config says Render | Rewrite README system-workflow/deployment sections from actual behavior in the same PR as each phase; delete or fix stale `Test/P1.py` so it can gate anything | E |
| 8 | Medium | CORS: `ALLOWED_ORIGINS` defaults to localhost + 2 hardcoded Vercel domains (`config.py:51`); `render.yaml` never sets it; README suggests `https://*.vercel.app` which Starlette matches literally (no wildcard support) | Set exact prod origin in `render.yaml` envVars; never wildcard | E |
| 9 | Medium | `/health` returns healthy without touching data (`main.py:250`) while `render.yaml:9` uses it for health checks | Check Pyronites `/health` (and drop scheduler check — there is no scheduler anymore) | E |
| 10 | Low | CSV loader contract mismatch: frontend sends `limit`/`clear_existing` (`api.ts:369-390`), backend accepts neither (`csv_loader.py:29`) | Remove dead params from `api.ts`, or implement them | E |
| 11 | Low | In-process APScheduler + watcher + fire-and-forget LLM tasks in one uvicorn worker; double-scraping race if ever scaled (`report_service.py:16` lock is per-process) | Removed by Phase C (no scheduler in FastAPI) | C |
| 12 | Low | `fetchJobs` never sends identity (`api.ts:75-78`) → personalization branch (`jobs.py:200`) dead from web client | Moot after auth rework: API client sends the session cookie/`Authorization` uniformly | A |

---

## Phase A — Pyronites provisioning + real auth

### A0. Provisioning inputs (collect first, nothing is invented)

Per the pyronites-wiring skill, I need from you before any provisioning runs:

- [ ] `PYRONITES_URL` — your Pyronase backend base URL (deployed, or `http://localhost:8000` if local first)
- [ ] account `email`
- [ ] `password` (via `PYRONITES_PASSWORD` env or getpass — never pasted in chat/shell args)
- [ ] admin API key, or authorization to mint one via your session
- [ ] `project_id` — read from `GET /auth/me → last_project_id`, **you confirm the exact id before any table is created**

Provisioning sequence (scripted, from the skill):
1. `GET $PYRONITES_URL/health` → 200.
2. signup → fallback login on 409; single `requests.Session`.
3. resolve + confirm `project_id`; pin as `PYRONITES_PROJECT_ID`.
4. mint keys: one `read`/`write` key for app+CI (this is the only key that exists in
   Render env and GitHub Secrets), one `admin` key used only now for table creation and
   then revoked/rotated offline. Keys go to `.env` chmod 600, `.env` git-ignored —
   never printed, never committed.
5. create tables (after you approve the target project):
   - `profiles` (**not `users`** — reserved by Pyronites), `jobs`, `news`, `trends`,
     `trend_predictions`, `observations`, `rate_limits`, `notifications`,
     `embeddings` (embedding as BLOB), `scraper_state` (key/value for `.last_wih_thread`
     etc., so CI has no local files)
   - Column types restricted to `TEXT INTEGER REAL BLOB NUMERIC BOOLEAN DATETIME DATE JSON`;
     map models from `backend/src/db/models.py`, **drop `report_version` from `jobs`/`news`**,
     add `feed_last_seen_at DATETIME` to `profiles`.
   - `GET .../tables` first; if a table exists, inspect schema instead of recreating.
6. `pip install pyronites` (PyPI only — no repo checkout, per skill hard rules).
7. Smoke test: insert → select → delete on `profiles` in the confirmed project.

### A1. FastAPI auth layer

New `backend/src/api/auth.py` (thin proxy — keys stay server-side, the browser never
talks to Pyronites directly):

- `POST /api/auth/signup`, `POST /api/auth/login` → pyronites auth; forward
  `session_token` as httpOnly, Secure, SameSite=Lax cookie.
- `POST /api/auth/logout`, `GET /api/auth/me` → `{id, email}`.
- `require_user` dependency: resolve cookie → verified user id via Pyronites
  (`client.auth.user()`-equivalent; **verify exact call against the installed package**,
  skill hard rule 3). No header identity anywhere after this.

Replace `X-User-ID` handling in: `profile.py`, `resume.py`, `digest.py`, `qa.py`,
`jobs.py` (personalize branch). Rewrite `check_rate_limit`/`increment_rate_limit`
(`llm_service.py:258-326`) to use the verified id (table `rate_limits`), IP-keyed only
when anonymous. Add the limiter to `POST /api/qa/chat`.

### A2. Frontend

- Rewrite `src/app/auth/page.tsx`: call `/api/auth/signup|login`, keep the real password
  field, surface errors. Store only `{id, email}` in context after `/api/auth/me`.
- `src/lib/api.ts`: delete `getUserIdHeader()`; browser sends the cookie
  (`credentials: "include"`) on every call; `fetchJobs` included (fixes #12).
- Add `src/middleware.ts`: no valid session cookie → redirect `/jobs`, `/digest`,
  `/trends`, `/profile`, `/qa`, `/setup/*` to `/auth`. (Presence-check only; the API
  does authoritative validation.)

### Verify A
- [ ] signup/login/logout round-trip works end-to-end in prod
- [ ] `curl -H "X-User-ID: <anything>" $API/api/profile` returns 401/empty-identity, not data
- [ ] chat endpoint returns 429 after the daily limit for one verified user; new random
      headers do NOT reset the limit
- [ ] `grep -r "X-User-ID" src backend/src` → zero matches outside git history

---

## Phase B — Data layer: SQLAlchemy/SQLite → pyronites client

Biggest workstream. Everything in `src/db/*`, `src/api/*`, `src/services/*` that touches
`async_session` gets rewritten to the client query builder
(`client.table("jobs").select().eq(...).order(...)` etc.).

1. New `backend/src/db/pyro.py`: `create_client(url, key)` singleton from env;
   `PYRONITES_URL`, `PYRONITES_KEY`, `PYRONITES_PROJECT_ID` in `config.py`.
2. Migrate each service: `base_scraper` save paths (upsert by `hn_item_id`),
   `report_service` (delete), `trend_service`, `digest_service`, `embedding_service`
   (BLOB round-trip), `resume_service` writes, `notifications`, rate limits.
3. Resume files: `supabase.py` storage upload → `client.storage.upload/download`;
   `resume_path` stores the Pyronites file id.
4. Delete: `src/db/database.py`, `src/db/models.py`, `src/db/schemas.py` (Pydantic
   response models stay, ORM goes), `src/db/supabase.py`, `tazakhabar.db`,
   `normalize_async_database_url`, the `create_all_tables` startup block
   (`main.py:76-84`), `supabase_diagnostic.py`.
5. Data seeding: export existing SQLite/Supabase rows → bulk insert to Pyronites, or
   start fresh (hobby data volume; your call — CI repopulates jobs/news within a day).
6. Health check reads Pyronites `/health`.

### Verify B
- [ ] `grep -rn "sqlalchemy\|aiosqlite\|DATABASE_URL" backend/src` → no matches
- [ ] every endpoint returns real data against Pyronites (jobs, news, trends, digest,
      profile, resume, badge-after-Phase-D)
- [ ] resume upload → storage → download round-trip
- [ ] deploy; restart Render; **data still there** (the #3 regression test)

---

## Phase C — Scraping + batch work → GitHub Actions

New `.github/workflows/scrape.yml`:

```yaml
name: scrape
on:
  schedule:
    - cron: "0 */2 * * *"   # every 2h, matches current cadence
  workflow_dispatch:
concurrency: { group: scrape, cancel-in-progress: false }
jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: pip }
      - run: pip install -r backend/requirements.ci.txt   # scrapers + pyronites + httpx; NO torch
      - uses: actions/cache@v4                            # only if embeddings move into CI
        with: { path: ~/.cache/huggingface, key: minilm }
      - run: python -m src.cli ci-run                     # scrapers → batch summarize → (embed) → (trends)
        env:
          PYRONITES_URL: ${{ secrets.PYRONITES_URL }}
          PYRONITES_KEY: ${{ secrets.PYRONITES_KEY }}
          PYRONITES_PROJECT_ID: ${{ secrets.PYRONITES_PROJECT_ID }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

- New `src/cli.py` command `ci-run`: runs all 4 scrapers + notification queue check +
  batch LLM (top-news summarization, midnight observation → run observation in this
  workflow when `date -u +%H == 0`, or a second daily workflow) + optional embeddings.
  Scraper state (`.last_wih_thread`) reads/writes the Pyronites `scraper_state` table —
  the runner is stateless.
- Failure alerting: GitHub emails workflow failures by default; optionally add a
  failure-badge step.
- `concurrency` without cancel prevents overlapping runs; `timeout-minutes` caps a hung
  HN call.

### Render cleanup (same PR)
- Delete from `main.py` lifespan: scheduler start/stop, notebook watcher, keep-alive
  block; delete `src/scheduler.py`, `src/services/notebook_sync_service.py` wiring,
  `NOTEBOOK_*`/`KEEPALIVE_*` settings; drop those envVars from `render.yaml`.
- Keep interactive LLM (ATS scoring, chat, suggestions) on Render — that's request-scoped
  work. Batch LLM keys live in GitHub Secrets; interactive keys stay in Render env
  (splitting limits the blast radius of one leak).
- Notebook pipeline (`NoteBooks/*.csv` + `push_to_app.py`): make it a dev-only local
  command, or fold CSV ingestion into `ci-run`. Remove the 15s watcher from prod.
- Logging: Render → stdout only (drop `FileHandler`, `main.py:29`) so the app writes
  zero bytes to Render's disk.

### Verify C
- [ ] `workflow_dispatch` run populates `jobs`/`news` from zero
- [ ] two scheduled runs in the log, no overlap (concurrency group)
- [ ] Render redeploy after CI run → data intact
- [ ] `grep -rn "start_scheduler\|APScheduler" backend/src` → no matches

---

## Phase D — Freshness model: kill report_version

1. **Badge**: `GET /api/badge` → counts of `jobs`/`news` where
   `scraped_at > profiles.feed_last_seen_at` for the verified user. `POST /api/badge/seen`
   updates it. No global state, no swap, per-user, survives devices.
2. **Feeds**: remove every `report_version` filter (`news.py:87`, `jobs.py:172`,
   `digest_service.py:74,89`, `trend_service.py:166-173`); query all rows (optionally
   `scraped_at > now-30d` for feed window).
3. **Delete**: `report_service.py` swap + purge, `/api/refresh` endpoint,
   `Report` model/table, `triggerRefresh` in `api.ts`, the "Swap report" banner button
   → replaced by "Mark seen" (`TopNav.tsx:163-170`).
4. **Trends**: `compute_keyword_frequencies` groups by week purely from `scraped_at`
   over all rows; nightly CI job upserts `trends` rows; raw-row purge (if ever needed)
   only after aggregation exists.
5. Badge polling stays at 60s (it's cheap); update README to say 60s, not 5min.

### Verify D
- [ ] fresh Pyronites project → run CI once → news/digest/trends render non-empty with
      no manual `curl /api/refresh` (the old closed-loop bug)
- [ ] user A "mark seen" does not change user B's badge
- [ ] trends week-over-week stable across a weekend with no deploys/clicks
- [ ] `grep -rn "report_version\|advance_report_cycle" backend/src src` → no matches

---

## Phase E — Hardening + doc truth

1. Remove/guard public mutation endpoints: delete `POST /api/scrape/run`; CSV/notebook
   sync endpoints behind an `ADMIN_TOKEN` header (or dev-only mount) — CI is the
   sanctioned writer now.
2. `ALLOWED_ORIGINS` set explicitly in `render.yaml` to the exact Vercel origin.
3. `/health` = Pyronites ping; keep it cheap, it's the healthCheckPath.
4. CSV loader params: fix `api.ts:369-390` or backend (either direction, not both).
5. README: rewrite deployment diagram (Vercel + Render-stateless + Pyronites + GH
   Actions), workflow sections, environment variables, verification checklist; remove
   Supabase/Railway/SQLite claims; fix badge field names (`new_jobs`/`new_news`).
   README status table updated in the same PR as each phase lands.
6. Tests: fix or delete `Test/P1.py` stale imports; add one smoke test per phase's
   verify checklist so the suite gates real behavior.

---

## Sequencing and risk

```
A (auth+provisioning) ──▶ B (data layer) ──▶ C (CI scraping) ──▶ D (freshness) ──▶ E (hardening)
        │                      │                   │
     needs A0 inputs        biggest PR         can start in parallel
                                          after A0 (CI only needs Pyronites
                                          tables to exist, not the FastAPI rewrite)
```

- **B is the bulk of the work** — every service touches the session layer. Ship it as
  one PR behind a feature flag is not practical here; instead ship B in the order
  read-paths first (jobs/news/trends GETs), then write-paths (scrape → CI, resume,
  profile), keeping SQLite working until the last read-path flips.
- C can start as soon as A0 tables exist — it doesn't wait for B's FastAPI rewrite,
  only for the scraper save-path to speak pyronites.
- Honest note: Pyronites-for-everything means `pyronites` is now a hard dependency of
  auth + data + storage. Per the skill, verify every unfamiliar call against the
  installed package's source, not memory or any repo.

## Global verify (end state)

- [ ] All 12 findings have a passing line in their phase's verify checklist
- [ ] `grep -r "X-User-ID\|report_version\|sqlalchemy\|APScheduler\|supabase" backend/src src`
      → empty
- [ ] Render disk usage flat for a week (no SQLite, stdout logs only)
- [ ] CI green for 3 consecutive scheduled runs
- [ ] README reproduces reality: follow it on a clean machine and the product works

---

## Implementation notes (what reality forced)

1. **The pip client could not be used.** `pyronites` 1.2.1 (latest on PyPI) calls the
   unscoped paths `/tables`, `/tables/{name}`, `/storage/*`. The deployed backend rejects
   those for a project-scoped key with
   `403 "This API key belongs to a project-scoped endpoint; use /api/projects/{project_id}/..."`.
   The data layer is therefore a small httpx client of our own,
   `backend/src/db/pyro.py`, using the project-scoped paths the backend documents in
   `/openapi.json`. Version 1.3.0 (checked 2026-10-21) is byte-identical to 1.2.1 apart
   from the `__version__` string: still unscoped paths, no `order()`, no range filters,
   no upsert, and the row insert still loops one request per row. The backend also
   ignores `order_by` / `sort` on the row API, so the SQL endpoint stays the only way
   to order or range-query. The app does not import the pip package at all.
2. **Row endpoints address rows by `id`.** `/tables/{table}/{id}` looks the row up by its
   `id` column, so a differently named primary key breaks row deletes (500). Every table
   now has an `id` column; `scraper_state` uses `id` plus a separate `state_key`.
3. **BLOB columns cannot carry vectors.** A blob comes back as text through the row API
   and as `<blob 5 bytes>` through SQL, and arbitrary bytes do not survive the text
   round trip. Embeddings are stored base64 encoded in a TEXT column.
4. **The SQL endpoint accepts a read/write key.** `POST .../sql/execute` works with the
   `read`/`write` app key, one statement per request (a multi-statement call returns the
   first result only). Values are escaped by `sql_literal`, identifiers by `sql_ident`.
5. **The owner account has no password.** `POST /auth/login` with the supplied password
   returns "Incorrect email or password": the account is Google-OAuth only. The app uses
   email and password signup and login, so the owner needs to set a password once through
   the forgot-password flow (`POST /api/auth/password/forgot`).
6. **Embeddings got their own workflow.** Torch does not belong in the 2-hour scrape job,
   so `embeddings.yml` runs the backfill daily and the API only reads the vectors.
7. **Freshness is per user.** `profiles.feed_last_seen_at` replaced the global report
   swap; the badge and the "Mark as seen" button use it, and the swap endpoint is gone.
8. **The schedules are three jobs, not one.** The scrape cycle is every 2 hours
   (`0 */2 * * *` UTC), the trend recount plus the market observation is daily
   (`15 0 * * *` UTC) and the embedding backfill is daily (`30 3 * * *` UTC). The first
   cut ran the trends and the observation inside every scrape cycle, which meant twelve
   LLM calls and twelve full-week scans a day for no extra insight.

---

## Measured load: old build vs new build

Measured with `backend/scripts/measure_load.py`, `measure_latency.py` and
`measure_scrape.py` (old build = git HEAD, new build = working tree, same request
load on both).

| Metric | Old (git HEAD on Render) | New (Render serves the API only) | Change |
|---|---|---|---|
| Batch work on the instance | 6.5 CPU-s per 2h cycle, 97 s wall occupancy, plus 20 LLM summarisation calls | 0, runs in GitHub Actions | **−100%** |
| Disk writes | SQLite file + log file on the free disk | none | **−100%** |
| Idle / peak RAM | 180.4 / 181 MB | 163.5 / 164 MB | **−9.4%** |
| CPU per API request | 9.4 ms | 5.2 ms | **−45%** |
| Instance hours | keepalive ping every 840 s, always awake | sleeps when idle | hours used drop with traffic |
| API latency (median) | 18 ms | 309 ms | +16x, the price of a stateless API |

The latency regression is the cost of the move: every read is now a network hop to
Pyronites. The first cut made it worse (723 ms median) because each endpoint made two
or three sequential upstream calls. Collapsing them to one statement per endpoint
(`COUNT(*) OVER ()` for the totals, a single `UNION ALL` for the badge) brought the
median to 309 ms and the per-request CPU to 5.2 ms.

Further levers, not taken yet: a short TTL cache (30 s) for the feed endpoints, and
keeping the Pyronites instance awake, since a cold start there costs 30-50 s and the
first request after an idle period pays for it.


