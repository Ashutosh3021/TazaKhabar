"""
HN Top Stories scraper.
Fetches top HN stories with score > 100 and saves to news table.
"""
import logging

from ..db.database import async_session
from ..db.models import Report
from .base_scraper import BaseScraper
from .client import HNClient

logger = logging.getLogger(__name__)


class TopStoriesScraper(BaseScraper):
    """
    Scraper for HN Top Stories.
    
    Fetches top 30 stories with score > 100 and saves items to database.
    """
    
    def __init__(self):
        self.client = HNClient()
        self.score_threshold = 100
    
    async def run(self) -> dict[str, int]:
        """
        Run the Top Stories scraper.
        
        Returns:
            Dict with run statistics.
        """
        logger.info("Starting Top Stories scraper run")
        print("\n" + "-" * 50)
        print(">>> [TOP-STORIES] Starting Top Stories scraper run")
        
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
            # Fetch Top Stories IDs
            story_ids = await self.client.fetch_story_ids("topstories")
            
            if not story_ids:
                print(">>> [TOP-STORIES] ERROR: No story IDs returned from HN Firebase API!")
                logger.warning("No top stories found")
                return {"collected": 0, "new": 0}
            
            # Limit to top 30
            story_ids = story_ids[:30]
            print(f">>> [TOP-STORIES] Fetching top {len(story_ids)} story IDs...")
            logger.info(f"Fetching {len(story_ids)} top stories")
            
            # Fetch stories in parallel batches
            print(f">>> [TOP-STORIES] Fetching {len(story_ids)} story details (parallel)...")
            stories = await self.client.fetch_items_batch(story_ids, semaphore=3)
            print(f">>> [TOP-STORIES] Fetched {len(stories)} stories")
            
            # Filter for stories with score > threshold
            filtered_stories = [
                s for s in stories 
                if s.get("score", 0) >= self.score_threshold
            ]
            
            print(f">>> [TOP-STORIES] Filtered to {len(filtered_stories)} stories with score >= {self.score_threshold}")
            logger.info(f"Filtered to {len(filtered_stories)} stories with score >= {self.score_threshold}")
            
            # Save to database
            print(f">>> [TOP-STORIES] Saving {len(filtered_stories)} stories to database...")
            total, new_count = await self.save_news(filtered_stories, "top_story")
            print(f">>> [TOP-STORIES] SUCCESS: {new_count} NEW items saved!")
            
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
            
            print(">>> [TOP-STORIES] Scraper run completed successfully")
            print("-" * 50 + "\n")
            logger.info(f"Top Stories scraper completed: {new_count} new items")
            return {"collected": total, "new": new_count}
            
        except Exception as e:
            print(f">>> [TOP-STORIES] ERROR: {e}")
            import traceback
            print(f">>> [TOP-STORIES] TRACE: {traceback.format_exc()}")
            logger.error(f"Top Stories scraper failed: {e}")
            
            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(Report).where(Report.id == report_id)
                result = await session.execute(stmt)
                report = result.scalar_one_or_none()
                if report:
                    report.status = "failed"
                    await session.commit()
            
            return {"collected": 0, "new": 0}
