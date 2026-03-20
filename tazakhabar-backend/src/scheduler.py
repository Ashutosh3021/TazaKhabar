"""
APScheduler integration for HN scrapers.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    """Start the APScheduler with all configured jobs."""
    # Import scrapers here to avoid circular imports
    from .scrapers.top_stories import TopStoriesScraper
    from .scrapers.ask_hn import AskHNScraper
    from .scrapers.show_hn import ShowHNScraper
    from .scrapers.who_is_hiring import WhoIsHiringScraper
    
    # Who Is Hiring: every 2 hours
    scheduler.add_job(
        WhoIsHiringScraper().run,
        trigger=CronTrigger(hour="*/2"),
        id="who_is_hiring",
        name="Who Is Hiring Scraper",
        replace_existing=True,
    )
    
    # Top Stories: every 2 hours
    scheduler.add_job(
        TopStoriesScraper().run,
        trigger=CronTrigger(hour="*/2"),
        id="top_stories",
        name="Top Stories Scraper",
        replace_existing=True,
    )
    
    # Ask HN: every 4 hours
    scheduler.add_job(
        AskHNScraper().run,
        trigger=CronTrigger(hour="*/4"),
        id="ask_hn",
        name="Ask HN Scraper",
        replace_existing=True,
    )
    
    # Show HN: every 6 hours
    scheduler.add_job(
        ShowHNScraper().run,
        trigger=CronTrigger(hour="*/6"),
        id="show_hn",
        name="Show HN Scraper",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("APScheduler shutdown complete")
