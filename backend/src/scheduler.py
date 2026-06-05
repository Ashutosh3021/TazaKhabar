"""
APScheduler integration for HN scrapers.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone="UTC")


async def _compute_trends_with_observation():
    """
    Compute keyword frequencies and generate market observation.
    Called daily at midnight UTC by the scheduler.
    """
    from src.db.database import async_session
    from src.db.models import Observation

    print(">>> [JOB] Starting trends computation + observation generation...")

    async with async_session() as session:
        # Step 1: Compute keyword frequencies
        from src.services.trend_service import compute_keyword_frequencies
        trends = await compute_keyword_frequencies(session)

        # Step 2: Extract booming and declining keywords
        booming = [t["keyword"] for t in trends if t.get("percentage_change", 0) > 20]
        declining = [t["keyword"] for t in trends if t.get("percentage_change", 0) < -20]
        booming.sort(key=lambda kw: next((t["percentage_change"] for t in trends if t["keyword"] == kw), 0), reverse=True)
        declining.sort(key=lambda kw: abs(next((t["percentage_change"] for t in trends if t["keyword"] == kw), 0)), reverse=True)

        print(f">>> [JOB] Trends: {len(booming)} booming, {len(declining)} declining keywords")

        # Step 3: Generate observation text
        from src.services.llm_service import generate_observation_text
        observation_text = await generate_observation_text(
            booming_keywords=booming[:10],
            declining_keywords=declining[:10],
        )

        # BUG FIX [M7]: guard against None observation (LLM rate-limited) before inserting
        if not observation_text:
            logger.warning("LLM rate-limited or returned None — skipping Observation insert this cycle")
            return

        # Step 4: Save to Observation table
        from datetime import datetime, timedelta
        week_end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = week_end - timedelta(days=7)

        observation = Observation(
            week_start=week_start,
            text=observation_text,
            generated_at=datetime.utcnow(),
        )
        session.add(observation)
        await session.commit()

        print(f">>> [JOB] Generated market observation for week of {week_start.date()}: {observation_text[:80]}...")


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
        try:
            queued = await check_and_queue_notifications(session)
            if queued > 0:
                logger.info(f"Queued {queued} notifications after scraper run")
        except Exception as e:
            logger.warning(f"Notification processing failed after scraper run: {e}")
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


async def _backfill_embeddings_job():
    """Daily embeddings backfill job."""
    from src.services.embedding_service import backfill_missing_embeddings
    from src.db.database import async_session

    print('>>> [JOB] Running daily embeddings backfill...')
    async with async_session() as session:
        try:
            result = await backfill_missing_embeddings(session)
            print(f">>> [JOB] Embeddings backfill completed: {result}")
        except Exception as e:
            print(f">>> [JOB] Embeddings backfill failed: {e}")


def start_scheduler() -> None:
    """Start the APScheduler with all configured jobs.

    Render free-tier note
    ---------------------
    The instance is kept alive by a 14-minute keep-alive ping, but every cold
    start resets the scheduler.  Using a pure CronTrigger(hour="*/2") would
    mean scrapers only fire at exact hour boundaries — potentially waiting up
    to 2 hours after a restart with no data collected.

    Fix: use IntervalTrigger(hours=2) so each scraper fires 2 hours after the
    *last run*, not at a fixed wall-clock hour.  We also schedule a one-shot
    startup run (30-second delay) so fresh data is collected immediately after
    every cold start, without hammering the HN API on the same second as boot.
    """
    from datetime import datetime, timedelta, timezone
    from apscheduler.triggers.interval import IntervalTrigger

    print("\n>>> [SCHEDULER] Registering scraper jobs...")

    now_utc = datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Stagger the one-shot startup runs so they don't all hit HN at once. #
    # Who Is Hiring is heaviest — give it a 60 s head-start window.       #
    # ------------------------------------------------------------------ #
    startup_offsets = {
        "who_is_hiring": 30,
        "top_stories":   90,
        "ask_hn":        150,
        "show_hn":       210,
    }

    scraper_jobs = [
        ("who_is_hiring", "Who Is Hiring Scraper",  _who_is_hiring_job),
        ("top_stories",   "Top Stories Scraper",    _top_stories_job),
        ("ask_hn",        "Ask HN Scraper",          _ask_hn_job),
        ("show_hn",       "Show HN Scraper",         _show_hn_job),
    ]

    for job_id, job_name, job_func in scraper_jobs:
        offset_s = startup_offsets[job_id]

        # Recurring: every 2 hours from first run
        scheduler.add_job(
            job_func,
            trigger=IntervalTrigger(hours=2, start_date=now_utc + timedelta(seconds=offset_s)),
            id=job_id,
            name=job_name,
            replace_existing=True,
        )
        print(f"    + [{job_id}] {job_name} -> first run in {offset_s}s, then every 2h")

    # Trend computation + observation: daily at midnight UTC (kept as cron — once a day is fine)
    scheduler.add_job(
        _compute_trends_with_observation,
        trigger=CronTrigger(hour="0"),
        id="compute_trends",
        name="Trends + Market Observation",
        replace_existing=True,
    )
    print("    + [compute_trends] Trends + Observation -> daily at midnight UTC")

    if settings.EMBEDDINGS_ENABLED:
        scheduler.add_job(
            _backfill_embeddings_job,
            trigger=CronTrigger(hour="3"),
            id="embeddings_backfill",
            name="Embeddings Backfill",
            replace_existing=True,
        )
        print("    + [embeddings_backfill] Embeddings Backfill -> daily at 03:00 UTC")
    else:
        print("    - [SKIP] Embeddings Backfill disabled (EMBEDDINGS_ENABLED=false)")

    scheduler.start()
    job_count = len(scheduler.get_jobs())
    print(f">>> [SCHEDULER] Started with {job_count} jobs registered")
    print(f">>> [SCHEDULER] Next run times:")
    for job in scheduler.get_jobs():
        print(f"    - {job.id}: {job.next_run_time}")


async def run_all_scrapers_now() -> dict[str, str]:
    """
    Run all HN scrapers immediately (same jobs as the 2-hour schedule).
    Useful for manual refresh during development.
    """
    print(">>> [SCRAPE] Manual run: all scrapers starting...")
    results: dict[str, str] = {}
    for name, job in (
        ("who_is_hiring", _who_is_hiring_job),
        ("top_stories", _top_stories_job),
        ("ask_hn", _ask_hn_job),
        ("show_hn", _show_hn_job),
    ):
        try:
            await job()
            results[name] = "ok"
            print(f">>> [SCRAPE] {name}: ok")
        except Exception as e:
            results[name] = f"error: {e}"
            logger.exception("Manual scraper run failed for %s", name)
    print(">>> [SCRAPE] Manual run complete")
    return results


def stop_scheduler() -> None:
    """Gracefully shutdown the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("APScheduler shutdown complete")
