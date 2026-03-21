# TazaKhabar

![Status](https://img.shields.io/badge/status-Phase%202%20Complete-FF2D00?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.1.0-black?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-FF2D00?style=for-the-badge)
![React Doctor](https://img.shields.io/badge/React%20Doctor-96%2F100-black?style=for-the-badge&logo=react)
![Next.js](https://img.shields.io/badge/Next.js_14-black?style=for-the-badge&logo=nextdotjs)
![TypeScript](https://img.shields.io/badge/TypeScript-black?style=for-the-badge&logo=typescript)
![Python](https://img.shields.io/badge/Python_3.11-black?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-black?style=for-the-badge&logo=fastapi)
![SQLite](https://img.shields.io/badge/SQLite-black?style=for-the-badge&logo=sqlite)
![Supabase](https://img.shields.io/badge/Supabase-black?style=for-the-badge&logo=supabase)
![Stripe](https://img.shields.io/badge/Stripe-black?style=for-the-badge&logo=stripe)
![Gemini](https://img.shields.io/badge/Gemini_1.5_Flash-black?style=for-the-badge&logo=google)
![Railway](https://img.shields.io/badge/Railway-black?style=for-the-badge&logo=railway)
![Vercel](https://img.shields.io/badge/Vercel-black?style=for-the-badge&logo=vercel)

> **Raw intelligence for the tech job market.**
> Real jobs. Real contact info. No ghost listings. No noise.

TazaKhabar scrapes Hacker News in real time, extracts verified job contact information, scores your resume against ATS systems, predicts which tech roles are booming or dying, and delivers a personalised daily digest — all in one brutalist dark interface built for serious tech job seekers.

---

## What It Does

- **Honest Job Hunt** — scrapes HN Who Is Hiring every 2 hours, extracts direct emails and apply links, flags ghost jobs with no contact info
- **AI Impact Trends** — tracks keyword frequency week over week across all HN data and predicts which roles are growing or declining
- **Personalised Digest** — matches scraped news to your profile using semantic RAG search and delivers only what matters to you
- **Resume Intelligence** — parses your PDF resume, scores ATS compatibility, and suggests keywords based on live market demand

---

## Full System Workflow

```mermaid
flowchart TD
    A([User Opens TazaKhabar]) --> B[Splash Screen]
    B --> C{Auth Method}
    C -->|Google| D[Supabase OAuth]
    C -->|GitHub| D
    C -->|Email| E[Supabase Email Auth]
    D --> F[Onboarding Wizard]
    E --> F
    F --> G[Role Selection]
    G --> H[Experience Level]
    H --> I[Resume Upload]
    I --> J[Dashboard]
    J --> K[Feed Screen]
    J --> L[Radar Screen]
    J --> M[Trends Screen]
    J --> N[Profile Screen]

    style A fill:#FF2D00,color:#000
    style J fill:#FF2D00,color:#000
```

---

## Stage 1 — Backend Foundation

> Steps 1 to 16 — FastAPI setup, database, scraper, data pipeline

```mermaid
flowchart TD
    A([APScheduler Triggers]) --> B[Run All 4 Scrapers]

    B --> C[Who Is Hiring Thread]
    B --> D[Ask HN Stories]
    B --> E[Show HN Stories]
    B --> F[Top Stories]

    C --> G[Raw HN API Response]
    D --> G
    E --> G
    F --> G

    G --> H[Contact Extractor]
    H --> H1{Email Found?}
    H1 -->|Yes| I1[Store email_contact]
    H1 -->|No| I2[email_contact = null]

    H --> H2{Apply Link Found?}
    H2 -->|Yes| J1[Store apply_link]
    H2 -->|No| J2[apply_link = null]

    I2 --> K{Both Null?}
    J2 --> K
    K -->|Yes| L[Flag as Ghost Job]
    K -->|No| M[Clean Job Record]
    L --> M

    M --> N[Deduplication Check]
    N --> N1{Already Exists?}
    N1 -->|Yes — Active Deadline| O1[Skip Insert]
    N1 -->|Yes — Deadline Passed| O2[Insert as New]
    N1 -->|No| O2

    O2 --> P[Tag as Report 2]
    P --> Q[Compare vs Report 1]
    Q --> R[Generate Changes Summary]
    R --> S[Store New Item Count]
    S --> T[Badge Counter Updated]
    T --> U([Frontend Shows Badge])

    style A fill:#FF2D00,color:#000
    style U fill:#FF2D00,color:#000
    style L fill:#7a1a1a,color:#fff
    style O1 fill:#1a1a1a,color:#888
```

---

## Stage 2 — Report Cycle Architecture

> The freshness system — how data stays current without disrupting the user

```mermaid
sequenceDiagram
    participant S as Scraper
    participant DB as SQLite Database
    participant FE as Frontend
    participant U as User

    Note over S,DB: Every 1-2 hours
    S->>DB: Collect new data → tag as Report 2
    DB->>DB: Compare Report 2 vs Report 1
    DB->>DB: Generate diff — new jobs, new news
    DB->>FE: Return badge count (new items found)
    FE->>U: Show red badge on nav tabs

    Note over U,FE: User sees old data until they refresh
    U->>FE: Taps refresh banner
    FE->>DB: Request Report 2 data
    DB->>DB: Delete Report 1
    DB->>DB: Rename Report 2 → Report 1
    DB->>FE: Serve fresh data
    FE->>U: Feed updates, badge clears

    Note over DB: Container is now empty and ready for next cycle
```

---

## Stage 3 — LLM Integration

> Steps 17 to 25 — Gemini, summarization, trend narration, headlines

```mermaid
flowchart TD
    A([New Scraped Item]) --> B{Item Type?}

    B -->|News / Story| C[Summarization Pipeline]
    B -->|Trend Data| D[Trend Narration Pipeline]
    B -->|Headline Unclear| E[Headline Rewriter]

    C --> C1[Check Rate Limit]
    C1 --> C2{Limit OK?}
    C2 -->|Yes| C3[Send to Gemini 1.5 Flash]
    C2 -->|No| C4[Queue for Next Window]
    C3 --> C5[2-3 Sentence Summary\nFocused on Job Market Impact]
    C5 --> C6[Store Summary on News Record]

    D --> D1[Collect Top 5 Booming Keywords]
    D1 --> D2[Collect Top 3 Declining Keywords]
    D2 --> D3[Send to Gemini with Trend Prompt]
    D3 --> D4[One Paragraph Observation]
    D4 --> D5[Store in Trends Table]
    D5 --> D6[Serve to Observation Block on Frontend]

    E --> E1[Send Original Title to Gemini]
    E1 --> E2[Editorial Style Rewrite]
    E2 --> E3[Store as Display Title]

    C6 --> F([Frontend Digest Screen])
    D6 --> G([Frontend Trends Screen])
    E3 --> H([Frontend Feed Screen])

    style A fill:#FF2D00,color:#000
    style F fill:#FF2D00,color:#000
    style G fill:#FF2D00,color:#000
    style H fill:#FF2D00,color:#000
    style C4 fill:#1a1a1a,color:#888
```

---

## Stage 4 — PDF Resume Processing

> Steps 26 to 32 — Upload, parse, score, suggest, rate limit

```mermaid
flowchart TD
    A([User Uploads Resume PDF]) --> B[FastAPI Resume Endpoint]
    B --> C{File Valid?}
    C -->|Invalid type or size| D[Return Error to Frontend]
    C -->|Valid| E[PyMuPDF Text Extraction]

    E --> F{Text Found?}
    F -->|No — Image PDF| G[Return Cannot Parse Error]
    F -->|Yes| H[Clean and Chunk Text]

    H --> I[Split into Sections\nExperience · Skills · Education]
    I --> J[Store Cleaned Text on User Record]

    J --> K[Check Daily Rate Limit]
    K --> K1{Limit Reached?}
    K1 -->|Yes| L[Return Seconds Until Reset]
    L --> L1[Frontend Shows Countdown Timer]
    K1 -->|No| M[Increment Request Counter]

    M --> N1[ATS Scoring Call → Gemini]
    M --> N2[Keyword Extraction Call → Gemini]

    N1 --> O1[Score 0-100\nCritical Fixes List\nJSON Response]
    N2 --> O2[Extracted Skills List]

    O2 --> P[Compare vs Trending Keywords\nFrom Trends Table]
    P --> Q[Generate Suggested Additions List]

    O1 --> R[Store ATS Score + Fixes]
    Q --> R

    R --> S([Profile Screen — Resume Intelligence Section])

    style A fill:#FF2D00,color:#000
    style S fill:#FF2D00,color:#000
    style D fill:#7a1a1a,color:#fff
    style G fill:#7a1a1a,color:#fff
    style L1 fill:#1a1a1a,color:#888
```

---

## Stage 5 — Personalization and RAG Pipeline

> Steps 33 to 42 — User matching, embeddings, semantic search, digest generation

```mermaid
flowchart TD
    A([User Completes Onboarding]) --> B[Store Profile Locally]
    B --> C[Roles + Experience + Preferences]

    C --> D[Generate Profile Embedding\nvia sentence-transformers]
    D --> E[Store in Embeddings Table]

    F([Scraper Adds New Item]) --> G[Generate Item Embedding]
    G --> H[Store in Embeddings Table]

    E --> I[RAG Search Engine]
    H --> I

    I --> J[Compute Cosine Similarity\nProfile vs All Items]
    J --> K[Rank by Similarity Score]
    K --> L[Normalise to Match Percentage]

    L --> M{Content Type?}
    M -->|Jobs| N[Job Feed — Sorted by Relevance]
    M -->|News| O[Personalised Digest — Top 5 Matches]
    M -->|Both| P[Profile Jobs You Qualify For Count]

    N --> Q([Radar Screen])
    O --> R([Feed Screen])
    P --> S([Profile Screen])

    T([New Scrape Cycle Completes]) --> U[Check Each User Profile]
    U --> V[Match New Jobs vs User Roles]
    V --> W{Match Score High Enough?}
    W -->|Yes| X[Queue Email Notification]
    W -->|No| Y[Skip]
    X --> Z{Supabase Connected?}
    Z -->|Yes| AA[Send Email to User]
    Z -->|No| AB[Log to Console — Dormant]

    style A fill:#FF2D00,color:#000
    style Q fill:#FF2D00,color:#000
    style R fill:#FF2D00,color:#000
    style S fill:#FF2D00,color:#000
    style AA fill:#1a7a1a,color:#fff
    style AB fill:#1a1a1a,color:#888
```

---

## Stage 6 — ML Trend Model

> Steps 21 to 25 — Keyword counting, week over week analysis, prediction model

```mermaid
flowchart TD
    A([All Scraped Data in DB]) --> B[Keyword Frequency Counter]
    B --> C[Scan Job Tags\nNews Titles\nStory Summaries]
    C --> D[Count Per Keyword Per Week]
    D --> E[Store in Trends Table\nweek_start · week_end · count]

    E --> F[Week over Week Calculator]
    F --> G{Percentage Change?}
    G -->|Growth over 20%| H[Mark as BOOMING]
    G -->|Decline over 20%| I[Mark as DECLINING]
    G -->|Stable| J[Mark as NEUTRAL]

    H --> K[Top 5 Booming → Red Bars on Trends Screen]
    I --> L[Top 3 Declining → Grey Bars on Trends Screen]

    E --> M{8 Weeks of Data Accumulated?}
    M -->|No| N[Use Raw Frequency Data Only]
    M -->|Yes| O[Train Scikit-learn Model]

    O --> P[LinearRegression on Weekly Counts]
    P --> Q[Predict Next 4 Weeks per Keyword]
    Q --> R[Format as Prediction Output\nKeyword · Current · W+2 · W+4 · Confidence]
    R --> S[Serve from /api/trends/predictions]

    K --> T([Trends Screen Bar Charts])
    L --> T
    S --> T

    style A fill:#FF2D00,color:#000
    style T fill:#FF2D00,color:#000
    style N fill:#1a1a1a,color:#888
```

---

## Stage 7 — Supabase Integration

> Steps 52 to 59 — Cloud migration, auth, storage, notifications

```mermaid
flowchart TD
    A([Supabase Project Created]) --> B[Run Schema Migration\nSQLite → PostgreSQL + pgvector]
    B --> C[Export Local SQLite Data]
    C --> D[Import into Supabase Tables]
    D --> E[Switch FastAPI DB Connection]

    E --> F[Configure Auth Providers]
    F --> F1[Google OAuth]
    F --> F2[GitHub OAuth]
    F --> F3[Email + Password]

    F1 --> G[Next.js Auth Middleware]
    F2 --> G
    F3 --> G
    G --> H[Protected Routes\nFeed · Radar · Trends · Profile]

    E --> I[Create Supabase Storage Bucket]
    I --> J[Move Resume Upload to Bucket]
    J --> K[Store Signed URL on User Record]

    E --> L[Move rate_limits Table to Supabase]
    L --> M[Per Authenticated User\nNot Per IP]

    E --> N[Activate Email Notifications]
    N --> O[Uncomment Send Call in notifications.py]
    O --> P[Configure Supabase Email Templates\nTazaKhabar Branding]
    P --> Q[Job Match Alert Toggle Now Live]

    E --> R[Remove SQLite Dependency]
    R --> S([Fully Cloud Native])

    style A fill:#FF2D00,color:#000
    style S fill:#FF2D00,color:#000
```

---

## Stage 8 — Monetization

> Steps 60 to 62 — Stripe, Pro tier, payment flow

```mermaid
flowchart TD
    A([Stripe Account Setup]) --> B[Define Products]
    B --> B1[Free Tier — $0\nBasic feed · 20 LLM requests/day\nContact info · Basic ATS score]
    B --> B2[Pro Tier — Monthly\nUnlimited LLM · Full predictions\nPriority matching · Job alerts]

    B1 --> C[Feature Gate Logic — Server Side]
    B2 --> C

    C --> D{User Hits Pro Feature?}
    D -->|Free User| E[Return 403 with Upgrade Prompt]
    D -->|Pro User| F[Serve Full Response]

    E --> G[Frontend Shows Upgrade Screen]
    G --> H[Trigger Stripe Checkout]
    H --> I[Payment Completed]
    I --> J[Stripe Webhook → FastAPI]

    J --> K{Event Type?}
    K -->|checkout.session.completed| L[Set subscription = pro on User]
    K -->|subscription.deleted| M[Set subscription = free on User]
    K -->|invoice.payment_failed| N[Notify User via Email]

    L --> O([Pro Features Unlocked Immediately])
    M --> P([Downgraded to Free Tier])

    style A fill:#FF2D00,color:#000
    style O fill:#1a7a1a,color:#fff
    style P fill:#7a1a1a,color:#fff
```

---

## Deployment Architecture

```mermaid
flowchart LR
    U([User]) -->|HTTPS| V[Vercel\nNext.js 14 Frontend]
    V -->|API Calls| R[Railway\nFastAPI Backend]
    R -->|Read Write| S[(Supabase\nPostgreSQL + pgvector)]
    R -->|File Storage| ST[Supabase\nStorage Bucket]
    R -->|Auth Verify| SA[Supabase\nAuth]
    R -->|LLM Calls| G[Google Gemini\n1.5 Flash]
    R -->|Payment Events| ST2[Stripe\nWebhooks]
    R -->|Scheduled Scraping| HN[Hacker News\nFirebase API]

    style U fill:#FF2D00,color:#000
    style V fill:#0E0E0E,color:#F0EDE6
    style R fill:#0E0E0E,color:#F0EDE6
    style S fill:#0E0E0E,color:#F0EDE6
    style G fill:#0E0E0E,color:#F0EDE6
```

---

## Project Structure

```
tazakhabar/
├── src/                         # Next.js 14 Frontend (Phase 1 + 2)
│   ├── app/
│   │   ├── page.tsx             # Splash + Login
│   │   ├── jobs/                # Job Radar screen (ghost + deadline badges)
│   │   ├── digest/              # News Feed screen (match % badges)
│   │   ├── trends/              # Trends screen (observation block)
│   │   └── profile/             # Profile screen (ATS, countdown timer)
│   ├── components/
│   └── lib/
│       ├── api.ts               # API client (Phase 1 + 2: live)
│       └── mockData.ts          # Deprecated
│
└── tazakhabar-backend/         # FastAPI Backend (Phase 1 + 2)
    ├── src/
    │   ├── main.py              # FastAPI app + lifespan (embedding model loaded)
    │   ├── config.py            # Pydantic settings
    │   ├── db/
    │   │   ├── database.py      # Async SQLite session
    │   │   ├── models.py        # SQLAlchemy 2.0 models (9 tables + Observation)
    │   │   └── schemas.py       # Pydantic models (Phase 1 + 2)
    │   ├── api/
    │   │   ├── jobs.py          # GET /api/jobs
    │   │   ├── news.py          # GET /api/news
    │   │   ├── trends.py        # GET /api/trends
    │   │   ├── badge.py         # GET /api/badge
    │   │   ├── refresh.py       # POST /api/refresh
    │   │   ├── observation.py   # GET /api/observation (Phase 2)
    │   │   ├── resume.py       # POST /api/resume/analyse (Phase 2)
    │   │   ├── profile.py       # GET + POST /api/profile (Phase 2)
    │   │   └── digest.py        # GET /api/digest (Phase 2)
    │   ├── scrapers/
    │   │   ├── client.py        # HN Firebase + Algolia client
    │   │   ├── base_scraper.py  # Shared + summarization + embedding scheduling
    │   │   ├── who_is_hiring.py # Who Is Hiring (Algolia, 2hr)
    │   │   ├── ask_hn.py        # Ask HN (Firebase, 4hr)
    │   │   ├── show_hn.py       # Show HN (Firebase, 6hr)
    │   │   └── top_stories.py   # Top Stories (Firebase, 2hr)
    │   ├── services/
    │   │   ├── report_service.py # Report 1/2 cycle + badge counts
    │   │   ├── trend_service.py  # Keyword frequency + week-over-week
    │   │   ├── llm_service.py   # Gemini client + retry + rate limiting (Phase 2)
    │   │   ├── resume_service.py # PDF extraction + ATS scoring (Phase 2)
    │   │   ├── embedding_service.py # sentence-transformers + cosine similarity (Phase 2)
    │   │   └── digest_service.py # Blended digest computation (Phase 2)
    │   ├── scheduler.py          # APScheduler (observation job replaces trends job)
    │   ├── notifications.py      # NotificationService (dormant Supabase)
    │   └── middleware/
    │       └── logging.py        # RequestLoggingMiddleware
    ├── tazakhabar.db             # SQLite database
    ├── Dockerfile                # Railway deployment
    ├── railway.json              # Railway config
    ├── .env.example              # Environment template
    └── requirements.txt         # Python dependencies (Phase 1 + 2)
```

---

## Getting Started

### 1. Start the Backend
```bash
cd tazakhabar-backend
pip install -r requirements.txt
cp .env.example .env             # Add your GEMINI_API_KEY (optional for Phase 1)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

You should see:
```
>>> [SETUP] Registering API routers...
    + /api/jobs registered
    + /api/news registered
    + /api/trends registered
    + /api/badge registered
    + /api/refresh registered
    + /api/observation registered
    + /api/resume registered
    + /api/profile registered
    + /api/digest registered
>>> [SCHEDULER] Started with 5 jobs registered
>>> [EMBEDDING] Loading sentence-transformers model...
>>> [OK] Embedding model loaded: all-MiniLM-L6-v2 (384 dims)
```

### 2. Test All Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Badge counter
curl http://localhost:8000/api/badge

# Job feed
curl http://localhost:8000/api/jobs

# News feed
curl http://localhost:8000/api/news

# Trends
curl http://localhost:8000/api/trends

# Market observation (Phase 2)
curl http://localhost:8000/api/observation

# Personalized digest (Phase 2)
curl http://localhost:8000/api/digest

# Refresh (swap reports)
curl -X POST http://localhost:8000/api/refresh
```

### 3. Start the Frontend
```bash
npm install
npm run dev
```

Visit `http://localhost:3000`

- **/jobs** — Job Radar (live HN jobs)
- **/digest** — News Feed (Ask HN, Show HN, Top Stories)
- **/trends** — Trends (keyword frequency bars)

---

## Verification Checklist

After starting the backend, verify everything is working:

### Start Backend
```bash
cd tazakhabar-backend
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```
Expected output shows all 5 routers registered and scheduler started.

### Test All API Endpoints
```bash
# Health check
curl http://localhost:8000/health
# -> {"status":"healthy","timestamp":"..."}

# Badge counter
curl http://localhost:8000/api/badge
# -> {"radar_new_count":0,"feed_new_count":0}

# Jobs feed (empty before scrapers run)
curl "http://localhost:8000/api/jobs"
curl "http://localhost:8000/api/jobs?roles=Frontend&remote=true"

# News feed (empty before scrapers run)
curl "http://localhost:8000/api/news"
curl "http://localhost:8000/api/news?type=ask_hn"

# Trends
curl http://localhost:8000/api/trends

# Refresh / swap reports
curl -X POST http://localhost:8000/api/refresh
# -> {"status":"swapped","radar_new_count":0,"feed_new_count":0}
```

### Run HN Scrapers Manually
```bash
cd tazakhabar-backend
python -c "
import asyncio
from src.scrapers.top_stories import TopStoriesScraper
from src.scrapers.ask_hn import AskHNScraper
from src.scrapers.show_hn import ShowHNScraper

async def run():
    r1 = await TopStoriesScraper().run()
    r2 = await AskHNScraper().run()
    r3 = await ShowHNScraper().run()
    print(f'Top Stories: {r1}')
    print(f'Ask HN: {r2}')
    print(f'Show HN: {r3}')

asyncio.run(run())
"
# Expected: >>> [TOP-STORIES] SUCCESS: N NEW items saved!
```

### Verify Data End-to-End
```bash
# 1. Run scrapers (above)
# 2. Swap so scraped data becomes visible
curl -X POST http://localhost:8000/api/refresh

# 3. News API should return data
curl "http://localhost:8000/api/news"
# -> {"data":[...],"meta":{"total":194,...}}

# 4. Badge shows non-zero
curl http://localhost:8000/api/badge
# -> {"radar_new_count":0,"feed_new_count":194}
```

### Common Errors & Fixes
| Error | Fix |
|---|---|
| Port 8000 in use | `netstat -ano \| findstr :8000` then kill PID |
| Module not found | Make sure you're in `tazakhabar-backend/` |
| 0 new items saved | Deduplication working — items already in DB |
| Badge validation error | Pull latest commit (`8367ce3`+) |
| Gemini 429 / rate limit | Wait until midnight UTC or set `GEMINI_API_KEY` with higher quota |
| sentence-transformers slow first load | Normal — model downloads on first run (~22MB) |
| Summarization not showing | Run scrapers to create news items, then summarization fires automatically |

### Database Contents
```bash
cd tazakhabar-backend
python -c "
from src.db.database import async_session
from sqlalchemy import select, func
from src.db.models import Job, News, Report, Observation, Embedding
import asyncio

async def check():
    async with async_session() as s:
        j = (await s.execute(select(func.count(Job.id)))).scalar()
        n = (await s.execute(select(func.count(News.id)))).scalar()
        r = (await s.execute(select(func.count(Report.id)))).scalar()
        o = (await s.execute(select(func.count(Observation.id)))).scalar()
        e = (await s.execute(select(func.count(Embedding.id)))).scalar()
        print(f'Jobs: {j} | News: {n} | Reports: {r} | Observations: {o} | Embeddings: {e}')

asyncio.run(check())
"
```

---

## Environment Variables

```env
# Backend .env
GEMINI_API_KEY=your_key_here                    # REQUIRED for Phase 2 (summarization, ATS, observation)
DATABASE_URL=sqlite+aiosqlite:///./tazakhabar.db
ALLOWED_ORIGINS=http://localhost:3000,https://tazakhabar.vercel.app,https://*.vercel.app
LOG_LEVEL=INFO
# SUPABASE_URL=add_later                       # Phase 3
# SUPABASE_KEY=add_later                       # Phase 3
# STRIPE_SECRET_KEY=add_later                  # Phase 3
# STRIPE_WEBHOOK_SECRET=add_later              # Phase 3

# Frontend .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_SUPABASE_URL=add_later           # Phase 3
# NEXT_PUBLIC_SUPABASE_ANON_KEY=add_later       # Phase 3
# NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=add_later  # Phase 3
```

---

## Build Progress

| Stage | Status | Notes |
|---|---|---|
| FastAPI setup and folder structure | DONE | 31 backend files created |
| SQLite schema (8 tables) | DONE | jobs, news, trends, users, rate_limits, reports, embeddings, notifications |
| HN Scrapers — all 4 sources | DONE | Who Is Hiring, Ask HN, Show HN, Top Stories |
| Report 1 and Report 2 architecture | DONE | `/api/refresh` swaps reports |
| Keyword frequency + week-over-week | DONE | 99 tech keywords tracked |
| Notification system | DONE | Full code, Supabase dormant |
| Frontend connected to real data | DONE | All 3 screens use live API |
| Badge counter + 5-min polling | DONE | `/api/badge` + TopNav polling |
| Railway deployment ready | DONE | Dockerfile + railway.json |
| CORS, logging, health check | DONE | All endpoints verified |
| Gemini LLM integration | DONE | `gemini-2.0-flash` auto-selected, Tenacity retry, rate limiting |
| News summarization | DONE | Top 20 by score, 2-3 sentences, fire-and-forget |
| Market observation generation | DONE | Daily at midnight, booming/declining keywords, `/api/observation` |
| PDF resume parsing | DONE | PyMuPDF, PDF + TXT, 5MB limit |
| ATS scoring | DONE | 0-100 score, top 3 critical fixes, missing keywords |
| Suggested additions | DONE | Gemini generates from resume + roles + trending keywords |
| RAG personalization | DONE | sentence-transformers all-MiniLM-L6-v2, cosine similarity |
| Personalized digest | DONE | Blended scoring, 5 items/page, `/api/digest` |
| Frontend — all pages wired | DONE | Profile, digest, trends, jobs connected to Phase 2 APIs |
| Ghost job + deadline badges | DONE | Job cards show "LIKELY GHOST" and "DEADLINE UNKNOWN" |
| ML trend prediction model | TODO | Phase 3 |
| Supabase integration | TODO | Phase 3 |
| Stripe monetization | TODO | Phase 3 |

---

## License

MIT — built with raw intelligence.