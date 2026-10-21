"""
Scraper workflow used by the GitHub Actions job and by the manual trigger.

Running the scrapers here keeps the API service stateless: the workflow does
the fetching, the Pyronites store holds the result.
"""
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def _run_scraper_with_notifications(scraper_func):
    """Run a scraper, then queue notifications for matching users."""
    from src.notifications import check_and_queue_notifications

    result = await scraper_func()

    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        queued = await check_and_queue_notifications(since)
        if queued:
            logger.info(f"Queued {queued} notifications after scraper run")
    except Exception as e:
        logger.warning(f"Notification processing failed after scraper run: {e}")
    return result


async def _who_is_hiring_job():
    from src.scrapers.who_is_hiring import WhoIsHiringScraper

    return await _run_scraper_with_notifications(WhoIsHiringScraper().run)


async def _top_stories_job():
    from src.scrapers.top_stories import TopStoriesScraper

    return await _run_scraper_with_notifications(TopStoriesScraper().run)


async def _ask_hn_job():
    from src.scrapers.ask_hn import AskHNScraper

    return await _run_scraper_with_notifications(AskHNScraper().run)


async def _show_hn_job():
    from src.scrapers.show_hn import ShowHNScraper

    return await _run_scraper_with_notifications(ShowHNScraper().run)


SCRAPER_JOBS = (
    ("who_is_hiring", _who_is_hiring_job),
    ("top_stories", _top_stories_job),
    ("ask_hn", _ask_hn_job),
    ("show_hn", _show_hn_job),
)


async def run_all_scrapers_now() -> dict[str, str]:
    """Run every HN scraper once and report the outcome per scraper."""
    logger.info("Running all scrapers...")
    results: dict[str, str] = {}
    for name, job in SCRAPER_JOBS:
        try:
            await job()
            results[name] = "ok"
        except Exception as e:
            results[name] = f"error: {e}"
            logger.exception("Scraper run failed for %s", name)
    return results


async def compute_trends_and_observation() -> str | None:
    """
    Recount keyword trends and write a fresh market observation.

    Returns:
        The observation text, or None when the LLM was rate limited.
    """
    from src.db import repos
    from src.services.llm_service import generate_observation_text
    from src.services.trend_service import compute_keyword_frequencies

    trends = await compute_keyword_frequencies()
    booming = [t["keyword"] for t in trends if t.get("percentage_change", 0) > 20]
    declining = [t["keyword"] for t in trends if t.get("percentage_change", 0) < -20]
    booming.sort(key=lambda kw: next((t["percentage_change"] for t in trends if t["keyword"] == kw), 0), reverse=True)
    declining.sort(key=lambda kw: abs(next((t["percentage_change"] for t in trends if t["keyword"] == kw), 0)), reverse=True)

    observation_text = await generate_observation_text(
        booming_keywords=booming[:10],
        declining_keywords=declining[:10],
    )
    if not observation_text:
        logger.warning("LLM rate limited or empty observation, skipping insert")
        return None

    week_end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = week_end - timedelta(days=7)
    await repos.insert_observation(observation_text, week_start.isoformat())
    return observation_text
