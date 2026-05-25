"""
Digest service for personalized news recommendations.
Blends top-scored and personalized (RAG) news items.
"""
import logging
from datetime import datetime

from sqlalchemy import select

from src.db.database import async_session
from src.db.models import Embedding, News
from src.services.embedding_service import cosine_similarity_bytes, normalize_similarity

logger = logging.getLogger(__name__)

_SOURCE_LABELS = {
    "ask_hn": "Ask HN",
    "show_hn": "Show HN",
    "top_story": "Top Story",
}

_CATEGORY_KEYWORDS = {
    "HIRING": ["hire", "hiring", "looking for", "searching for", "join", "career"],
    "LAYOFFS": ["layoff", "laid off", "fired", "cut", "restructure", "downsize"],
    "FUNDING": ["fund", "raise", "series", "invest", "venture", "seed round", "IPO"],
}


def _source_label(news_type: str) -> str:
    return _SOURCE_LABELS.get(news_type, news_type.title())


def _infer_category(title: str) -> str:
    title_lower = title.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return "ALL"


async def get_personalized_digest(
    user_id: str | None,
    skip: int = 0,
    limit: int = 5,
) -> tuple[list[dict], int]:
    """
    Return personalized news items with match percentages.

    Blends top-scored + personalized via weighted scoring.
    Only returns news items with AI summaries (News.summary != None).

    Fallback for anonymous users: If no embedded news exist, returns summarized news by score.

    Returns:
        (items: list[dict], total_count: int)
    """
    async with async_session() as session:
        # 1. Get user embedding (if user_id provided)
        user_emb = None
        if user_id:
            stmt = select(Embedding).where(
                Embedding.item_id == user_id,
                Embedding.item_type == "user_profile",
            )
            result = await session.execute(stmt)
            user_emb = result.scalar_one_or_none()

        # 2. Get news items with embeddings (only summarized, active report)
        news_stmt = (
            select(Embedding, News)
            .join(News, Embedding.item_id == News.id)
            .where(
                Embedding.item_type == "news",
                News.report_version == "1",
                News.summary != None,  # Only summarized items
            )
            .order_by(News.score.desc())
        )
        news_result = await session.execute(news_stmt)
        news_rows = news_result.all()

        logger.info(f"[DIGEST] Found {len(news_rows)} summarized news items with embeddings")

        # Fallback for anonymous users: If no embedded news exist, get summarized news by score
        if not news_rows:
            fallback_stmt = (
                select(News)
                .where(
                    News.report_version == "1",
                    News.summary != None,
                )
                .order_by(News.score.desc())
            )
            fallback_result = await session.execute(fallback_stmt)
            fallback_news = fallback_result.scalars().all()
            
            logger.info(f"[DIGEST] No embeddings found, using fallback: {len(fallback_news)} summarized items")
            
            scored_items = []
            for news in fallback_news:
                # Anonymous users get 0 match percentage
                scored_items.append((news, 0, float(news.score)))
        else:
            # 3. Compute blended scores
            scored_items = []
            for emb, news in news_rows:
                if user_emb:
                    sim = cosine_similarity_bytes(user_emb.embedding, emb.embedding)
                    match_pct = normalize_similarity(sim)
                    # Blend: 40% score rank + 60% similarity rank
                    score_rank = news.score
                    blended = float(score_rank) * 0.4 + float(sim) * 0.6
                else:
                    # Fallback for anonymous: use score only
                    match_pct = 0
                    sim = 0.0
                    blended = float(news.score)

                scored_items.append((news, match_pct, blended))

        # 4. Sort by blended score, apply pagination
        scored_items.sort(key=lambda x: x[2], reverse=True)
        total = len(scored_items)
        page = scored_items[skip : skip + limit]

        # 5. Build response
        items = []
        for idx, (news, match_pct, _) in enumerate(page):
            items.append(
                {
                    "id": news.id,
                    "headline": news.title,
                    "source": _source_label(news.type),
                    "summary": news.summary or "N/A",
                    "category": _infer_category(news.title),
                    "readTime": "5 min read",
                    "score": news.score,
                    "match_percentage": match_pct,
                    "featured": idx < 3,
                }
            )

        logger.info(f"[DIGEST] Returning {len(items)} items (total={total}, user_id={user_id})")
        return items, total


