"""
Refresh API endpoint for report swap trigger.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import async_session
from src.db.schemas import RefreshResponse
from src.services.report_service import swap_reports

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


@router.post("", response_model=RefreshResponse)
async def trigger_refresh(
    session: AsyncSession = Depends(async_session),
) -> RefreshResponse:
    """
    Trigger report swap (Report 2 → Report 1).
    
    FRESH-05: User triggers refresh → backend swaps reports → badge resets to 0.
    Container is empty and ready for next scrape cycle.
    """
    try:
        result = await swap_reports(session)
        return RefreshResponse(
            status=result.get("status", "swapped"),
            radar_new_count=result.get("radar_new_count", 0),
            feed_new_count=result.get("feed_new_count", 0),
        )
    except Exception as e:
        logger.error(f"Error during refresh: {e}")
        return RefreshResponse(
            status="error",
            radar_new_count=0,
            feed_new_count=0,
        )
