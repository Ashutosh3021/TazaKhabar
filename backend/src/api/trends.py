"""
Trends API endpoint for keyword frequency and week-over-week analysis.
"""
import logging
from datetime import datetime

from fastapi import APIRouter

from src.db.schemas import PaginatedResponse, PaginationMeta
from src.db import repos
from src.services.trend_service import (
    TrendService,
    compute_keyword_frequencies,
    current_week_bounds,
    get_trends,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
async def get_trending_keywords(limit: int = 20) -> dict:
    """
    Get trending keywords with week-over-week analysis.

    Returns top 5 booming (>20% growth) and top 3 declining (>20% decline)
    keywords. When the current week has not been counted yet, it is computed
    on demand.
    """
    try:
        trends = await get_trends(limit)

        week_start, _ = current_week_bounds()
        if not await repos.list_trends(week_start.isoformat()):
            try:
                await compute_keyword_frequencies()
                trends = await get_trends(limit)
            except Exception:
                logger.exception("Failed to compute trends")

        return {
            "data": trends,
            "meta": {
                "total": len(trends),
                "booming_count": len([t for t in trends if t.get("direction") == "booming"]),
                "declining_count": len([t for t in trends if t.get("direction") == "declining"]),
                "week_start": week_start.isoformat(),
            },
        }
    except Exception as e:
        logger.exception("Error fetching trends")
        return {
            "data": [],
            "meta": {"total": 0, "booming_count": 0, "declining_count": 0},
            "error": str(e),
        }


@router.get("/observation")
async def get_trend_observation() -> dict:
    """
    Get the LLM-written paragraph about current trends.

    Returns the most recent observation written by the scraper workflow, or a
    clear message when none has been generated yet.
    """
    try:
        latest = await repos.latest_observation()
        if not latest:
            return {
                "observation": None,
                "message": "No observation generated yet. Run the scraper workflow.",
            }
        return {"observation": latest.get("text"), "generated_at": latest.get("generated_at")}
    except Exception:
        logger.exception("Error fetching observation")
        return {"observation": None, "message": "Error fetching observation."}


@router.post("/compute")
async def trigger_trend_computation() -> dict:
    """Recount keyword frequencies for the current week."""
    try:
        results = await compute_keyword_frequencies()
        return {
            "status": "success",
            "keywords_computed": len(results),
            "keywords": [r["keyword"] for r in results[:10]],
        }
    except Exception as e:
        logger.exception("Error computing trends")
        return {"status": "error", "error": str(e)}


@router.get("/predictions")
async def get_trend_predictions(limit: int = 50) -> dict:
    """
    Return predictions for keywords: {keyword, current, w2, w4, confidence}

    With less than 8 weeks of history the current count is returned and the
    predictions stay null.
    """
    try:
        preds = await TrendService().predict_keywords()
        return {"data": preds[:limit], "meta": {"total": len(preds)}}
    except Exception as e:
        logger.exception("Error computing predictions")
        return {"data": [], "meta": {"total": 0}, "error": str(e)}
