"""
Report cycle management service.
Handles promotion/demotion of scraped data between report versions.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job, News, Report

logger = logging.getLogger(__name__)

_swap_lock = asyncio.Lock()


async def advance_report_cycle(session: AsyncSession) -> dict:
    """
    Advance the report cycle after a refresh trigger.

    Steps:
    1. Demote report_version="1" → "archived"
    2. Promote report_version="2" → "1"
    3. Purge archived items older than 7 days
    4. Record swap event in reports table
    5. Return new job and news counts after badge reset
    """
    async with _swap_lock:
        try:
            # BUG FIX [M5]: protect report swaps from concurrent refresh calls
            await session.execute(
                update(Job).where(Job.report_version == "1").values(report_version="archived")
            )
            await session.execute(
                update(News).where(News.report_version == "1").values(report_version="archived")
            )

            await session.execute(
                update(Job).where(Job.report_version == "2").values(report_version="1")
            )
            await session.execute(
                update(News).where(News.report_version == "2").values(report_version="1")
            )

            cutoff = datetime.utcnow() - timedelta(days=7)
            await session.execute(
                delete(Job).where(
                    Job.report_version == "archived",
                    Job.scraped_at < cutoff,
                )
            )
            await session.execute(
                delete(News).where(
                    News.report_version == "archived",
                    News.scraped_at < cutoff,
                )
            )

            report = Report(
                version="1",
                items_collected=0,
                new_items=0,
                status="swapped",
                run_at=datetime.utcnow(),
            )
            session.add(report)
            await session.commit()

            logger.info("Report swap completed: Report 2 -> Report 1")
            return {"status": "swapped", "new_jobs": 0, "new_news": 0}

        except Exception as e:
            logger.error(f"Error advancing report cycle: {e}")
            await session.rollback()
            raise


async def _get_active_report(session: AsyncSession) -> Report | None:
    try:
        result = await session.execute(
            select(Report)
            .where(Report.version == "1")
            .order_by(Report.run_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error fetching active report: {e}")
        return None


async def get_badge_counts(session: AsyncSession) -> dict:
    """
    Get badge counts for new items since last report swap.

    Returns:
        Dict with new_jobs and new_news
    """
    try:
        active_report = await _get_active_report(session)
        if active_report:
            since = getattr(active_report, "swapped_at", None) or active_report.run_at
            job_stmt = select(func.count(Job.id)).where(
                Job.report_version == "1",
                Job.scraped_at >= since,
            )
            news_stmt = select(func.count(News.id)).where(
                News.report_version == "1",
                News.scraped_at >= since,
            )
        else:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            job_stmt = select(func.count(Job.id)).where(
                Job.report_version == "1",
                Job.scraped_at >= cutoff,
            )
            news_stmt = select(func.count(News.id)).where(
                News.report_version == "1",
                News.scraped_at >= cutoff,
            )

        job_result = await session.execute(job_stmt)
        new_jobs = job_result.scalar() or 0

        news_result = await session.execute(news_stmt)
        new_news = news_result.scalar() or 0

        return {
            "new_jobs": new_jobs,
            "new_news": new_news,
        }

    except Exception as e:
        logger.error(f"Error getting badge counts: {e}")
        return {"new_jobs": 0, "new_news": 0}
