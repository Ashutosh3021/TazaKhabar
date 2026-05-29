"""
Notebook pipeline API — sync CSV / HN scraper output into the running app database.
"""
import logging

from fastapi import APIRouter, Query

from src.scheduler import run_all_scrapers_now
from src.services.notebook_sync_service import (
    get_notebook_sync_status,
    sync_all_notebook_outputs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


@router.get("/status")
async def notebook_sync_status() -> dict:
    """CSV files, last sync state, and watcher settings."""
    return await get_notebook_sync_status()


@router.post("/sync")
async def notebook_sync_now(
    force: bool = Query(default=False, description="Re-import even if CSV unchanged"),
) -> dict:
    """
    Immediately load notebook outputs into the database.

  Call this from Jupyter after saving jobs_output.csv, or rely on the
  background watcher (every NOTEBOOK_SYNC_INTERVAL_SEC seconds).
    """
    return await sync_all_notebook_outputs(force=force)


@router.post("/sync-hn")
async def notebook_sync_hacker_news() -> dict:
    """
    Run the same HN scrapers as tazakhabar_scraper.ipynb (Who Is Hiring, Top Stories, etc.)
    directly into the app database.
    """
    scrapers = await run_all_scrapers_now()
    csv_sync = await sync_all_notebook_outputs(force=False)
    return {"status": "ok", "scrapers": scrapers, "csv": csv_sync}
