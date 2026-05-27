"""
Base scraper class with shared logic for deduplication and bulk inserts.
"""
import asyncio
import logging
from datetime import datetime, timedelta
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

    def _should_replace_job_deadline(
        self,
        existing_deadline: str | None,
        candidate_deadline: str | None,
    ) -> bool:
        if not candidate_deadline:
            return False
        if not existing_deadline:
            return True

        try:
            existing_dt = datetime.fromisoformat(existing_deadline)
            candidate_dt = datetime.fromisoformat(candidate_deadline)
            return candidate_dt > existing_dt
        except ValueError:
            existing_norm = existing_deadline.strip().lower()
            candidate_norm = candidate_deadline.strip().lower()
            if existing_norm == candidate_norm:
                return False
            if not existing_norm:
                return True
            if not candidate_norm:
                return False
            return len(candidate_norm) > len(existing_norm)

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
        saved_jobs: list[tuple[str, str, str, str | None]] = []  # (id, title, company, location)
        updated_job_ids: list[str] = []
        
        async with async_session() as session:
            for job_data in jobs:
                try:
                    hn_item_id = job_data.get("hn_item_id")
                    if not hn_item_id:
                        continue

                    existing_job = None
                    if hn_item_id:
                        existing = await session.execute(
                            select(Job).where(Job.hn_item_id == hn_item_id)
                        )
                        existing_job = existing.scalar_one_or_none()

                    if existing_job:
                        # BUG FIX [H5]: allow replacement when existing deadline expired or job is stale
                        deadline_expired = False
                        no_deadline_and_stale = False
                        try:
                            if existing_job.deadline:
                                try:
                                    existing_deadline_dt = datetime.fromisoformat(existing_job.deadline)
                                    if existing_deadline_dt < datetime.utcnow():
                                        deadline_expired = True
                                except Exception:
                                    # If stored deadline isn't ISO, ignore expiry check
                                    deadline_expired = False
                            else:
                                # No deadline stored; consider stale if scraped > 90 days ago
                                if existing_job.scraped_at and existing_job.scraped_at < datetime.utcnow() - timedelta(days=90):
                                    no_deadline_and_stale = True
                        except Exception:
                            deadline_expired = False
                            no_deadline_and_stale = False

                        # Determine whether to replace: expired OR stale OR candidate has later deadline
                        should_replace = (
                            deadline_expired
                            or no_deadline_and_stale
                            or self._should_replace_job_deadline(existing_job.deadline, job_data.get("deadline"))
                        )

                        if should_replace:
                            # Update fields on existing job and collect ID for embedding refresh
                            existing_job.title = job_data.get("title", "")
                            existing_job.company = job_data.get("company", "Unknown")
                            existing_job.location = job_data.get("location", "N/A")
                            existing_job.tags = job_data.get("tags", [])
                            existing_job.email_contact = job_data.get("email_contact")
                            existing_job.apply_link = job_data.get("apply_link")
                            existing_job.is_ghost_job = job_data.get("is_ghost_job", False)
                            existing_job.deadline = job_data.get("deadline")
                            existing_job.posted_at = job_data.get("posted_at", datetime.utcnow())
                            existing_job.scraped_at = datetime.utcnow()
                            # BUG FIX [H3]: schedule embedding refresh for updated records after commit
                            try:
                                updated_job_ids.append(existing_job.id)
                            except Exception:
                                pass
                        else:
                            # Existing job is still active; skip
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
                    await session.flush()
                    saved_jobs.append((job.id, job.title, job.company, job.location))
                    new_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to save job: {e}")
                    continue
            
            await session.commit()
        
        logger.info(f"Saved {new_count}/{total} new jobs")

        if saved_jobs or updated_job_ids:
            try:
                from src.services.embedding_service import embed_job_item
                loop = asyncio.get_running_loop()
                for job_id, title, company, location in saved_jobs:
                    loop.create_task(embed_job_item(job_id, title, company, location))
                # Also refresh embeddings for updated jobs (deadline replacements)
                for ujid in updated_job_ids:
                    try:
                        # Fetch minimal data for embedding; embed_job_item tolerates title/company empty but preferable to pass placeholders
                        loop.create_task(embed_job_item(ujid, "", "", ""))
                    except Exception:
                        logger.warning(f"Failed to schedule embedding refresh for updated job {ujid}")
                logger.info(f"Scheduled embedding generation for {len(saved_jobs)} job items")
            except Exception as e:
                logger.warning(f"Failed to schedule job embeddings: {e}")

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
        saved_news: list[tuple[str, str, str | None]] = []  # (id, title, summary)
        
        async with async_session() as session:
            for item_data in items:
                try:
                    hn_item_id = item_data.get("id") or item_data.get("hn_item_id")
                    if not hn_item_id:
                        continue
                    
                    # Check if already exists
                    if await self.check_exists(session, hn_item_id, News):
                        continue
                    
                    title = item_data.get("title", "")
                    summary = item_data.get("summary")
                    
                    # Create news instance
                    news = News(
                        hn_item_id=hn_item_id,
                        type=news_type,
                        title=title,
                        url=item_data.get("url"),
                        score=item_data.get("score", 0),
                        comment_count=item_data.get("descendants", 0) or item_data.get("comment_count", 0),
                        summary=summary,
                        summarized=False,
                        scraped_at=datetime.utcnow(),
                        report_version="2",
                    )
                    
                    session.add(news)
                    await session.flush()
                    saved_news.append((news.id, title, summary))
                    new_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to save news item: {e}")
                    continue
            
            await session.commit()

        logger.info(f"Saved {new_count}/{total} new {news_type} items")

        # Schedule summarization for top 20 items (fire-and-forget, non-blocking)
        if new_count > 0:
            try:
                from src.services.llm_service import summarize_top_news
                loop = asyncio.get_running_loop()
                loop.create_task(summarize_top_news(top_n=20))
                logger.info("Scheduled news summarization for top 20 items")
            except Exception as e:
                logger.warning(f"Failed to schedule summarization: {e}")

            # Schedule content embeddings for saved items (incremental)
            try:
                from src.services.embedding_service import embed_news_item
                loop = asyncio.get_running_loop()
                for news_id, title, summary in saved_news:
                    loop.create_task(embed_news_item(news_id, title, summary, news_type))
                logger.info(f"Scheduled embedding generation for {len(saved_news)} news items")
            except Exception as e:
                logger.warning(f"Failed to schedule embeddings: {e}")

        return total, new_count

