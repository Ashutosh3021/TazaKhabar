"""
HN Show HN scraper.
Fetches top Show HN stories and saves to news table.
"""
import logging

from ..db.database import async_session
from ..db.models import Report
from .base_scraper import BaseScraper
from .client import HNClient

logger = logging.getLogger(__name__)


class ShowHNScraper(BaseScraper):
    """
    Scraper for HN Show HN stories.
    
    Fetches top 200 Show HN story IDs and saves items to database.
    """
    
    def __init__(self):
        self.client = HNClient()
    
    async def run(self) -> dict[str, int]:
        """
        Run the Show HN scraper.
        
        Returns:
            Dict with run statistics.
        """
        logger.info("Starting Show HN scraper run")
        
        # Create report entry
        async with async_session() as session:
            report = Report(
                version="2",
                items_collected=0,
                new_items=0,
                status="running",
            )
            session.add(report)
            await session.flush()
            report_id = report.id
            await session.commit()  # Commit so other sessions can see this report
        
        try:
            # Fetch Show HN story IDs
            story_ids = await self.client.fetch_story_ids("showstories")
            
            if not story_ids:
                logger.warning("No Show HN stories found")
                return {"collected": 0, "new": 0}
            
            # Limit to top 200
            story_ids = story_ids[:200]
            logger.info(f"Fetching {len(story_ids)} Show HN stories")
            
            # Fetch stories in parallel batches
            stories = await self.client.fetch_items_batch(story_ids, semaphore=5)
            
            # Save to database
            total, new_count = await self.save_news(stories, "show_hn")
            
            # Update report
            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(Report).where(Report.id == report_id)
                result = await session.execute(stmt)
                report = result.scalar_one()
                report.items_collected = total
                report.new_items = new_count
                report.status = "completed"
                await session.commit()
            
            logger.info(f"Show HN scraper completed: {new_count} new items")
            return {"collected": total, "new": new_count}
            
        except Exception as e:
            logger.error(f"Show HN scraper failed: {e}")
            
            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(Report).where(Report.id == report_id)
                result = await session.execute(stmt)
                report = result.scalar_one_or_none()
                if report:
                    report.status = "failed"
                    await session.commit()
            
            return {"collected": 0, "new": 0}
