"""
HN Who Is Hiring thread scraper.
Discovers threads via Algolia, parses comments for job listings.
"""
import logging
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from html import unescape

from ..db.database import async_session
from ..db.models import Report
from .base_scraper import BaseScraper
from .client import HNClient

logger = logging.getLogger(__name__)


class WhoIsHiringScraper(BaseScraper):
    """
    Scraper for HN Who Is Hiring threads.
    
    Discovers the latest Who Is Hiring thread via Algolia,
    fetches comments and parses job listings.
    """
    
    def __init__(self):
        self.client = HNClient()
        # Use an absolute path anchored to this file so it works regardless of CWD
        self._last_thread_id_file = Path(__file__).resolve().parent.parent.parent / ".last_wih_thread"
    
    def _get_last_thread_id(self) -> int | None:
        """Get the last processed Who Is Hiring thread ID."""
        try:
            return int(self._last_thread_id_file.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError, IOError):
            return None
    
    def _set_last_thread_id(self, thread_id: int) -> None:
        """Store the last processed Who Is Hiring thread ID."""
        try:
            self._last_thread_id_file.write_text(str(thread_id), encoding="utf-8")
        except IOError as e:
            logger.warning(f"Failed to save last thread ID: {e}")
    
    async def discover_thread(self) -> dict[str, Any] | None:
        """
        Discover the latest Who Is Hiring thread via Algolia.

        Searches by the known author "whoishiring" with multiple queries so we
        are not reliant on a generic "who is hiring" keyword appearing in the
        top-50 Algolia hits.

        Returns:
            Thread data dict with objectID/id, title, and author, or None if not found.
        """
        queries = [
            ("Ask HN: Who is hiring?", "story"),
            ("who is hiring", "story,author_whoishiring"),
        ]

        for query, tags in queries:
            try:
                results = await self.client.search_algolia(query=query, tags=tags)
                for hit in results:
                    author = hit.get("author", "")
                    title = hit.get("title", "")
                    if "whoishiring" in author.lower() and "hiring" in title.lower():
                        logger.info(f"Found Who Is Hiring thread: {title[:80]}")
                        return hit
            except Exception as e:
                logger.warning(f"Algolia query '{query}' failed: {e}")
                continue

        # Hard fallback: use HN Firebase jobstories endpoint which lists the
        # Who Is Hiring thread IDs directly.
        try:
            logger.info("Algolia miss — falling back to HN jobstories endpoint")
            job_ids = await self.client.fetch_story_ids("jobstories")
            if job_ids:
                # The first ID in jobstories is typically the current month's thread
                story = await self.client.fetch_item(job_ids[0])
                if story and "whoishiring" in (story.get("by") or "").lower():
                    logger.info(f"Found thread via jobstories fallback: {story.get('title', '')[:80]}")
                    return {
                        "id": story["id"],
                        "objectID": str(story["id"]),
                        "title": story.get("title", ""),
                        "author": story.get("by", ""),
                    }
        except Exception as e:
            logger.warning(f"jobstories fallback failed: {e}")

        logger.warning("No Who Is Hiring thread found in search results")
        print(">>> [WIH-SCRAPER] WARNING: No Who Is Hiring thread found!")
        return None

    def parse_comment(self, comment: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parse HN comment text to extract job information.
        
        Extracts: company, role/title, location, tags, email, apply link.
        
        Args:
            comment: Comment dict with 'text' and 'author' fields.
            
        Returns:
            Job dict with extracted data, or None if parsing fails.
        """
        try:
            # Unescape HTML entities and strip HN comment HTML formatting
            raw_text = comment.get("text", "") or ""
            # Strip HTML tags and unescape entities to plain text
            text = unescape(re.sub(r'<[^>]+>', '', raw_text))
            text = re.sub(r'\s+', ' ', text).strip()
            author = comment.get("author", "")
            
            if not text.strip():
                return None
            
            # Extract company (first line bold text or author)
            company = author  # Default to author
            
            # Try to find bold text (Markdown **text**)
            bold_match = re.search(r'\*\*(.+?)\*\*', text)
            if bold_match:
                company = bold_match.group(1).strip()
            
            # Extract title/role - look for the actual job title
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = "Unknown Position"
            
            # Skip the first few lines (company, empty, etc.)
            for i, line in enumerate(lines):
                # Skip bold lines and very short lines
                if line.startswith("**") or len(line) < 5:
                    continue
                # Skip lines that look like URLs
                if line.startswith("http") or "http" in line:
                    continue
                title = line
                break
            
            # Extract location
            location = "N/A"
            text_lower = text.lower()
            if "remote" in text_lower:
                location = "Remote"
            elif "onsite" in text_lower or "in-person" in text_lower or "in person" in text_lower:
                location = "Onsite"
            elif "hybrid" in text_lower:
                location = "Hybrid"
            
            # Extract tags from text
            tags = []
            keywords = ["senior", "junior", "intern", "contract", "full-time",
                       "part-time", "entry", "mid", "lead", "principal", "staff",
                       "frontend", "front-end", "backend", "back-end", "fullstack", "full-stack", "devops", "data", "ml", "ai",
                       "react", "python", "go", "rust", "java", "typescript", "node", "postgresql", "aws", "gcp", "azure",
                       "machine learning", "nlp", "llm", "gpt", "tensorflow", "pytorch"]
            text_lower_kw = text.lower()
            for keyword in keywords:
                if keyword in text_lower_kw:
                    tags.append(keyword)
            
            # Extract email contact
            email = None
            email_patterns = [
                r'[\w.+-]+@[\w-]+\.[\w.-]+',  # Standard email
                r'([\w.+-]+)\s+at\s+([\w-]+)\s+dot\s+([\w.-]+)',  # Obfuscated
                r'([\w.+-]+)\s*@\s*([\w.-]+)',  # @ symbol with spaces
            ]
            
            for pattern in email_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    email = match.group(0)
                    break
            
            # Extract apply link
            apply_link = None
            apply_patterns = [
                r'(https?://[^\s<>"\']+)',
                r'(?:apply at|application|apply|contact)[:\s]+(https?://[^\s<>"\']+)',
            ]
            
            for pattern in apply_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    apply_link = match.group(1) if match.lastindex else match.group(0)
                    break
            
            # Extract deadline (e.g., "deadline: 2024-01-15" or "apply by")
            deadline = None
            deadline_pattern = r'(?:deadline|apply by|closes?)[:\s]*(\d{4}-\d{2}-\d{2})'
            deadline_match = re.search(deadline_pattern, text, re.IGNORECASE)
            if deadline_match:
                deadline = deadline_match.group(1)
            
            # Get HN item ID
            hn_item_id = comment.get("id")

            # Posted time and reply count (kids)
            timestamp = comment.get("time")
            reply_count = len(comment.get("kids", [])) if comment.get("kids") else 0

            # Heuristic ghost job detection
            def _is_ghost_job(txt: str, ts: int | None, replies: int) -> bool:
                """Return True if job likely ghost/expired using heuristics."""
                txt_lower = (txt or "").lower()
                phrases = ["position filled", "no longer hiring", "role closed", "hiring paused", "application closed"]
                if any(p in txt_lower for p in phrases):
                    return True

                # If timestamp present and older than 90 days and no replies
                if ts:
                    try:
                        age_days = (datetime.utcnow() - datetime.fromtimestamp(int(ts))).days
                        if age_days > 90 and replies == 0:
                            return True
                    except Exception:
                        pass

                return False

            is_ghost_job = _is_ghost_job(text, timestamp, reply_count)

            posted_at = datetime.utcnow()
            if timestamp:
                try:
                    posted_at = datetime.fromtimestamp(int(timestamp))
                except Exception:
                    posted_at = datetime.utcnow()

            job_dict = {
                "hn_item_id": int(hn_item_id) if hn_item_id else 0,
                "title": title,
                "company": company,
                "location": location,
                "tags": tags,
                "email_contact": email,
                "apply_link": apply_link,
                "is_ghost_job": is_ghost_job,
                "deadline": deadline,
                "posted_at": posted_at,
            }

            # BUG FIX [H1]: compute ghost job heuristics (age/replies/phrases)
            # BUG FIX [C3]: strip HTML from comment text before storing
            return job_dict
            
        except Exception as e:
            logger.error(f"Failed to parse comment: {e}")
            return None
    
    async def run(self) -> dict[str, int]:
        """
        Run the Who Is Hiring scraper.
        
        Discovers thread, fetches comments, parses jobs, and saves to database.
        
        Returns:
            Dict with run statistics.
        """
        print("\n" + "-" * 50)
        print(">>> [WIH-SCRAPER] Starting Who Is Hiring scraper run")
        logger.info("Starting Who Is Hiring scraper run")

        # Create report entry
        async with async_session() as session:
            report = Report(
                version="2",
                items_collected=0,
                new_items=0,
                status="running",
                scraper_name="who_is_hiring",
            )
            session.add(report)
            await session.commit()
            report_id = report.id

        try:
            # Discover latest thread
            print(">>> [WIH-SCRAPER] Step 1: Discovering Who Is Hiring thread via Algolia...")
            thread = await self.discover_thread()
            if not thread:
                print(">>> [WIH-SCRAPER] ERROR: No thread discovered. Check Algolia API key and internet connection.")
                logger.warning("No Who Is Hiring thread found")
                async with async_session() as session:
                    from sqlalchemy import select as _select
                    r = (await session.execute(_select(Report).where(Report.id == report_id))).scalar_one_or_none()
                    if r:
                        r.status = "failed"
                        await session.commit()
                return {"collected": 0, "new": 0}

            thread_id = thread.get("id") or thread.get("objectID")
            thread_title = thread.get("title", "Unknown")[:60]
            print(f">>> [WIH-SCRAPER] Found thread ID={thread_id}: '{thread_title}'")

            if not thread_id:
                print(f">>> [WIH-SCRAPER] ERROR: Thread has no ID field!")
                logger.error("Thread has no ID")
                async with async_session() as session:
                    from sqlalchemy import select as _select
                    r = (await session.execute(_select(Report).where(Report.id == report_id))).scalar_one_or_none()
                    if r:
                        r.status = "failed"
                        await session.commit()
                return {"collected": 0, "new": 0}

            # Check if this is a new thread
            last_thread_id = self._get_last_thread_id()
            if last_thread_id == int(thread_id):
                print(f">>> [WIH-SCRAPER] Thread {thread_id} already processed (last run), skipping.")
                logger.info(f"Thread {thread_id} already processed, skipping")
                async with async_session() as session:
                    from sqlalchemy import select as _select
                    r = (await session.execute(_select(Report).where(Report.id == report_id))).scalar_one_or_none()
                    if r:
                        r.status = "completed"
                        r.items_collected = 0
                        await session.commit()
                return {"collected": 0, "new": 0}
            else:
                print(f">>> [WIH-SCRAPER] New thread detected! Last: {last_thread_id}, Current: {thread_id}")

            # Fetch comments via Firebase API
            print(f">>> [WIH-SCRAPER] Step 2: Fetching comments for thread {thread_id} via Firebase...")

            # First get the story to find kids (comment IDs)
            story = await self.client.fetch_item(int(thread_id))
            if not story:
                print(f">>> [WIH-SCRAPER] ERROR: Could not fetch story {thread_id}")
                return {"collected": 0, "new": 0}

            # Get all top-level comment IDs from the story
            comment_ids = story.get("kids", [])
            print(f">>> [WIH-SCRAPER] Found {len(comment_ids)} comment IDs in story")

            # Fetch all comments and all descendants (full tree) in parallel
            # BUG FIX [H2]: fetch entire comment tree (no 100-item cap), with concurrency semaphore
            comments = []
            if comment_ids:
                to_fetch = list(comment_ids)
                fetched_ids = set()
                sem = 20
                while to_fetch:
                    batch_ids = to_fetch
                    to_fetch = []
                    fetched = await self.client.fetch_items_batch(batch_ids, semaphore=sem)
                    valid = [c for c in fetched if c and c.get("text")]
                    comments.extend(valid)
                    for item in fetched:
                        if not item:
                            continue
                        kids = item.get("kids", []) or []
                        for k in kids:
                            if k not in fetched_ids:
                                to_fetch.append(k)
                                fetched_ids.add(k)
                print(f">>> [WIH-SCRAPER] Fetched {len(comments)} valid comments (including descendants)")
            else:
                print(f">>> [WIH-SCRAPER] No comments found in story")

            # Parse comments into jobs
            print(f">>> [WIH-SCRAPER] Step 3: Parsing {len(comments)} comments into job listings...")
            jobs = []
            parse_errors = 0
            for comment in comments:
                try:
                    job = self.parse_comment(comment)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    parse_errors += 1

            # Deduplicate by company + title
            seen = set()
            unique_jobs = []
            for job in jobs:
                key = (job["company"].lower(), job["title"].lower())
                if key not in seen:
                    seen.add(key)
                    unique_jobs.append(job)

            print(f">>> [WIH-SCRAPER] Parsed: {len(jobs)} raw jobs -> {len(unique_jobs)} unique (after dedup)")
            if parse_errors > 0:
                print(f">>> [WIH-SCRAPER] Parse errors: {parse_errors}")
            logger.info(f"Parsed {len(unique_jobs)} unique jobs from {len(comments)} comments")

            # Save to database
            print(f">>> [WIH-SCRAPER] Step 4: Saving {len(unique_jobs)} jobs to database...")
            try:
                total, new_count = await self.save_jobs(unique_jobs)
                print(f">>> [WIH-SCRAPER] Database save complete: {new_count} NEW jobs, {total} total")
            except Exception as e:
                print(f">>> [WIH-SCRAPER] DATABASE ERROR: {e}")
                raise

            # Update report
            self._set_last_thread_id(int(thread_id))

            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(Report).where(Report.id == report_id)
                result = await session.execute(stmt)
                report = result.scalar_one_or_none()
                if report:
                    report.items_collected = total
                    report.new_items = new_count
                    report.status = "completed"
                    await session.commit()
                else:
                    logger.warning(f"Could not find report {report_id} to update")

            print(f">>> [WIH-SCRAPER] SUCCESS: {new_count} new jobs saved!")
            print(">>> [WIH-SCRAPER] Scraper run completed successfully")
            print("-" * 50 + "\n")
            logger.info(f"Who Is Hiring scraper completed: {new_count} new jobs")
            return {"collected": total, "new": new_count}

        except Exception as e:
            print(f">>> [WIH-SCRAPER] ERROR: Scraper failed with exception: {e}")
            print(f">>> [WIH-SCRAPER] ERROR TYPE: {type(e).__name__}")
            import traceback
            print(f">>> [WIH-SCRAPER] TRACE: {traceback.format_exc()}")
            logger.error(f"Who Is Hiring scraper failed: {e}")

            async with async_session() as session:
                from sqlalchemy import select
                stmt = select(Report).where(Report.id == report_id)
                result = await session.execute(stmt)
                report = result.scalar_one_or_none()
                if report:
                    report.status = "failed"
                    await session.commit()
                else:
                    logger.warning(f"Could not find report {report_id} to update status to failed")

            return {"collected": 0, "new": 0}
