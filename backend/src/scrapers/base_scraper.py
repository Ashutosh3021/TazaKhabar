"""
Base scraper class with shared logic for deduplication and bulk inserts.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import settings
from src.db import repos

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BaseScraper:
    """Base class for all HN scrapers with shared database operations."""

    async def check_exists(self, hn_item_id: int, table: str) -> bool:
        """Check if an HN item already exists in the store."""
        if table == "jobs":
            return await repos.job_by_hn_item_id(hn_item_id) is not None
        return await repos.news_by_hn_item_id(hn_item_id) is not None

    async def record_run(
        self, name: str, status: str, collected: int = 0, new: int = 0
    ) -> None:
        """Store the outcome of a scraper run so the status endpoint can show it."""
        try:
            await repos.set_state(f"scraper:{name}:status", status)
            await repos.set_state(
                f"scraper:{name}:stats",
                json.dumps(
                    {
                        "collected": collected,
                        "new": new,
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
            )
        except Exception as exc:
            logger.warning("Could not record run state for %s: %s", name, exc)

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
            if candidate_norm == existing_norm:
                return False
            if not candidate_norm:
                return True
            if not existing_norm:
                return False
            return len(candidate_norm) > len(existing_norm)

    async def save_jobs(self, jobs: list[dict[str, Any]]) -> tuple[int, int]:
        """
        Save job listings with deduplication.

        Returns:
            Tuple of (total_processed, new_items_added).
        """
        total = len(jobs)
        new_count = 0
        existing = await repos.existing_jobs_by_hn_item_id()
        now = _utcnow()
        now_iso = now.isoformat()

        new_rows: list[dict[str, Any]] = []
        refreshed_ids: list[str] = []

        for job_data in jobs:
            try:
                hn_item_id = job_data.get("hn_item_id")
                if not hn_item_id:
                    continue

                known = existing.get(int(hn_item_id))
                if known:
                    deadline_expired = False
                    no_deadline_and_stale = False
                    existing_deadline = known.get("deadline")
                    if existing_deadline:
                        try:
                            deadline_expired = datetime.fromisoformat(
                                existing_deadline
                            ) < now
                        except ValueError:
                            deadline_expired = False
                    else:
                        scraped_at = known.get("scraped_at")
                        if scraped_at:
                            try:
                                parsed = datetime.fromisoformat(
                                    str(scraped_at).replace("Z", "+00:00")
                                )
                                if parsed.tzinfo is not None:
                                    parsed = parsed.astimezone(
                                        timezone.utc
                                    ).replace(tzinfo=None)
                                no_deadline_and_stale = parsed < now - timedelta(days=90)
                            except ValueError:
                                no_deadline_and_stale = False

                    should_replace = (
                        deadline_expired
                        or no_deadline_and_stale
                        or self._should_replace_job_deadline(
                            existing_deadline, job_data.get("deadline")
                        )
                    )
                    if not should_replace:
                        continue

                    await repos.upsert_job(
                        known["id"],
                        {
                            "hn_item_id": int(hn_item_id),
                            "title": job_data.get("title", ""),
                            "company": job_data.get("company", "Unknown"),
                            "location": job_data.get("location", "N/A"),
                            "tags": job_data.get("tags", []),
                            "email_contact": job_data.get("email_contact"),
                            "apply_link": job_data.get("apply_link"),
                            "is_ghost_job": bool(job_data.get("is_ghost_job", False)),
                            "deadline": job_data.get("deadline"),
                            "posted_at": _as_iso(job_data.get("posted_at")) or now_iso,
                            "scraped_at": now_iso,
                        },
                    )
                    refreshed_ids.append(known["id"])
                    continue

                new_rows.append(
                    {
                        "id": uuid.uuid4().hex,
                        "hn_item_id": int(hn_item_id),
                        "title": job_data.get("title", ""),
                        "company": job_data.get("company", "Unknown"),
                        "location": job_data.get("location", "N/A"),
                        "tags": job_data.get("tags", []),
                        "email_contact": job_data.get("email_contact"),
                        "apply_link": job_data.get("apply_link"),
                        "is_ghost_job": bool(job_data.get("is_ghost_job", False)),
                        "deadline": job_data.get("deadline"),
                        "posted_at": _as_iso(job_data.get("posted_at")) or now_iso,
                        "scraped_at": now_iso,
                        "processed": False,
                    }
                )
                new_count += 1
            except Exception as e:
                logger.error(f"Failed to save job: {e}")
                continue

        if new_rows:
            await repos.insert_rows("jobs", new_rows)

        logger.info(f"Saved {new_count}/{total} new jobs")

        if settings.EMBEDDINGS_ENABLED and (new_rows or refreshed_ids):
            try:
                from src.services.embedding_service import embed_job_item

                loop = asyncio.get_running_loop()
                for row in new_rows:
                    loop.create_task(
                        embed_job_item(row["id"], row["title"], row["company"], row["location"])
                    )
                for job_id in refreshed_ids:
                    loop.create_task(embed_job_item(job_id, "", "", ""))
            except Exception as e:
                logger.warning(f"Failed to schedule job embeddings: {e}")

        return total, new_count

    async def save_news(self, items: list[dict[str, Any]], news_type: str) -> tuple[int, int]:
        """
        Save news items with deduplication.

        Returns:
            Tuple of (total_processed, new_items_added).
        """
        total = len(items)
        new_count = 0
        known_ids = await repos.existing_news_hn_item_ids()
        now_iso = datetime.now(timezone.utc).isoformat()

        new_rows: list[dict[str, Any]] = []
        for item_data in items:
            try:
                hn_item_id = item_data.get("id") or item_data.get("hn_item_id")
                if not hn_item_id:
                    continue
                if int(hn_item_id) in known_ids:
                    continue

                new_rows.append(
                    {
                        "id": uuid.uuid4().hex,
                        "hn_item_id": int(hn_item_id),
                        "type": news_type,
                        "title": item_data.get("title", ""),
                        "url": item_data.get("url"),
                        "score": int(item_data.get("score", 0) or 0),
                        "comment_count": int(
                            item_data.get("descendants", 0) or item_data.get("comment_count", 0) or 0
                        ),
                        "summary": item_data.get("summary"),
                        "summarized": bool(item_data.get("summary")),
                        "scraped_at": now_iso,
                    }
                )
                new_count += 1
            except Exception as e:
                logger.error(f"Failed to save news item: {e}")
                continue

        if new_rows:
            await repos.insert_rows("news", new_rows)

        logger.info(f"Saved {new_count}/{total} new {news_type} items")

        if new_count > 0:
            try:
                from src.services.llm_service import summarize_top_news

                loop = asyncio.get_running_loop()
                loop.create_task(summarize_top_news(top_n=20))
            except Exception as e:
                logger.warning(f"Failed to schedule summarization: {e}")

            try:
                from src.services.embedding_service import embed_news_item

                if not settings.EMBEDDINGS_ENABLED:
                    raise RuntimeError("embeddings disabled")

                loop = asyncio.get_running_loop()
                for row in new_rows:
                    loop.create_task(
                        embed_news_item(row["id"], row["title"], row.get("summary"), news_type)
                    )
            except Exception as e:
                logger.warning(f"Failed to schedule embeddings: {e}")

        return total, new_count


def _as_iso(value: Any) -> str | None:
    """Normalize a timestamp into an ISO string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
