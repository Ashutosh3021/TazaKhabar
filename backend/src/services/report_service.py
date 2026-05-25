"""
Report cycle management service.
Handles promotion/demotion of scraped data between report versions.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job, News, Report

logger = logging.getLogger(__name__)


async def advance_report_cycle(session: AsyncSession) -> int:
    """
    Advance the report cycle after each scraper run.

    Steps:
    1. Demote all report_version="1" → "archived"
    2. Promote report_version="2" → "1"
    3. Count active items for badge since the last report swap
    4. Create new Report record
    5. Return new_count

    Returns:
        Number of new items scraped in this cycle
    """
    try:
        # Step 1: Demote existing "1" → "archived"
        await session.execute(
            update(Job).where(Job.report_version == "1").values(report_version="archived")
        )
        await session.execute(
            update(News).where(News.report_version == "1").values(report_version="archived")
        )

        # Step 2: Promote "2" → "1"
        await session.execute(
            update(Job).where(Job.report_version == "2").values(report_version="1")
        )
        await session.execute(
            update(News).where(News.report_version == "2").values(report_version="1")
        )

        # Step 3: Count active items since the last swap window if available
        last_swap = await get_last_swap_time(session)
        if last_swap:
            job_count_result = await session.execute(
                select(func.count(Job.id)).where(Job.report_version == "1")
            )
            news_count_result = await session.execute(
                select(func.count(News.id)).where(News.report_version == "1")
            )
        else:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            job_count_result = await session.execute(
                select(func.count(Job.id)).where(
                    Job.report_version == "1",
                    Job.scraped_at >= cutoff,
                )
            )
            news_count_result = await session.execute(
                select(func.count(News.id)).where(
                    News.report_version == "1",
                    News.scraped_at >= cutoff,
                )
            )
        new_count = (job_count_result.scalar() or 0) + (news_count_result.scalar() or 0)

        # Step 4: Create new Report record
        report = Report(
            version="1",
            items_collected=new_count,
            new_items=new_count,
            status="completed",
            run_at=datetime.utcnow(),
        )
        session.add(report)
        await session.commit()

        logger.info(f"Report cycle advanced: {new_count} new items")
        return new_count

    except Exception as e:
        logger.error(f"Error advancing report cycle: {e}")
        await session.rollback()
        raise


async def get_badge_counts(session: AsyncSession) -> dict:
    """
    Get badge counts for new items since last report swap.

    Returns:
        Dict with radar_new_count and feed_new_count
    """
    try:
        last_swap = await get_last_swap_time(session)
        if last_swap:
            job_stmt = select(func.count(Job.id)).where(Job.report_version == "1")
            news_stmt = select(func.count(News.id)).where(News.report_version == "1")
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
        radar_count = job_result.scalar() or 0

        news_result = await session.execute(news_stmt)
        feed_count = news_result.scalar() or 0

        return {
            "radar_new_count": radar_count,
            "feed_new_count": feed_count,
        }

    except Exception as e:
        logger.error(f"Error getting badge counts: {e}")
        return {"radar_new_count": 0, "feed_new_count": 0}


async def get_last_swap_time(session: AsyncSession) -> datetime | None:
    """
    Get the most recent report swap timestamp.
    
    Returns:
        Datetime of last swap, or None if never swapped
    """
    try:
        result = await session.execute(
            select(Report.run_at)
            .where(Report.status == "swapped")
            .order_by(Report.run_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row
    except Exception as e:
        logger.error(f"Error getting last swap time: {e}")
        return None


async def swap_reports(session: AsyncSession) -> dict:
    """
    Swap Report 2 → Report 1 and reset badge counts.
    
    FRESH-05: User triggers refresh → swap reports → badge count resets to 0
    
    Steps:
    1. Demote all report_version="1" → "archived"
    2. Promote report_version="2" → "1"
    3. Record swap in reports table
    4. Return badge counts (0 after swap)
    
    Returns:
        RefreshResponse dict with status and zero counts
    """
    try:
        # Remove stale archived items before swapping in the new report cycle
        await session.execute(delete(Job).where(Job.report_version == "archived"))
        await session.execute(delete(News).where(News.report_version == "archived"))

        # Step 1: Demote existing "1" → "archived"
        await session.execute(
            update(Job).where(Job.report_version == "1").values(report_version="archived")
        )
        await session.execute(
            update(News).where(News.report_version == "1").values(report_version="archived")
        )

        # Step 2: Promote "2" → "1"
        await session.execute(
            update(Job).where(Job.report_version == "2").values(report_version="1")
        )
        await session.execute(
            update(News).where(News.report_version == "2").values(report_version="1")
        )

        # Step 3: Create swap report record
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

        # Step 4: Return with zero counts (FRESH-05: badge resets)
        return {
            "status": "swapped",
            "radar_new_count": 0,
            "feed_new_count": 0,
        }

    except Exception as e:
        logger.error(f"Error swapping reports: {e}")
        await session.rollback()
        raise
