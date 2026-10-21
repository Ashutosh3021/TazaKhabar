"""
Badge counter API endpoint for lightweight polling.

Freshness is per user: the badge counts items scraped since that user's
``feed_last_seen_at``. There is no global report swap any more.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from src.api.deps import optional_user, require_user
from src.db import repos
from src.db.schemas import BadgeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/badge", tags=["badge"])


@router.get("", response_model=BadgeResponse)
async def get_badge(
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> BadgeResponse:
    """
    Get badge counts for items the user has not seen yet.

    Signed-in users are counted from their last "mark seen" moment; anonymous
    callers get the last 24 hours.
    """
    try:
        fallback = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        counts = await repos.badge_counts(user["id"] if user else None, fallback)
        return BadgeResponse(
            new_jobs=counts.get("new_jobs", 0),
            new_news=counts.get("new_news", 0),
        )
    except Exception:
        logger.exception("Error fetching badge counts")
        return BadgeResponse(new_jobs=0, new_news=0)


@router.post("/seen", response_model=BadgeResponse)
async def mark_seen(user: Dict[str, Any] = Depends(require_user)) -> BadgeResponse:
    """Mark everything up to now as seen for this user."""
    try:
        await repos.set_feed_last_seen(user["id"])
        return BadgeResponse(new_jobs=0, new_news=0)
    except Exception:
        logger.exception("Error marking feed as seen")
        return BadgeResponse(new_jobs=0, new_news=0)
