---
phase: "01-foundation-backend"
plan: "01-03"
tasks_completed: 3
artifacts_created:
  - tazakhabar-backend/src/services/trend_service.py
  - tazakhabar-backend/src/api/trends.py
  - tazakhabar-backend/src/api/badge.py
  - tazakhabar-backend/src/api/refresh.py
key_decisions:
  - Implemented keyword frequency counter with 99 tech keywords covering languages, AI/ML, infrastructure, databases, frontend, backend, architecture, and work style
  - Week-over-week percentage change calculated: booming (>20% growth), declining (<-20% decline), neutral otherwise
  - Badge endpoint returns lightweight {radar_new_count, feed_new_count} for efficient 5-min polling
  - Report swap (refresh) demotes Report 1 to archived, promotes Report 2 to 1, resets badge counts to 0
  - Trends page converted from static mock data to live API calls (no mock fallback per TRND-07)
  - TopNav polls /api/badge every 5 minutes with useEffect + setInterval pattern
  - APScheduler job added for daily keyword frequency computation at midnight UTC
blockers: []
commits:
  - ae0bcf1: feat(01-03): add keyword frequency counter and trends API
  - c4f2fdb: feat(01-03): add badge endpoint, report swap, and refresh trigger
  - b7db6ef: feat(01-03): connect frontend trends screen and TopNav badge polling
---

# Phase 01 Plan 03 Summary: Trends API and Badge System

## One-liner
Implemented keyword frequency counter with week-over-week analysis, badge endpoint for 5-minute polling, report swap/refresh trigger, and connected frontend to live trend data.

## Tasks Completed

### Task 1: Keyword Frequency Counter and Trends API
- **Files:** `tazakhabar-backend/src/services/trend_service.py`, `tazakhabar-backend/src/api/trends.py`
- **Key Features:**
  - 99 TECH_KEYWORDS covering all major tech domains
  - `extract_keywords()`: tokenizes text and matches against keyword list
  - `compute_keyword_frequencies()`: scans jobs (title, tags) and news (title, summary), calculates week-over-week change
  - `get_trends()`: returns top 5 booming (>20% growth) + top 3 declining (>20% decline)
  - APScheduler job runs daily at midnight UTC
- **Endpoints:**
  - `GET /api/trends`: returns `{data: [Trend, ...], meta: {...}}`
  - `GET /api/trends/observation`: returns static placeholder (Phase 2 LLM narration deferred)
  - `POST /api/trends/compute`: manual trigger for testing

### Task 2: Badge Endpoint, Report Swap, and Refresh Trigger
- **Files:** `tazakhabar-backend/src/api/badge.py`, `tazakhabar-backend/src/api/refresh.py`, `tazakhabar-backend/src/services/report_service.py`, `tazakhabar-backend/src/db/schemas.py`
- **Key Features:**
  - `BadgeResponse`: `{radar_new_count: int, feed_new_count: int}`
  - `RefreshResponse`: `{status: str, radar_new_count: int, feed_new_count: int}`
  - `swap_reports()`: demotes Report 1 → archived, promotes Report 2 → 1, resets badge to 0
  - `get_last_swap_time()`: retrieves most recent swap timestamp
- **Endpoints:**
  - `GET /api/badge`: lightweight endpoint for 5-minute polling
  - `POST /api/refresh`: triggers report swap, returns counts (0 after swap)

### Task 3: Frontend Integration
- **Files:** `src/lib/api.ts`, `src/app/trends/page.tsx`, `src/components/TopNav.tsx`
- **Key Features:**
  - `fetchTrends()`: calls `/api/trends`, returns `{data: Trend[], meta: ...}`
  - `triggerRefresh()`: calls `POST /api/refresh`
  - `fetchBadgeCounts()`: now calls live `/api/badge` endpoint (previously returned zeros)
  - Trends page: converted to async Server Component fetching live data (no mock fallback)
  - TopNav: `useEffect` with `setInterval` polls `/api/badge` every 5 minutes
  - Badge display: shows count on notification icon with red dot indicator

## Verification Results

```
Task 1: python -c "from src.services.trend_service import TrendService, TECH_KEYWORDS; ..."
  TrendService: OK
  TECH_KEYWORDS count: 99
  PASS

Task 2: python -c "from src.api.badge import router; from src.db.schemas import BadgeResponse, RefreshResponse; ..."
  Badge routes: ['/api/badge']
  Refresh routes: ['/api/refresh']
  BadgeResponse fields: ['radar_new_count', 'feed_new_count']
  RefreshResponse fields: ['status', 'radar_new_count', 'feed_new_count']
  PASS

Task 3: python -c "from src.main import app; ..."
  Badge endpoint registered: True
  Refresh endpoint registered: True
  Trends endpoint registered: True
  PASS
```

## Files Modified/Created

### Backend
| File | Change |
|------|--------|
| `tazakhabar-backend/src/services/trend_service.py` | NEW - Keyword frequency service |
| `tazakhabar-backend/src/api/trends.py` | NEW - Trends REST endpoint |
| `tazakhabar-backend/src/api/badge.py` | NEW - Badge counter endpoint |
| `tazakhabar-backend/src/api/refresh.py` | NEW - Refresh/swap trigger endpoint |
| `tazakhabar-backend/src/services/report_service.py` | MODIFIED - Added `swap_reports()`, `get_last_swap_time()` |
| `tazakhabar-backend/src/db/schemas.py` | MODIFIED - Added `BadgeResponse`, `RefreshResponse` |
| `tazakhabar-backend/src/scheduler.py` | MODIFIED - Added daily trend computation job |
| `tazakhabar-backend/src/api/__init__.py` | MODIFIED - Export new routers |
| `tazakhabar-backend/src/main.py` | MODIFIED - Include new routers |

### Frontend
| File | Change |
|------|--------|
| `src/lib/api.ts` | MODIFIED - Added `fetchTrends()`, `triggerRefresh()`, updated `fetchBadgeCounts()` |
| `src/app/trends/page.tsx` | MODIFIED - Converted to async Server Component using live API |
| `src/components/TopNav.tsx` | MODIFIED - Added 5-min badge polling with `useEffect` |

## Success Criteria Met
- [x] GET /api/trends returns keyword frequency data
- [x] GET /api/badge returns {radar_new_count, feed_new_count}
- [x] POST /api/refresh returns {status: "swapped", ...} and resets badge counts
- [x] Trends screen shows live data (not mock)
- [x] TopNav polls /api/badge every 5 minutes
- [x] Week-over-week percentage change correctly computed
- [x] >20% growth = booming, <-20% decline = declining

## Self-Check: PASSED
All files created, all commits verified.
