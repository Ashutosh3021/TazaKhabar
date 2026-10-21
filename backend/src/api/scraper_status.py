"""
Scraper status API endpoint.

GET /api/scrapers/status

Scrapers run in the GitHub Actions workflow, so the status is derived from the
shared state table (last run per scraper) plus the row counts in the store.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db import repos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])

# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------
# "news_type" is set for the scrapers that write to the news table.
_SCRAPERS: List[Dict[str, Any]] = [
    {
        "scraper_id": "who_is_hiring",
        "name": "Who Is Hiring (HN)",
        "news_type": None,  # writes to the jobs table
        "expected": 500,
    },
    {
        "scraper_id": "top_stories",
        "name": "Top Stories (HN)",
        "news_type": "top_story",
        "expected": 30,
    },
    {
        "scraper_id": "ask_hn",
        "name": "Ask HN",
        "news_type": "ask_hn",
        "expected": 200,
    },
    {
        "scraper_id": "show_hn",
        "name": "Show HN",
        "news_type": "show_hn",
        "expected": 200,
    },
]


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
    scrapers: List[ScraperStatusItem]


def _progress(scraped: int, expected: int) -> tuple[int, int]:
    """(progress_pct, items_remaining) both clamped sensibly."""
    if expected <= 0:
        return (100 if scraped > 0 else 0), 0
    pct = min(100, round(scraped * 100 / expected))
    remaining = max(0, expected - scraped)
    return pct, remaining


@router.get("/status", response_model=ScraperStatusResponse)
async def get_scraper_status() -> ScraperStatusResponse:
    """Progress and last-run state for every scraper."""
    try:
        news_counts = await repos.news_counts_by_type()
        hn_job_stats = await repos.hn_job_stats()

        items: List[ScraperStatusItem] = []
        for cfg in _SCRAPERS:
            scraper_id = cfg["scraper_id"]
            expected = cfg["expected"]

            status = await repos.get_state(f"scraper:{scraper_id}:status") or "never_run"
            raw_stats = await repos.get_state(f"scraper:{scraper_id}:stats")
            last_updated = None
            if raw_stats:
                try:
                    stats = json.loads(raw_stats)
                    last_updated = stats.get("at")
                    scraped = int(stats.get("collected") or 0)
                except (TypeError, ValueError):
                    scraped = 0
            else:
                scraped = 0

            news_type = cfg.get("news_type")
            if news_type is None:
                scraped = hn_job_stats["count"] or 0
                last_updated = hn_job_stats["last_scraped"]
            elif scraped == 0:
                row = news_counts.get(news_type, {})
                scraped = row.get("count", 0)
                last_updated = row.get("last_scraped")

            pct, remaining = _progress(scraped, expected)
            if status == "completed" and scraped == 0:
                pct, remaining = 100, 0

            items.append(
                ScraperStatusItem(
                    scraper_id=scraper_id,
                    name=cfg["name"],
                    is_active=status == "running",
                    progress_percentage=pct,
                    items_scraped=scraped,
                    items_remaining=remaining,
                    status=status,
                    last_updated=last_updated,
                    next_run=None,
                )
            )

        return ScraperStatusResponse(scrapers=items)

    except Exception as exc:
        logger.exception("Scraper status fetch failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch scraper status: {exc}",
        ) from exc
