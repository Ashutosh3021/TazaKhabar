"""
Notebook pipeline API — sync CSV output into the running store.

These endpoints are for the notebook workflow and are guarded by the admin
token. In production the GitHub Actions workflow is the sanctioned writer.
"""
import logging

from fastapi import APIRouter, Header, HTTPException, Query

from src.config import settings
from src.services.notebook_sync_service import (
    get_notebook_sync_status,
    sync_all_notebook_outputs,
)
from src.services.scraper_runner import run_all_scrapers_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


def _require_admin(x_admin_token: str | None) -> None:
    if settings.ADMIN_TOKEN and x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")


@router.get("/status")
async def notebook_sync_status() -> dict:
    """CSV files, last sync state, and watcher settings."""
    return await get_notebook_sync_status()


@router.post("/sync")
async def notebook_sync_now(
    force: bool = Query(default=False, description="Re-import even if CSV unchanged"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    """
    Immediately load notebook outputs into the store.
    """
    _require_admin(x_admin_token)
    return await sync_all_notebook_outputs(force=force)


@router.post("/sync-hn")
async def notebook_sync_hacker_news(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    """
    Run the HN scrapers (Who Is Hiring, Top Stories, Ask HN, Show HN).
    """
    _require_admin(x_admin_token)
    scrapers = await run_all_scrapers_now()
    csv_sync = await sync_all_notebook_outputs(force=False)
    return {"status": "ok", "scrapers": scrapers, "csv": csv_sync}
