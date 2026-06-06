"""
Scraper status API endpoint.

GET /api/scrapers/status

Returns real-time progress for all scrapers across two pipelines:

  HN Pipeline  (APScheduler, every 2h):
    who_is_hiring  → jobs table  (hn_item_id IS NOT NULL)
    top_stories    → news table  (type = 'top_story')
    ask_hn         → news table  (type = 'ask_hn')
    show_hn        → news table  (type = 'show_hn')

  Notebook Pipeline  (job_scraper.ipynb → jobs_output.csv → CSV watcher):
    ambitionbox_jobs → jobs table (hn_item_id IS NULL)
                       Progress read from .notebook_sync_state.json
                       Total = companies in company_data.csv (9 497 currently)

Response shape
--------------
{
  "scrapers": [
    {
      "scraper_id":          str,
      "name":                str,
      "is_active":           bool,
      "progress_percentage": int,    # 0-100
      "items_scraped":       int,
      "items_remaining":     int,
      "status":              str,    # "running"|"completed"|"failed"|"never_run"
      "last_updated":        str | null,
      "next_run":            str | null
    }, ...
  ]
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Job, News, Report
from src.scheduler import scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])

# ---------------------------------------------------------------------------
# Notebook sync-state file (written by notebook_sync_service)
# ---------------------------------------------------------------------------
_STATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "NoteBooks"
    / ".notebook_sync_state.json"
)
_COMPANY_CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent / "NoteBooks" / "company_data.csv"
)

# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------
# "pipeline" is either "hn" or "notebook"
# "news_type" (hn pipeline only): maps to news.type column
# "expected": default ceiling for progress calc
_SCRAPERS: list[dict] = [
    {
        "scraper_id": "ambitionbox_jobs",
        "name": "AmbitionBox Jobs (Notebook)",
        "pipeline": "notebook",
        "expected": 9497,          # total companies in company_data.csv
    },
    {
        "scraper_id": "who_is_hiring",
        "name": "Who Is Hiring (HN)",
        "pipeline": "hn",
        "news_type": None,          # goes to jobs table
        "expected": 500,
    },
    {
        "scraper_id": "top_stories",
        "name": "Top Stories (HN)",
        "pipeline": "hn",
        "news_type": "top_story",
        "expected": 30,
    },
    {
        "scraper_id": "ask_hn",
        "name": "Ask HN",
        "pipeline": "hn",
        "news_type": "ask_hn",
        "expected": 200,
    },
    {
        "scraper_id": "show_hn",
        "name": "Show HN",
        "pipeline": "hn",
        "news_type": "show_hn",
        "expected": 200,
    },
]


# ---------------------------------------------------------------------------
# Pydantic models
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


def _progress(scraped: int, expected: int) -> tuple[int, int]:
    """(progress_pct, items_remaining) both clamped sensibly."""
    if expected <= 0:
        return (100 if scraped > 0 else 0), 0
    pct = min(100, round(scraped * 100 / expected))
    remaining = max(0, expected - scraped)
    return pct, remaining


def _read_notebook_state() -> dict:
    try:
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _count_company_csv() -> int:
    """Count data rows in company_data.csv (cached cheaply)."""
    try:
        import csv as csv_mod
        with _COMPANY_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
            reader = csv_mod.reader(f)
            next(reader, None)  # skip header
            return sum(1 for _ in reader)
    except Exception:
        return 9497  # fall back to known value


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/status",
    response_model=ScraperStatusResponse,
    summary="Scraper progress status",
    description=(
        "Returns real-time progress for all scrapers — both the HN pipeline "
        "(who_is_hiring, top_stories, ask_hn, show_hn) and the AmbitionBox "
        "notebook pipeline (job_scraper.ipynb → jobs_output.csv)."
    ),
)
async def get_scraper_status(
    db: AsyncSession = Depends(get_db),
) -> ScraperStatusResponse:
    try:
        # ------------------------------------------------------------------ #
        # 1. Tagged Reports — latest per scraper_name (post-migration runs)   #
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
        # 2. Active (currently running) scrapers from Report table            #
        # ------------------------------------------------------------------ #
        active_result = await db.execute(
            select(Report.scraper_name).where(
                Report.status == "running",
                Report.scraper_name.isnot(None),
            )
        )
        active_scrapers: set[str] = {r[0] for r in active_result.all() if r[0]}

        # ------------------------------------------------------------------ #
        # 3. HN fallback: news table stats per type + HN jobs count           #
        # ------------------------------------------------------------------ #
        news_stats_result = await db.execute(
            select(
                News.type,
                func.count(News.id).label("cnt"),
                func.max(News.scraped_at).label("last_scraped"),
            ).group_by(News.type)
        )
        news_stats: dict[str, dict] = {
            row.type: {"count": row.cnt, "last_scraped": row.last_scraped}
            for row in news_stats_result.all()
        }

        # HN jobs: hn_item_id IS NOT NULL
        hn_jobs_result = await db.execute(
            select(
                func.count(Job.id).label("cnt"),
                func.max(Job.scraped_at).label("last_scraped"),
            ).where(Job.hn_item_id.isnot(None))
        )
        hn_jobs_row = hn_jobs_result.one_or_none()
        hn_jobs_stats = {
            "count": hn_jobs_row.cnt if hn_jobs_row else 0,
            "last_scraped": hn_jobs_row.last_scraped if hn_jobs_row else None,
        }

        # ------------------------------------------------------------------ #
        # 4. Notebook pipeline: AmbitionBox CSV jobs (hn_item_id IS NULL)     #
        # ------------------------------------------------------------------ #
        nb_jobs_result = await db.execute(
            select(
                func.count(Job.id).label("cnt"),
                func.max(Job.scraped_at).label("last_scraped"),
            ).where(Job.hn_item_id.is_(None))
        )
        nb_jobs_row = nb_jobs_result.one_or_none()
        nb_jobs_in_db = nb_jobs_row.cnt if nb_jobs_row else 0
        nb_last_scraped = nb_jobs_row.last_scraped if nb_jobs_row else None

        # Notebook sync state gives us CSV row count (= companies attempted)
        nb_state = _read_notebook_state()
        nb_csv_info = nb_state.get("jobs_output.csv", {})
        nb_csv_rows = int(nb_csv_info.get("row_count", 0))  # CSV rows written so far
        nb_last_sync = nb_csv_info.get("last_sync")

        # Total expected = total companies in company_data.csv
        nb_total_companies = _count_company_csv()

        # ------------------------------------------------------------------ #
        # 5. APScheduler next_run map                                         #
        # ------------------------------------------------------------------ #
        next_run_map: dict[str, str | None] = {}
        try:
            for job in scheduler.get_jobs():
                next_run_map[job.id] = _iso(job.next_run_time)
        except Exception:
            pass

        # ------------------------------------------------------------------ #
        # 6. Assemble per-scraper status items                                #
        # ------------------------------------------------------------------ #
        items: list[ScraperStatusItem] = []

        for cfg in _SCRAPERS:
            scraper_id: str = cfg["scraper_id"]
            name: str = cfg["name"]
            pipeline: str = cfg["pipeline"]
            expected: int = cfg["expected"]
            is_active = scraper_id in active_scrapers

            # ---- Notebook pipeline (AmbitionBox) ---- #
            if pipeline == "notebook":
                # Items scraped = jobs loaded into DB from CSV
                scraped = nb_jobs_in_db
                # Use company CSV total as the ceiling (how many companies to go)
                expected = nb_total_companies or expected
                # last_updated: prefer last_sync timestamp, fall back to DB scraped_at
                last_upd = nb_last_sync or _iso(nb_last_scraped)
                # Status: if we have CSV rows written, it has run
                if nb_csv_rows > 0 or scraped > 0:
                    status = "running" if is_active else "completed"
                else:
                    status = "never_run"

                # Progress against total companies (CSV rows ~ companies attempted)
                progress_count = nb_csv_rows if nb_csv_rows > 0 else scraped
                pct, remaining = _progress(progress_count, expected)

                # Notebook has no APScheduler job — it runs manually / via watcher
                next_run = None

            # ---- HN pipeline ---- #
            else:
                news_type: str | None = cfg.get("news_type")
                report = tagged_reports.get(scraper_id)

                if report is not None:
                    # Use tagged Report (accurate for post-migration runs)
                    scraped = report.items_collected or 0
                    status = report.status or "unknown"
                    last_upd = _iso(report.run_at)
                    # When completed, treat the actual items fetched as the ceiling
                    # so progress shows 100% instead of a misleading partial %.
                    if status == "completed" and scraped > 0:
                        expected = scraped
                else:
                    # Fallback: query actual table data
                    if news_type is None:
                        # who_is_hiring → jobs table (HN only)
                        scraped = hn_jobs_stats["count"] or 0
                        last_upd = _iso(hn_jobs_stats["last_scraped"])
                    else:
                        row = news_stats.get(news_type, {})
                        scraped = row.get("count", 0) or 0
                        last_upd = _iso(row.get("last_scraped"))

                    status = "completed" if scraped > 0 else "never_run"

                pct, remaining = _progress(scraped, expected)
                next_run = next_run_map.get(scraper_id)

            # Never show 100% while still running
            if is_active:
                status = "running"
                if pct >= 100:
                    pct = 99

            # Completed with 0 new items this run is still done (dedup skipped all)
            if status == "completed" and scraped == 0:
                pct, remaining = 100, 0

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
                    next_run=next_run,
                )
            )

        return ScraperStatusResponse(scrapers=items)

    except Exception as exc:
        logger.exception("Scraper status fetch failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch scraper status: {exc}",
        ) from exc
