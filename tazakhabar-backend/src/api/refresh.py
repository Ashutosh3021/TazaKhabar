"""
Refresh API endpoint for report swap trigger.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.schemas import RefreshResponse
from src.services.report_service import swap_reports

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/refresh", tags=["refresh"])


@router.post("", response_model=RefreshResponse)
async def trigger_refresh(
    session: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """
    Trigger report swap (Report 2 → Report 1).
    
    FRESH-05: User triggers refresh → backend swaps reports → badge resets to 0.
    Container is empty and ready for next scrape cycle.
    """
    try:
        print(f"\n>>> [API:POST /api/refresh] Request received - triggering report swap")
        result = await swap_reports(session)
        status = result.get("status", "swapped")
        radar = result.get("radar_new_count", 0)
        feed = result.get("feed_new_count", 0)
        print(f">>> [API:POST /api/refresh] Swap complete: status={status}, radar={radar}, feed={feed}")
        print(f">>> [API:POST /api/refresh] Badge counts reset to 0. Ready for next scrape cycle.")
        return RefreshResponse(
            status=status,
            radar_new_count=radar,
            feed_new_count=feed,
        )
    except Exception as e:
        print(f">>> [API:POST /api/refresh] ERROR: {e}")
        import traceback
        print(f">>> [API:POST /api/refresh] TRACE: {traceback.format_exc()}")
        logger.error(f"Error during refresh: {e}")
        return RefreshResponse(
            status="error",
            radar_new_count=0,
            feed_new_count=0,
        )
