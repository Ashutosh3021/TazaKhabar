"""
Scraper status API endpoint.

GET /api/scrapers/status

Returns real-time progress information for all known scrapers, built from the
latest Report row per scraper_name combined with APScheduler job metadata.

Response shape
--------------
{
  "scrapers": [
    {
      "scraper_id":          str,   # scheduler job ID / scraper_name
      "name":                str,   # human-readable label
      "is_active":           bool,  # True while status == "running"
      "progress_percentage": int,   # 0-100
      "items_scraped":       int,   # items_collected from latest Report
      "items_remaining":     int,   # max(0, expected_total - items_scraped)
      "status":              str,   # "running" | "completed" | "failed" | "never_run"
      "last_updated":        str,   # ISO-8601 UTC timestamp of last run_at
      "next_run":            str | null  # ISO-8601 UTC of next scheduled run
    },
    ...
  ]
}
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Report
from src.scheduler import scheduler

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])

# ---------------------------------------------------------------------------
# Expected total items per scraper (based on batch sizes in each scraper).
# Used to compute progress_percentage and items_remaining.
# Top-stories fetches 30 IDs and then filters by score; we use 30 as the
# ceiling.  Who Is Hiring is variable; we use 500 as a reasonable upper bound.
# ---------------------------------------------------------------------------
_EXPECTED_TOTALS: dict[str, int] = {
    "who_is_hiring": 500,
    "top_stories": 30,
    "ask_hn": 200,
    "show_hn": 200,
}

_DISPLAY_NAMES: dict[str, str] = {
    "who_is_hiring": "Who Is Hiring",
    "top_stories": "Top Stories",
    "ask_hn": "Ask HN",
    "show_hn": "Show HN",
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
# Helper
# ---------------------------------------------------------------------------

def _iso(dt: datetime | None) -> str | None:
    """Return an ISO-8601 UTC string or None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _compute_progress(items_scraped: int, expected: int) -> tuple[int, int]:
    """Return (progress_percentage, items_remaining) clamped to [0, 100]."""
    if expected <= 0:
        pct = 100 if items_scraped > 0 else 0
        return pct, 0
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
        "Returns the real-time status of every HN scraper: whether it is "
        "currently active, how many items have been scraped, estimated "
        "progress percentage, items remaining, and the next scheduled run time."
    ),
)
async def get_scraper_status(
    db: AsyncSession = Depends(get_db),
) -> ScraperStatusResponse:
    """
    Query the latest Report row for each scraper and combine with
    APScheduler metadata to build a progress report for all scrapers.
    """
    try:
        # --- 1. Fetch the most recent Report per scraper_name ---
        # Subquery: max run_at per scraper_name
        subq = (
            select(
                Report.scraper_name,
                func.max(Report.run_at).label("latest_run_at"),
            )
            .where(Report.scraper_name.isnot(None))
            .group_by(Report.scraper_name)
            .subquery()
        )

        stmt = select(Report).join(
            subq,
            (Report.scraper_name == subq.c.scraper_name)
            & (Report.run_at == subq.c.latest_run_at),
        )
        result = await db.execute(stmt)
        latest_reports: dict[str, Report] = {
            r.scraper_name: r for r in result.scalars().all() if r.scraper_name
        }

        # --- 2. Build next_run lookup from APScheduler ---
        next_run_map: dict[str, str | None] = {}
        try:
            for job in scheduler.get_jobs():
                next_run_map[job.id] = _iso(job.next_run_time)
        except Exception:
            pass  # scheduler may not be running in test environments

        # --- 3. Assemble status for every known scraper ---
        items: list[ScraperStatusItem] = []
        for scraper_id in _EXPECTED_TOTALS:
            report = latest_reports.get(scraper_id)
            expected = _EXPECTED_TOTALS[scraper_id]
            name = _DISPLAY_NAMES.get(scraper_id, scraper_id)

            if report is None:
                # Scraper has never run (fresh DB)
                items.append(
                    ScraperStatusItem(
                        scraper_id=scraper_id,
                        name=name,
                        is_active=False,
                        progress_percentage=0,
                        items_scraped=0,
                        items_remaining=expected,
                        status="never_run",
                        last_updated=None,
                        next_run=next_run_map.get(scraper_id),
                    )
                )
                continue

            scraped = report.items_collected or 0
            status = report.status or "unknown"
            is_active = status == "running"

            # A completed run with 0 items still counts as 100 % done
            if status == "completed" and scraped == 0:
                pct, remaining = 100, 0
            else:
                pct, remaining = _compute_progress(scraped, expected)

            # If still running, do not show 100 % yet
            if is_active and pct == 100:
                pct = 99

            items.append(
                ScraperStatusItem(
                    scraper_id=scraper_id,
                    name=name,
                    is_active=is_active,
                    progress_percentage=pct,
                    items_scraped=scraped,
                    items_remaining=remaining,
                    status=status,
                    last_updated=_iso(report.run_at),
                    next_run=next_run_map.get(scraper_id),
                )
            )

        return ScraperStatusResponse(scrapers=items)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch scraper status: {exc}") from exc
