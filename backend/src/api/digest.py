"""
Digest API endpoint.
GET /api/digest — Personalized news digest with RAG-powered match percentages.
"""
import logging

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from src.db.schemas import PaginationMeta, PaginatedResponse
from src.services.digest_service import get_personalized_digest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digest", tags=["digest"])


@router.get("")
async def get_digest(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=5, ge=1, le=20),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> JSONResponse:
    """
    Get personalized news digest.

    - Returns top-scored + personalized news items blended by RAG
    - Only includes news items with AI summaries
    - match_percentage: 0-100 based on cosine similarity with user profile
    - Pagination: skip/limit, default 5 items per page
    - Authenticated users get personalized results; anonymous get top items
    """
    print(f"\n>>> [API:GET /api/digest] user={x_user_id}, skip={skip}, limit={limit}")

    items, total = await get_personalized_digest(
        user_id=x_user_id,
        skip=skip,
        limit=limit,
    )

    print(f">>> [API:GET /api/digest] Returning {len(items)} items (total={total})")

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
