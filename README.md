# TazaKhabar

![License](https://img.shields.io/badge/license-MIT-FF2D00?style=for-the-badge)
![Next.js](https://img.shields.io/badge/Next.js_14-black?style=for-the-badge&logo=nextdotjs)
![TypeScript](https://img.shields.io/badge/TypeScript-black?style=for-the-badge&logo=typescript)
![Python](https://img.shields.io/badge/Python_3.11-black?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-black?style=for-the-badge&logo=fastapi)
![Pyronites](https://img.shields.io/badge/Pyronites-PyroCore-black?style=for-the-badge)
![Vercel](https://img.shields.io/badge/Vercel-black?style=for-the-badge&logo=vercel)
![Render](https://img.shields.io/badge/Render-black?style=for-the-badge&logo=render)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-black?style=for-the-badge&logo=githubactions)

> **Raw intelligence for the tech job market.**
> Real jobs. Real contact info. No ghost listings. No noise.

TazaKhabar scrapes Hacker News for job listings and market news, scores your
resume against ATS systems, tracks which tech roles are rising, and delivers a
personalised digest — all in one brutalist dark interface.

---

## Architecture

```
                    cron every 2h + manual dispatch
GitHub Actions ────────────────────────────────┐
  scrape HN → summarize → count trends → embed  │
                                                 │  PYRONITES_KEY (write), LLM keys
                                                 ▼
Browser ◀──HTTPS──▶ Vercel (Next.js)      Pyronites (PyroCore)
   │                    │ session cookie        │ tables: profiles, jobs, news,
   │                    ▼                      │ trends, embeddings, rate_limits,
   └─────HTTPS────▶ Render (FastAPI) ──────────┘ scraper_state
                     stateless API only         storage: resume files
```

- **Pyronites** holds everything: accounts, sessions, jobs, news, trends,
  embeddings and uploaded resumes. The browser never talks to it directly, the
  API key never leaves the server.
- **GitHub Actions** does the scraping. The Render service runs no scheduler and
  writes nothing to its own disk.
- **Render** serves a stateless API: it reads and writes Pyronites, calls the
  LLM for the interactive endpoints, and returns.
- **Vercel** serves the frontend and holds no secrets.

### Why it is shaped this way

The previous design kept scraped data in a SQLite file on a free Render
instance and identified users with a client supplied `X-User-ID` header. Both
were fatal: the disk was ephemeral and the disk space was tiny, and any caller
could claim any account. Scraping now runs in CI and the data lives in
Pyronites, so a redeploy cannot lose a row and a forged header cannot open a
door.

---

## How it works

**Accounts and sessions.** There are no passwords. Sign in with Google or GitHub
on the `/auth` terminal: the API is the OAuth client, it redirects the browser
to the provider, handles the callback, links the identity to an `accounts` row
and hands the browser an httpOnly, signed session cookie. Every private
endpoint (`/api/profile`, `/api/resume/analyse`, `/api/qa/chat`, …) verifies
that signature on each request. `src/middleware.ts` sends signed-out visitors
to `/auth`; the API is the real gate.

The app does not use the Pyronites OAuth endpoints: they hard-code their own
callback URL and hand the session to that host with a host-only cookie, which
this API (a different host) cannot read.

**Freshness.** There is no global report swap any more. Each user has a
`feed_last_seen_at` marker; the badge counts jobs and news scraped since that
moment, and "Mark as seen" moves the marker. One user marking the feed seen
never affects another user.

**Trends.** Keyword counts come from a date window over everything scraped in
the current week, compared with the stored previous week. Nothing depends on a
button being pressed, so the week-over-week numbers are stable.

**Personalisation.** The GitHub Actions workflow embeds jobs, news and user
profiles with `all-MiniLM-L6-v2` and stores the vectors in Pyronites. The digest
and the job feed blend score and cosine similarity against the signed-in
user's profile.

---

## Local development

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m src.cli check-pyronites        # verifies the Pyronites connection
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Configuration is read from `backend/.env` and from the repo root `.env`
(root first, backend wins). The root `.env` is git-ignored:

```bash
PYRONITES_URL=https://pyrocore-backend.onrender.com
PYRONITES_KEY=pyro_live_...              # read + write scope
PYRONITES_PROJECT_ID=tazakhabar
PYRONITES_ADMIN_KEY=pyro_live_...        # only for provisioning, never deployed
AUTH_SESSION_SECRET=<long random string>
AUTH_COOKIE_SECURE=false                 # true in production
AUTH_COOKIE_SAMESITE=lax                 # none in production (cross-site cookie)
```

### Frontend

```bash
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

The frontend calls the backend with `credentials: "include"`, so the session
cookie travels with every request. In production the cookie is
`SameSite=None; Secure` because Vercel and Render are different sites.

### Scripts

| Command | Purpose |
|---|---|
| `python backend/scripts/pyro_provision.py` | create the app key, the tables and the smoke test |
| `python backend/scripts/check_auth_flow.py` | sign up / sign in / session checks against Pyronites |
| `python backend/scripts/check_api_flow.py` | auth gate, profile round trip, feed and badge checks |
| `python -m src.cli check-pyronites` | connection and table listing |
| `python -m src.cli ci-run` | run the scrapers and the trend job (what CI runs) |

---

## Deployment

### Render (API)

`render.yaml` declares the service, so the quickest path is **New → Blueprint**
in the Render dashboard, point it at the repository and apply. Render then
creates the service with the right root directory, build and start commands.

To create it by hand instead: **New → Web Service**, connect the repository, then
set:

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Runtime | Python 3.11.9 (from `backend/runtime.txt`) |
| Build command | `pip install -r requirements.render.txt` |
| Start command | `uvicorn src.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |
| Instance type | Free |

Then the environment variables:

| Variable | Value | Required |
|---|---|---|
| `PYRONITES_URL` | `https://pyrocore-backend.onrender.com` | yes |
| `PYRONITES_KEY` | the project key with `read` + `write` scope | yes |
| `PYRONITES_PROJECT_ID` | `tazakhabar` | yes |
| `AUTH_SESSION_SECRET` | any long random string | yes |
| `AUTH_COOKIE_SECURE` | `true` | yes |
| `AUTH_COOKIE_SAMESITE` | `none` (the frontend is on another site) | yes |
| `API_PUBLIC_URL` | the public API URL, the OAuth callback target | yes |
| `FRONTEND_URL` | the frontend URL, where the browser lands after sign in | yes |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google web app credentials | yes |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth app credentials | yes |
| `ALLOWED_ORIGINS` | the exact frontend origin, e.g. `https://tazakhabar3021.vercel.app` | yes |
| `ADMIN_TOKEN` | a random string, guards the write endpoints | yes |
| `GROQ_API_KEY` | your Groq key, for resume scoring and the career bot | recommended |
| `OPENROUTER_API_KEY` | your OpenRouter key, used when Groq fails | recommended |
| `EMBEDDINGS_ENABLED` | `false` (embeddings come from the workflow) | recommended |
| `LOG_LEVEL` | `INFO` | optional |

Delete any leftovers from the old service: `LOG_DIR`, `NOTEBOOK_SYNC_*`,
`KEEPALIVE_*`, `DATABASE_URL`, `SUPABASE_*`.

The service logs to stdout only, so it never writes to the Render disk.

After the first deploy, point Vercel's `NEXT_PUBLIC_API_URL` at the new Render
URL. The two must agree: `ALLOWED_ORIGINS` has to be exactly the origin the
browser calls from, or the browser drops the session cookie and every request
comes back 401.

On the free tier the instance sleeps after 15 minutes idle, so the first
request after a pause takes 30-50 seconds. A scheduled ping (a GitHub Actions
job hitting `/health`) keeps it warm if that matters.

### GitHub Actions (scraping)

Three workflows, all needing the repository secrets `PYRONITES_URL`,
`PYRONITES_KEY`, `PYRONITES_PROJECT_ID` (and `GROQ_API_KEY` /
`OPENROUTER_API_KEY` for the trend job):

| Workflow | Schedule | What it does |
|---|---|---|
| `scrape.yml` | every 2 hours (`0 */2 * * *` UTC) | scrape HN, summarize the new items |
| `trends.yml` | daily (`15 0 * * *` UTC) | recount the weekly keywords, write the market observation |
| `embeddings.yml` | daily (`30 3 * * *` UTC) | backfill the content embeddings |

GitHub cron is best effort: a scheduled run usually starts a few minutes after
the hour, sometimes later. The `concurrency` block stops two runs from
overlapping, and `workflow_dispatch` runs any of them on demand.

Who Is Hiring publishes one thread per month. The scraper records the thread it
processed, so most cycles find that thread and skip it; the other three
scrapers refresh on every cycle.

### Vercel (frontend)

Set `NEXT_PUBLIC_API_URL` to the Render URL.

---

## API reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/auth/providers` | — | which sign-in methods are configured |
| GET | `/api/auth/oauth/{provider}` | — | start the Google or GitHub flow |
| GET | `/api/auth/oauth/{provider}/callback` | — | provider callback, sets the session |
| POST | `/api/auth/logout` | — | drop the session |
| GET | `/api/auth/me` | — | resolve the current session |
| GET | `/api/jobs` | optional | job feed, filters and pagination |
| GET | `/api/news` | — | news feed |
| GET | `/api/trends` | — | keyword trends, observation, predictions |
| GET | `/api/digest` | optional | personalised digest |
| GET | `/api/badge` | optional | items the user has not seen |
| POST | `/api/badge/seen` | required | mark the feed as seen |
| GET/POST | `/api/profile` | required | read and update the profile |
| POST | `/api/resume/analyse` | required | upload a resume, get the ATS score |
| GET | `/api/qa/*` | optional | career bot data |
| POST | `/api/qa/chat` | required | talk to the career bot (rate limited) |
| GET | `/api/scrapers/status` | — | last run of every scraper |
| POST | `/api/scrape/run` | admin token | run the scrapers on demand |
| GET | `/health` | — | health check (pings Pyronites) |

Rate limits live in the `rate_limits` table and are keyed on the verified user
id, so changing a header no longer resets a limit.

---

## Tables

| Table | Holds |
|---|---|
| `accounts` | OAuth identities (provider, provider id, email) |
| `profiles` | user profile, ATS results, `feed_last_seen_at` (id = account id) |
| `jobs` | scraped job listings |
| `news` | scraped news items |
| `trends` | weekly keyword counts |
| `trend_predictions` | W+2 / W+4 predictions |
| `embeddings` | base64 vectors per item and per user profile |
| `rate_limits` | per user daily counters |
| `observations` | LLM market observations |
| `notifications` | queued job match alerts |
| `scraper_state` | scraper bookkeeping (last thread id, last run) |

`users` is a reserved word on Pyronites, which is why the account table is
called `accounts` and the profile table `profiles`.

### Registering the OAuth apps

- **Google**: Cloud Console → APIs & Services → Credentials → Create → Web
  application. Authorized redirect URI:
  `https://tazakhabar-backend.onrender.com/api/auth/oauth/google/callback`.
- **GitHub**: Settings → Developer settings → OAuth Apps → New OAuth App.
  Authorization callback URL:
  `https://tazakhabar-backend.onrender.com/api/auth/oauth/github/callback`.

Put the client id and secret in the Render environment variables.

---

## Known limitations

- Free-tier hosts sleep when idle, so the first request after a pause is slow.
- Embeddings only exist for items that were scraped after the embeddings
  workflow started; older rows fall back to score order.
- Who Is Hiring publishes one thread per month. The scraper skips a thread it
  has already processed, so most runs collect nothing from it.
- The market observation needs a working LLM key; without one the block stays
  hidden instead of showing a placeholder.

## License

MIT
