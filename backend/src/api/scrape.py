"""
Manual scraper trigger API.

Scraping normally runs in the GitHub Actions workflow. This endpoint stays for
local development and is guarded by the admin token.
"""
import logging

from fastapi import APIRouter, Header, HTTPException

from src.config import settings
from src.services.scraper_runner import run_all_scrapers_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


@router.post("/run")
async def trigger_scrapers(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    """
    Run all HN scrapers immediately (Who Is Hiring, Top Stories, Ask HN, Show HN).

    Requires the admin token when ADMIN_TOKEN is configured.
    """
    if settings.ADMIN_TOKEN and x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    results = await run_all_scrapers_now()
    failed = [k for k, v in results.items() if not v.startswith("ok")]
    return {
        "status": "partial" if failed else "success",
        "scrapers": results,
    }
