"""
Refresh API endpoint for report swap trigger.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.schemas import RefreshResponse
from src.services.report_service import advance_report_cycle

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
        # BUG FIX [M1]: wired advance_report_cycle into refresh endpoint
        print(f"\n>>> [API:POST /api/refresh] Request received - triggering report swap")
        result = await advance_report_cycle(session)
        status = result.get("status", "swapped")
        new_jobs = result.get("new_jobs", 0)
        new_news = result.get("new_news", 0)
        print(f">>> [API:POST /api/refresh] Swap complete: status={status}, new_jobs={new_jobs}, new_news={new_news}")
        print(f">>> [API:POST /api/refresh] Badge counts reset to 0. Ready for next scrape cycle.")
        return RefreshResponse(
            status=status,
            new_jobs=new_jobs,
            new_news=new_news,
        )
    except Exception as e:
        print(f">>> [API:POST /api/refresh] ERROR: {e}")
        import traceback
        print(f">>> [API:POST /api/refresh] TRACE: {traceback.format_exc()}")
        logger.error(f"Error during refresh: {e}")
        return RefreshResponse(
            status="error",
            new_jobs=0,
            new_news=0,
        )
