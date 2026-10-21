"""
News feed REST API endpoint.
"""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

from src.db import repos
from src.db.schemas import (
    ErrorResponse,
    NewsResponse,
    PaginatedResponse,
    PaginationMeta,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/news", tags=["news"])

# Category inference keywords
CATEGORY_KEYWORDS = {
    "HIRING": ["hiring", "looking for", "hire", "job opening", "engineer needed"],
    "LAYOFFS": ["layoff", "laid off", "restructure", "cutting", "downsizing"],
    "FUNDING": ["funding", "raised", "series", "investor", "capital", "valuation"],
    "SKILLS": ["skill", "learn", "tutorial", "course", "how to", "tech stack"],
}


def _infer_category(title: str) -> str:
    """Infer news category from title keywords."""
    title_lower = (title or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return "ALL"


def _source_from_type(news_type: str) -> str:
    """Map news type to display source."""
    mapping = {
        "ask_hn": "Ask HN",
        "show_hn": "Show HN",
        "top_story": "Top Story",
    }
    return mapping.get(news_type or "", (news_type or "").title())


def _row_to_response(row: Dict[str, Any], featured_ids: set[str]) -> NewsResponse:
    """Map a stored news row to the API response."""
    return NewsResponse(
        id=row["id"],
        headline=row.get("title") or "",
        source=_source_from_type(row.get("type") or ""),
        summary=row.get("summary") or "N/A",
        category=_infer_category(row.get("title") or ""),
        readTime="5 min read",
        featured=row["id"] in featured_ids,
    )


@router.get(
    "",
    response_model=PaginatedResponse[NewsResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_news(
    type: str = Query(default="all", description="Filter by type: ask_hn, show_hn, top_story, or all"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[NewsResponse]:
    """
    Get paginated news items from HN.

    - **type**: Filter by news type (ask_hn, show_hn, top_story, or all)
    - **skip**: Number of records to skip (pagination offset)
    - **limit**: Maximum records to return (max 100)
    """
    try:
        news_type = None if not type or type == "all" else type
        rows, total, featured_ids = await repos.list_news_page(
            news_type=news_type, skip=skip, limit=limit
        )

        news_data = [_row_to_response(r, featured_ids) for r in rows]
        has_more = (skip + limit) < total

        return PaginatedResponse(
            data=news_data,
            meta=PaginationMeta(
                total=total,
                skip=skip,
                limit=limit,
                has_more=has_more,
            ),
        )

    except Exception as e:
        logger.exception("GET /api/news failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch news", "code": "DB_ERROR", "detail": str(e)},
        )
