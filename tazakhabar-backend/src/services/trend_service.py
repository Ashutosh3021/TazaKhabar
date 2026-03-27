"""
Trend service for keyword frequency counting and week-over-week analysis.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import async_session
from src.db.models import Job, News, Trend

logger = logging.getLogger(__name__)

# Common tech keywords to track for frequency analysis
TECH_KEYWORDS = [
    # Languages
    "react", "typescript", "python", "javascript", "golang", "rust",
    "java", "c++", "c#", "ruby", "swift", "kotlin", "scala", "php",
    # AI/ML
    "machine learning", "ai", "ml", "deep learning", "llm", "nlp",
    "generative ai", "chatgpt", "openai", "tensorflow", "pytorch",
    # Infrastructure
    "kubernetes", "docker", "devops", "sre", "cloud", "aws", "gcp", "azure",
    "terraform", "ansible", "ci/cd", "github actions", "jenkins",
    # Databases
    "postgres", "postgresql", "mongodb", "redis", "elasticsearch", "mysql",
    "dynamodb", "cassandra", "sqlite", "sql", "nosql",
    # Frontend
    "vue", "angular", "next.js", "svelte", "tailwind", "css", "html",
    "graphql", "apollo", "redux", "react native", "flutter",
    # Backend
    "node.js", "fastapi", "django", "flask", "rails", "spring",
    "express", "gin", "echo", "nestjs", "fiber",
    # Architecture
    "api", "grpc", "microservices", "backend", "frontend", "fullstack",
    "serverless", "lambda", "rest", "webhooks",
    # Work style
    "remote", "onsite", "hybrid", "startup", "senior", "junior", "principal",
    "lead", "manager", "director", "staff",
    # General tech
    "security", "blockchain", "web3", "iot", "5g", "edge computing",
]


def tokenize_text(text: str) -> set[str]:
    """
    Tokenize text into lowercase words, removing punctuation.
    
    Args:
        text: Raw text to tokenize
        
    Returns:
        Set of lowercase tokens
    """
    if not text:
        return set()
    
    # Lowercase and remove punctuation, split on whitespace
    text = text.lower()
    # Replace common punctuation with spaces
    text = re.sub(r'[/\\()\[\]{}.,;:!?\'"<>]', ' ', text)
    tokens = text.split()
    return set(tokens)


async def extract_keywords(text: str, keywords: list[str] = None) -> set[str]:
    """
    Extract matching keywords from text.
    
    Args:
        text: Text to search in
        keywords: List of keywords to match (defaults to TECH_KEYWORDS)
        
    Returns:
        Set of matched keywords
    """
    if keywords is None:
        keywords = TECH_KEYWORDS
    
    if not text:
        return set()
    
    # Normalize text and tokenize
    normalized_text = text.lower()
    tokens = tokenize_text(normalized_text)
    
    # Find matching keywords (can match multi-word phrases)
    matched = set()
    
    # Check for multi-word keywords first
    for keyword in keywords:
        if ' ' in keyword:
            if keyword in normalized_text:
                matched.add(keyword)
        elif keyword in tokens:
            matched.add(keyword)
    
    return matched


async def compute_keyword_frequencies(session: AsyncSession = None) -> list[dict[str, Any]]:
    """
    Compute keyword frequencies for the current week and calculate week-over-week change.
    
    TRND-01: Scans all job tags, titles, summaries and news titles, summaries
    TRND-02: Stores keywords in trends table with week_start and week_end
    TRND-03: Calculates week-over-week percentage change
    TRND-04: >20% growth = booming
    TRND-05: >20% decline = declining
    
    Args:
        session: Database session (creates one if not provided)
        
    Returns:
        List of trend dictionaries
    """
    should_close_session = False
    if session is None:
        session = async_session()
        should_close_session = True
    
    try:
        # Determine week boundaries
        now = datetime.utcnow()
        week_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = week_end - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start
        
        # Query all jobs and news with report_version="1"
        jobs_result = await session.execute(
            select(Job).where(Job.report_version == "1")
        )
        jobs = jobs_result.scalars().all()
        
        news_result = await session.execute(
            select(News).where(News.report_version == "1")
        )
        news_items = news_result.scalars().all()
        
        # Count keyword frequencies
        keyword_counts: dict[str, int] = {}
        
        # Process jobs
        for job in jobs:
            # Extract from title
            if job.title:
                matched = await extract_keywords(job.title)
                for kw in matched:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
            
            # Extract from tags
            if job.tags:
                tags_text = " ".join(job.tags) if isinstance(job.tags, list) else str(job.tags)
                matched = await extract_keywords(tags_text)
                for kw in matched:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
            
            # Extract from summary (if available)
            # Jobs don't have summary in model, so skip
        
        # Process news
        for news in news_items:
            # Extract from title
            if news.title:
                matched = await extract_keywords(news.title)
                for kw in matched:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
            
            # Extract from summary
            if news.summary:
                matched = await extract_keywords(news.summary)
                for kw in matched:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        # Get previous week's counts
        prev_trends_result = await session.execute(
            select(Trend).where(
                Trend.week_start == prev_week_start,
                Trend.week_end == prev_week_end,
            )
        )
        prev_trends = {t.keyword: t.count for t in prev_trends_result.scalars().all()}
        
        # Upsert current week trends
        results = []
        for keyword, count in keyword_counts.items():
            prev_count = prev_trends.get(keyword, 0)
            
            # Calculate percentage change
            if prev_count > 0:
                percentage_change = ((count - prev_count) / prev_count) * 100
            else:
                percentage_change = 100.0 if count > 0 else 0.0
            
            # Upsert into trends table
            existing = await session.execute(
                select(Trend).where(
                    Trend.keyword == keyword,
                    Trend.week_start == week_start,
                )
            )
            existing_trend = existing.scalar_one_or_none()
            
            if existing_trend:
                existing_trend.count = count
                existing_trend.percentage_change = percentage_change
            else:
                new_trend = Trend(
                    keyword=keyword,
                    count=count,
                    week_start=week_start,
                    week_end=week_end,
                    percentage_change=percentage_change,
                )
                session.add(new_trend)
            
            results.append({
                "keyword": keyword,
                "count": count,
                "percentage_change": percentage_change,
                "week_start": week_start,
                "week_end": week_end,
            })
        
        await session.commit()
        logger.info(f"Computed keyword frequencies for {len(results)} keywords")
        
        return results
        
    except Exception as e:
        logger.error(f"Error computing keyword frequencies: {e}")
        await session.rollback()
        raise
    finally:
        if should_close_session:
            await session.close()


async def get_trends(session: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
    """
    Get trending keywords with week-over-week analysis.
    
    TRND-06: Returns top 5 booming + top 3 declining keywords with percentages
    
    Args:
        session: Database session
        limit: Maximum number of trends to return (default 20)
        
    Returns:
        List of trend dictionaries with skill, percentage, weeklyChange
    """
    try:
        # Get the most recent week's trends
        now = datetime.utcnow()
        week_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = week_end - timedelta(days=7)
        
        trends_result = await session.execute(
            select(Trend).where(
                Trend.week_start == week_start,
            )
        )
        trends = trends_result.scalars().all()
        
        if not trends:
            return []
        
        # Check if we have previous week data (to determine if this is first run)
        prev_week_start = week_start - timedelta(days=7)
        has_prev_data = await session.execute(
            select(Trend).where(Trend.week_start == prev_week_start)
        )
        has_prev_data = has_prev_data.scalars().first() is not None
        
        # Separate booming and declining
        booming = [t for t in trends if t.percentage_change > 20]
        declining = [t for t in trends if t.percentage_change < -20]
        
        # If no previous data, use count-based percentages instead of change-based
        if not has_prev_data and (booming or declining):
            # Use raw counts to determine "percentage" (relative popularity)
            all_trends = list(trends)
            max_count = max((t.count for t in all_trends), default=1)
            
            # Recalculate percentages based on relative count
            for t in all_trends:
                t.percentage_change = (t.count / max_count) * 100 if max_count > 0 else 0
            
            booming = [t for t in all_trends if t.count >= max_count * 0.7]
            declining = [t for t in all_trends if t.count < max_count * 0.3]
        
        # Sort by absolute percentage change descending
        booming.sort(key=lambda t: abs(t.percentage_change), reverse=True)
        declining.sort(key=lambda t: abs(t.percentage_change), reverse=True)
        
        # Get top 5 booming, top 3 declining
        top_booming = booming[:5]
        top_declining = declining[:3]
        
        # If still no booming/declining, pick top by count
        if not top_booming:
            sorted_by_count = sorted(trends, key=lambda t: t.count, reverse=True)
            top_booming = sorted_by_count[:5]
        if not top_declining:
            sorted_by_count_asc = sorted(trends, key=lambda t: t.count, reverse=False)
            top_declining = sorted_by_count_asc[:3]
        
        # Build response
        results = []
        
        # Add booming trends
        for t in top_booming:
            results.append({
                "skill": t.keyword,
                "percentage": min(abs(t.percentage_change), 100),  # Cap at 100%
                "weeklyChange": t.percentage_change,
                "direction": "booming",
            })
        
        # Add declining trends
        for t in top_declining:
            results.append({
                "skill": t.keyword,
                "percentage": min(abs(t.percentage_change), 100),
                "weeklyChange": t.percentage_change,
                "direction": "declining",
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        return []


class TrendService:
    """
    Service class for trend operations.
    """
    
    def __init__(self):
        self.tech_keywords = TECH_KEYWORDS
    
    async def extract_keywords(self, text: str) -> set[str]:
        """Extract matching keywords from text."""
        return await extract_keywords(text, self.tech_keywords)
    
    async def compute_frequencies(self, session: AsyncSession = None) -> list[dict[str, Any]]:
        """Compute keyword frequencies for the current week."""
        return await compute_keyword_frequencies(session)
    
    async def get_trending(self, session: AsyncSession, limit: int = 20) -> list[dict[str, Any]]:
        """Get trending keywords."""
        return await get_trends(session, limit)
