"""
Manual scraper trigger API.
"""
import logging

from fastapi import APIRouter

from src.scheduler import run_all_scrapers_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


@router.post("/run")
async def trigger_scrapers() -> dict:
    """
    Run all HN scrapers immediately (Who Is Hiring, Top Stories, Ask HN, Show HN).

    Scrapers also run automatically every 2 hours while the backend is running.
    New items are stored with report_version='2' until POST /api/refresh promotes them.
    """
    results = await run_all_scrapers_now()
    failed = [k for k, v in results.items() if not v.startswith("ok")]
    return {
        "status": "partial" if failed else "success",
        "scrapers": results,
        "hint": "Load CSV jobs via POST /api/csv/load-jobs if the jobs table is still empty.",
    }
