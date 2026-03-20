"""
Badge counter API endpoint for lightweight polling.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import async_session
from src.db.schemas import BadgeResponse
from src.services.report_service import get_badge_counts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/badge", tags=["badge"])


@router.get("", response_model=BadgeResponse)
async def get_badge(
    session: AsyncSession = Depends(async_session),
) -> BadgeResponse:
    """
    Get badge counts for new items since last scrape cycle.
    
    FRESH-04: Lightweight endpoint for 5-minute polling.
    Returns only {radar_new_count, feed_new_count}.
    """
    try:
        counts = await get_badge_counts(session)
        return BadgeResponse(
            radar_new_count=counts.get("radar_new_count", 0),
            feed_new_count=counts.get("feed_new_count", 0),
        )
    except Exception as e:
        logger.error(f"Error fetching badge counts: {e}")
        # Return zeros on error to avoid breaking the frontend
        return BadgeResponse(radar_new_count=0, feed_new_count=0)
