"""
News feed REST API endpoint.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import News
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
    title_lower = title.lower()
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
    return mapping.get(news_type, news_type.title())


def _row_to_response(row: News, featured_ids: set[str]) -> NewsResponse:
    """Map SQLAlchemy News row to NewsResponse."""
    return NewsResponse(
        id=row.id,
        headline=row.title,
        source=_source_from_type(row.type),
        summary="N/A",  # Will be filled by Phase 2 LLM
        category=_infer_category(row.title),
        readTime="5 min read",
        featured=row.id in featured_ids,
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
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NewsResponse]:
    """
    Get paginated news items from HN.

    - **type**: Filter by news type (ask_hn, show_hn, top_story, or all)
    - **skip**: Number of records to skip (pagination offset)
    - **limit**: Maximum records to return (max 100)
    """
    try:
        print(f"\n>>> [API:GET /api/news] Request received")
        print(f"    Filters -> type: '{type}'")
        print(f"    Pagination -> skip: {skip}, limit: {limit}")
        
        # Build base filter — only active report version
        base_filter = News.report_version == "1"

        # Type filter
        if type and type != "all":
            base_filter = base_filter & (News.type == type)
            print(f"    Filter: type = '{type}'")

        # Count query
        count_query = select(func.count(News.id)).where(base_filter)
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        print(f"    DB total count: {total} news items")

        # Data query: sort by score desc, then scraped_at desc
        query = (
            select(News)
            .where(base_filter)
            .order_by(News.score.desc(), News.scraped_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        rows = result.scalars().all()
        print(f"    DB returned: {len(rows)} news items")

        # Determine featured: top 3 by score get featured=True
        # We need to know overall ranking, not just within the page
        featured_query = (
            select(News)
            .where(base_filter)
            .order_by(News.score.desc())
            .limit(3)
        )
        featured_result = await db.execute(featured_query)
        featured_ids = {r.id for r in featured_result.scalars().all()}
        print(f"    Featured: {len(featured_ids)} items")

        news_data = [_row_to_response(r, featured_ids) for r in rows]
        has_more = (skip + limit) < total
        
        print(f">>> [API:GET /api/news] Response: {len(news_data)} items (total: {total}, has_more: {has_more})")

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
        print(f">>> [API:GET /api/news] ERROR: {e}")
        import traceback
        print(f">>> [API:GET /api/news] TRACE: {traceback.format_exc()}")
        logger.error(f"Error fetching news: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch news", "code": "DB_ERROR", "detail": str(e)},
        )
