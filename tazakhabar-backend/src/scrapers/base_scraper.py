"""
Base scraper class with shared logic for deduplication and bulk inserts.
"""
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import async_session
from ..db.models import Job, News

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base class for all HN scrapers with shared database operations."""
    
    async def check_exists(self, session: AsyncSession, hn_item_id: int, model_class: type) -> bool:
        """
        Check if an HN item already exists in the database.
        
        Args:
            session: Database session.
            hn_item_id: HN item ID to check.
            model_class: Model class (Job or News).
            
        Returns:
            True if item exists, False otherwise.
        """
        stmt = select(model_class).where(model_class.hn_item_id == hn_item_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    async def save_jobs(self, jobs: list[dict[str, Any]]) -> tuple[int, int]:
        """
        Save job listings to database with deduplication.
        
        Args:
            jobs: List of job dicts with HN item data.
            
        Returns:
            Tuple of (total_processed, new_items_added).
        """
        total = len(jobs)
        new_count = 0
        
        async with async_session() as session:
            for job_data in jobs:
                try:
                    hn_item_id = job_data.get("hn_item_id")
                    if not hn_item_id:
                        continue
                    
                    # Check if already exists
                    if await self.check_exists(session, hn_item_id, Job):
                        continue
                    
                    # Create job instance
                    job = Job(
                        hn_item_id=hn_item_id,
                        title=job_data.get("title", ""),
                        company=job_data.get("company", "Unknown"),
                        location=job_data.get("location", "N/A"),
                        tags=job_data.get("tags", []),
                        email_contact=job_data.get("email_contact"),
                        apply_link=job_data.get("apply_link"),
                        is_ghost_job=job_data.get("is_ghost_job", False),
                        deadline=job_data.get("deadline"),
                        posted_at=job_data.get("posted_at", datetime.utcnow()),
                        scraped_at=datetime.utcnow(),
                        report_version="2",
                    )
                    
                    session.add(job)
                    new_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to save job: {e}")
                    continue
            
            await session.commit()
        
        logger.info(f"Saved {new_count}/{total} new jobs")
        return total, new_count
    
    async def save_news(self, items: list[dict[str, Any]], news_type: str) -> tuple[int, int]:
        """
        Save news items to database with deduplication.
        
        Args:
            items: List of news dicts with HN item data.
            news_type: Type of news ('ask_hn', 'show_hn', 'top_story').
            
        Returns:
            Tuple of (total_processed, new_items_added).
        """
        total = len(items)
        new_count = 0
        
        async with async_session() as session:
            for item_data in items:
                try:
                    hn_item_id = item_data.get("id") or item_data.get("hn_item_id")
                    if not hn_item_id:
                        continue
                    
                    # Check if already exists
                    if await self.check_exists(session, hn_item_id, News):
                        continue
                    
                    # Create news instance
                    news = News(
                        hn_item_id=hn_item_id,
                        type=news_type,
                        title=item_data.get("title", ""),
                        url=item_data.get("url"),
                        score=item_data.get("score", 0),
                        comment_count=item_data.get("descendants", 0) or item_data.get("comment_count", 0),
                        summary=item_data.get("summary"),
                        summarized=False,
                        scraped_at=datetime.utcnow(),
                        report_version="2",
                    )
                    
                    session.add(news)
                    new_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to save news item: {e}")
                    continue
            
            await session.commit()
        
        logger.info(f"Saved {new_count}/{total} new {news_type} items")
        return total, new_count
