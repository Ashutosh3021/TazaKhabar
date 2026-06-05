"""
Scraper status API endpoint.

GET /api/scrapers/status

Returns real-time progress information for all known scrapers.

Data sources (in priority order per scraper):
  1. Latest Report row WHERE scraper_name = <id>  (new tagged runs)
  2. MAX(scraped_at) + COUNT from news/jobs tables (works for all historic data)
  3. APScheduler job metadata for next_run

Response shape
--------------
{
  "scrapers": [
    {
      "scraper_id":          str,   # scheduler job ID
      "name":                str,   # human-readable label
      "is_active":           bool,  # True while a "running" Report exists
      "progress_percentage": int,   # 0-100
      "items_scraped":       int,   # total rows for this scraper in DB
      "items_remaining":     int,   # max(0, expected_total - items_scraped)
      "status":              str,   # "running"|"completed"|"failed"|"never_run"
      "last_updated":        str,   # ISO-8601 UTC of most recent scrape
      "next_run":            str | null
    },
    ...
  ]
}
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Job, News, Report
from src.scheduler import scheduler

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])

# ---------------------------------------------------------------------------
# Known batch-size ceilings — used for progress_percentage / items_remaining.
# who_is_hiring is unbounded; 500 is a conservative upper bound per thread.
# ---------------------------------------------------------------------------
_EXPECTED_TOTALS: dict[str, int] = {
    "who_is_hiring": 500,
    "top_stories":   30,
    "ask_hn":        200,
    "show_hn":       200,
}

_DISPLAY_NAMES: dict[str, str] = {
    "who_is_hiring": "Who Is Hiring",
    "top_stories":   "Top Stories",
    "ask_hn":        "Ask HN",
    "show_hn":       "Show HN",
}

# news.type values that map to each scraper
_NEWS_TYPE: dict[str, str] = {
    "top_stories": "top_story",
    "ask_hn":      "ask_hn",
    "show_hn":     "show_hn",
}


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class ScraperStatusItem(BaseModel):
    scraper_id: str
    name: str
    is_active: bool
    progress_percentage: int
    items_scraped: int
    items_remaining: int
    status: str
    last_updated: str | None
    next_run: str | None


class ScraperStatusResponse(BaseModel):
    scrapers: list[ScraperStatusItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _compute_progress(items_scraped: int, expected: int) -> tuple[int, int]:
    if expected <= 0:
        return (100 if items_scraped > 0 else 0), 0
    pct = min(100, round(items_scraped * 100 / expected))
    remaining = max(0, expected - items_scraped)
    return pct, remaining


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=ScraperStatusResponse,
    summary="Scraper progress status",
    description=(
        "Returns the real-time status of every HN scraper. "
        "Uses tagged Report rows for new runs and falls back to "
        "scraped_at timestamps in news/jobs tables for historic data."
    ),
)
async def get_scraper_status(
    db: AsyncSession = Depends(get_db),
) -> ScraperStatusResponse:
    """
    Build per-scraper status from three sources:
      - Report rows tagged with scraper_name (new runs after migration)
      - MAX(scraped_at) / COUNT from news & jobs tables (all historic data)
      - APScheduler job list for next_run_time and is_running state
    """
    try:
        # ------------------------------------------------------------------ #
        # 1. Tagged Reports: latest row per scraper_name (new runs only)      #
        # ------------------------------------------------------------------ #
        tagged_subq = (
            select(
                Report.scraper_name,
                func.max(Report.run_at).label("latest_run_at"),
            )
            .where(Report.scraper_name.isnot(None))
            .group_by(Report.scraper_name)
            .subquery()
        )
        tagged_stmt = select(Report).join(
            tagged_subq,
            (Report.scraper_name == tagged_subq.c.scraper_name)
            & (Report.run_at == tagged_subq.c.latest_run_at),
        )
        tagged_result = await db.execute(tagged_stmt)
        tagged_reports: dict[str, Report] = {
            r.scraper_name: r
            for r in tagged_result.scalars().all()
            if r.scraper_name
        }

        # ------------------------------------------------------------------ #
        # 2. Active (running) report — any scraper currently mid-run          #
        # ------------------------------------------------------------------ #
        active_stmt = (
            select(Report.scraper_name)
            .where(
                Report.status == "running",
                Report.scraper_name.isnot(None),
            )
        )
        active_result = await db.execute(active_stmt)
        active_scrapers: set[str] = {
            row[0] for row in active_result.all() if row[0]
        }

        # ------------------------------------------------------------------ #
        # 3. Fallback: stats from news / jobs tables (always populated)       #
        # ------------------------------------------------------------------ #
        # news table: (type, count, max scraped_at)
        news_stats_stmt = select(
            News.type,
            func.count(News.id).label("cnt"),
            func.max(News.scraped_at).label("last_scraped"),
        ).group_by(News.type)
        news_stats_result = await db.execute(news_stats_stmt)
        # keyed by news.type  e.g. "top_story", "ask_hn", "show_hn"
        news_stats: dict[str, dict] = {
            row.type: {"count": row.cnt, "last_scraped": row.last_scraped}
            for row in news_stats_result.all()
        }

        # jobs table: count + max scraped_at (all from who_is_hiring)
        jobs_stats_stmt = select(
            func.count(Job.id).label("cnt"),
            func.max(Job.scraped_at).label("last_scraped"),
        )
        jobs_stats_result = await db.execute(jobs_stats_stmt)
        jobs_row = jobs_stats_result.one_or_none()
        jobs_stats = {
            "count": jobs_row.cnt if jobs_row else 0,
            "last_scraped": jobs_row.last_scraped if jobs_row else None,
        }

        # ------------------------------------------------------------------ #
        # 4. APScheduler: next_run_time per job                               #
        # ------------------------------------------------------------------ #
        next_run_map: dict[str, str | None] = {}
        try:
            for job in scheduler.get_jobs():
                next_run_map[job.id] = _iso(job.next_run_time)
        except Exception:
            pass

        # ------------------------------------------------------------------ #
        # 5. Assemble per-scraper status                                      #
        # ------------------------------------------------------------------ #
        items: list[ScraperStatusItem] = []

        for scraper_id in _EXPECTED_TOTALS:
            expected = _EXPECTED_TOTALS[scraper_id]
            name = _DISPLAY_NAMES[scraper_id]
            is_active = scraper_id in active_scrapers

            # --- Try tagged Report first ---
            report = tagged_reports.get(scraper_id)
            if report is not None:
                scraped  = report.items_collected or 0
                status   = report.status or "unknown"
                last_upd = _iso(report.run_at)
            else:
                # --- Fallback: infer from actual table data ---
                if scraper_id == "who_is_hiring":
                    scraped      = jobs_stats["count"] or 0
                    last_scraped = jobs_stats["last_scraped"]
                else:
                    news_type    = _NEWS_TYPE[scraper_id]
                    row          = news_stats.get(news_type, {})
                    scraped      = row.get("count", 0) or 0
                    last_scraped = row.get("last_scraped")

                last_upd = _iso(last_scraped)
                # If we found actual data in the DB, mark as completed
                status = "completed" if scraped > 0 else "never_run"

            # Clamp progress
            if status == "completed" and scraped == 0:
                pct, remaining = 100, 0
            else:
                pct, remaining = _compute_progress(scraped, expected)

            # Never show 100 % while still running
            if is_active and pct >= 100:
                pct = 99
                status = "running"

            items.append(
                ScraperStatusItem(
                    scraper_id=scraper_id,
                    name=name,
                    is_active=is_active,
                    progress_percentage=pct,
                    items_scraped=scraped,
                    items_remaining=remaining,
                    status=status,
                    last_updated=last_upd,
                    next_run=next_run_map.get(scraper_id),
                )
            )

        return ScraperStatusResponse(scrapers=items)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch scraper status: {exc}",
        ) from exc
