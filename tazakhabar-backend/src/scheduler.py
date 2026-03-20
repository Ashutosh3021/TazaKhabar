"""
APScheduler integration for HN scrapers.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")


async def _run_scraper_with_notifications(scraper_func):
    """
    Wrapper to run a scraper and then process notifications.
    
    After each scraper run, check for matching users and queue notifications.
    Then process the notification queue.
    """
    from src.db.database import async_session
    from src.notifications import check_and_queue_notifications
    
    result = await scraper_func()
    
    async with async_session() as session:
        queued = await check_and_queue_notifications(session)
        if queued > 0:
            logger.info(f"Queued {queued} notifications after scraper run")
    
    return result


async def _who_is_hiring_job():
    """Who Is Hiring scraper wrapped with notification processing."""
    from .scrapers.who_is_hiring import WhoIsHiringScraper
    return await _run_scraper_with_notifications(WhoIsHiringScraper().run)


async def _top_stories_job():
    """Top Stories scraper wrapped with notification processing."""
    from .scrapers.top_stories import TopStoriesScraper
    return await _run_scraper_with_notifications(TopStoriesScraper().run)


async def _ask_hn_job():
    """Ask HN scraper wrapped with notification processing."""
    from .scrapers.ask_hn import AskHNScraper
    return await _run_scraper_with_notifications(AskHNScraper().run)


async def _show_hn_job():
    """Show HN scraper wrapped with notification processing."""
    from .scrapers.show_hn import ShowHNScraper
    return await _run_scraper_with_notifications(ShowHNScraper().run)


def start_scheduler() -> None:
    """Start the APScheduler with all configured jobs."""
    print("\n>>> [SCHEDULER] Registering scraper jobs...")
    
    # Who Is Hiring: every 2 hours
    scheduler.add_job(
        _who_is_hiring_job,
        trigger=CronTrigger(hour="*/2"),
        id="who_is_hiring",
        name="Who Is Hiring Scraper",
        replace_existing=True,
    )
    print("    + [JOB-1] Who Is Hiring -> runs every 2 hours (Algolia)")
    
    # Trend computation: every 24 hours (weekly keyword frequency analysis)
    from .services.trend_service import compute_keyword_frequencies as _compute_trends
    scheduler.add_job(
        _compute_trends,
        trigger=CronTrigger(hour="0"),  # Run at midnight UTC
        id="compute_trends",
        name="Keyword Frequency Computation",
        replace_existing=True,
    )
    print("    + [JOB-2] Trends Computation -> runs daily at midnight UTC")
    
    # Top Stories: every 2 hours
    scheduler.add_job(
        _top_stories_job,
        trigger=CronTrigger(hour="*/2"),
        id="top_stories",
        name="Top Stories Scraper",
        replace_existing=True,
    )
    print("    + [JOB-3] Top Stories -> runs every 2 hours (Firebase)")
    
    # Ask HN: every 4 hours
    scheduler.add_job(
        _ask_hn_job,
        trigger=CronTrigger(hour="*/4"),
        id="ask_hn",
        name="Ask HN Scraper",
        replace_existing=True,
    )
    print("    + [JOB-4] Ask HN -> runs every 4 hours (Firebase)")
    
    # Show HN: every 6 hours
    scheduler.add_job(
        _show_hn_job,
        trigger=CronTrigger(hour="*/6"),
        id="show_hn",
        name="Show HN Scraper",
        replace_existing=True,
    )
    print("    + [JOB-5] Show HN -> runs every 6 hours (Firebase)")
    
    scheduler.start()
    job_count = len(scheduler.get_jobs())
    print(f">>> [SCHEDULER] Started with {job_count} jobs registered")
    print(f">>> [SCHEDULER] Next run times:")
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        print(f"    - {job.id}: {next_run}")


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("APScheduler shutdown complete")
