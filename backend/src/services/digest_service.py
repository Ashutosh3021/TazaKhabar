"""
Digest service for personalized news recommendations.
Blends top-scored and personalized (RAG) news items.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.db import repos
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
    return _SOURCE_LABELS.get(news_type or "", (news_type or "").title())


def _infer_category(title: str) -> str:
    title_lower = (title or "").lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return category
    return "ALL"


async def get_personalized_digest(
    user_id: Optional[str],
    skip: int = 0,
    limit: int = 5,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Return personalized news items with match percentages.

    Blends top-scored and personalized items through weighted scoring. Only
    items that have an AI summary are returned. Anonymous callers get the
    top-scored items with a match percentage of 0.
    """
    user_emb = await repos.get_embedding(user_id, "user_profile") if user_id else None

    news_items = await repos.list_news(summarized_only=True, limit=200)
    logger.info("[DIGEST] %s summarized news items available", len(news_items))

    emb_map: Dict[str, bytes] = {}
    if user_emb and news_items:
        emb_map = await repos.get_embeddings([n["id"] for n in news_items], "news")

    scored: List[Tuple[Dict[str, Any], float, float]] = []
    for item in news_items:
        blob = emb_map.get(item["id"])
        if user_emb and blob:
            similarity = cosine_similarity_bytes(user_emb, blob)
            match_pct = normalize_similarity(similarity)
            blended = float(item["score"]) * 0.4 + float(similarity) * 0.6
        else:
            match_pct = 0
            blended = float(item["score"])
        scored.append((item, match_pct, blended))

    scored.sort(key=lambda row: row[2], reverse=True)
    total = len(scored)
    page = scored[skip : skip + limit]

    items = [
        {
            "id": news["id"],
            "headline": news.get("title") or "",
            "source": _source_label(news.get("type") or ""),
            "summary": news.get("summary") or "N/A",
            "category": _infer_category(news.get("title") or ""),
            "readTime": "5 min read",
            "score": news.get("score", 0),
            "match_percentage": match_pct,
            "featured": index < 3,
        }
        for index, (news, match_pct, _) in enumerate(page)
    ]

    logger.info("[DIGEST] Returning %s items (total=%s)", len(items), total)
    return items, total
