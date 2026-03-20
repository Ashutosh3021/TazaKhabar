"""
Trends API endpoint for keyword frequency and week-over-week analysis.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.schemas import PaginatedResponse, PaginationMeta
from src.services.trend_service import compute_keyword_frequencies, get_trends, TrendService, TECH_KEYWORDS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
async def get_trending_keywords(
    limit: int = 20,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get trending keywords with week-over-week analysis.
    
    Returns top 5 booming (>20% growth) and top 3 declining (>20% decline) keywords.
    
    TRND-06: Returns {data: [Trend, ...], meta: {count: int}}
    """
    try:
        trends = await get_trends(session, limit)
        
        return {
            "data": trends,
            "meta": {
                "total": len(trends),
                "booming_count": len([t for t in trends if t.get("direction") == "booming"]),
                "declining_count": len([t for t in trends if t.get("direction") == "declining"]),
                "week_start": (datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)).isoformat(),
            }
        }
    except Exception as e:
        logger.error(f"Error fetching trends: {e}")
        return {
            "data": [],
            "meta": {"total": 0, "booming_count": 0, "declining_count": 0},
            "error": str(e),
        }


@router.get("/observation")
async def get_trend_observation() -> dict:
    """
    Get LLM-written paragraph about current trends.
    
    TRND-08: Phase 2 — for now returns static placeholder text.
    """
    return {
        "data": {
            "text": "Trends are being computed. Check back after your first scrape cycle. "
                    "The analysis will provide insights into hiring velocity, skill demand shifts, "
                    "and market signals based on HackerNews data."
        }
    }


@router.post("/compute")
async def trigger_trend_computation(
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Manually trigger keyword frequency computation.
    Useful for testing or immediate refresh.
    """
    try:
        results = await compute_keyword_frequencies(session)
        return {
            "status": "success",
            "keywords_computed": len(results),
            "keywords": [r["keyword"] for r in results[:10]],  # Return first 10 as sample
        }
    except Exception as e:
        logger.error(f"Error computing trends: {e}")
        return {
            "status": "error",
            "error": str(e),
        }
