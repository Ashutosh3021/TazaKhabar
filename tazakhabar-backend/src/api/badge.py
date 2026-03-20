"""
Badge counter API endpoint for lightweight polling.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.schemas import BadgeResponse
from src.services.report_service import get_badge_counts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/badge", tags=["badge"])


@router.get("", response_model=BadgeResponse)
async def get_badge(
    session: AsyncSession = Depends(get_db),
) -> BadgeResponse:
    """
    Get badge counts for new items since last scrape cycle.
    
    FRESH-04: Lightweight endpoint for 5-minute polling.
    Returns only {radar_new_count, feed_new_count}.
    """
    try:
        print(f"\n>>> [API:GET /api/badge] Request received (5-min poll)")
        counts = await get_badge_counts(session)
        radar = counts.get("radar_new_count", 0)
        feed = counts.get("feed_new_count", 0)
        print(f">>> [API:GET /api/badge] Response: radar={radar}, feed={feed}")
        return BadgeResponse(
            radar_new_count=radar,
            feed_new_count=feed,
        )
    except Exception as e:
        print(f">>> [API:GET /api/badge] ERROR: {e}")
        import traceback
        print(f">>> [API:GET /api/badge] TRACE: {traceback.format_exc()}")
        logger.error(f"Error fetching badge counts: {e}")
        # Return zeros on error to avoid breaking the frontend
        return BadgeResponse(radar_new_count=0, feed_new_count=0)
