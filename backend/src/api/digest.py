"""
Digest API endpoint.
GET /api/digest — Personalized news digest with RAG-powered match percentages.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.deps import optional_user
from src.services.digest_service import get_personalized_digest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digest", tags=["digest"])


@router.get("")
async def get_digest(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=5, ge=1, le=20),
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> JSONResponse:
    """
    Get personalized news digest.

    - Returns top-scored + personalized news items blended by RAG
    - Only includes news items with AI summaries
    - match_percentage: 0-100 based on cosine similarity with the user profile
    - Signed-in users get personalized results; anonymous callers get top items
    """
    user_id = user.get("id") if user else None
    items, total = await get_personalized_digest(user_id=user_id, skip=skip, limit=limit)

    return JSONResponse(
        content={
            "data": items,
            "meta": {
                "total": total,
                "skip": skip,
                "limit": limit,
                "has_more": skip + limit < total,
            },
        }
    )
