"""
Notification service for job match alerts.

Notifications are matched by keyword scoring between a user's profile and the
jobs scraped since the last cycle. Sending is done over SMTP when
``EMAIL_SMTP_HOST`` is configured; otherwise the notification is logged and
marked as sent (dormant mode).
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Set

from src.config import settings
from src.db import repos

logger = logging.getLogger("tazakhabar")


class NotificationService:
    """Service for managing job match notifications."""

    def __init__(self, match_threshold: int = 5):
        """
        Args:
            match_threshold: Minimum keyword matches to queue a notification.
        """
        self.match_threshold = match_threshold

    async def check_and_queue_notifications(self, since: Optional[str] = None) -> int:
        """
        Queue a notification for every user whose profile matches a recent job.

        Args:
            since: ISO timestamp; defaults to the last 24 hours.

        Returns:
            Number of notifications queued.
        """
        profiles = await repos.all_profiles()
        logger.info(f"Checking notifications for {len(profiles)} users")

        jobs = await repos.list_jobs(since=since, limit=200)
        logger.info(f"Checking {len(jobs)} recent jobs for matches")

        notifications_queued = 0
        for profile in profiles:
            keywords = self._extract_keywords(profile)
            if not keywords:
                continue

            for job in jobs:
                score = self._score_job(job, keywords)
                if score >= self.match_threshold:
                    await repos.queue_notification(profile["id"], job["id"], score)
                    notifications_queued += 1
                    logger.info(
                        f"Queued notification for user {profile['id']}: "
                        f"job {job['id']} (score={score})"
                    )

        if notifications_queued:
            logger.info(f"Queued {notifications_queued} notifications")
        return notifications_queued

    def _extract_keywords(self, profile: Dict[str, Any]) -> Set[str]:
        """Extract keywords from the user's roles and preferences."""
        keywords: Set[str] = set()

        for role in profile.get("roles") or []:
            keywords.update(self._tokenize(role))

        preferences = profile.get("preferences") or {}
        for value in preferences.values():
            if isinstance(value, str):
                keywords.update(self._tokenize(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        keywords.update(self._tokenize(item))

        return keywords

    def _tokenize(self, text: str) -> Set[str]:
        """Split text into lowercase tokens, dropping very short ones."""
        if not text:
            return set()
        tokens = text.lower().replace("/", " ").replace("-", " ").split()
        return {t.strip() for t in tokens if len(t) > 2}

    def _score_job(self, job: Dict[str, Any], keywords: Set[str]) -> int:
        """Score a job against the user's keywords."""
        score = len(self._tokenize(job.get("title") or "") & keywords)
        score += len(self._tokenize(job.get("company") or "") & keywords)
        for tag in job.get("tags") or []:
            score += len(self._tokenize(tag) & keywords)
        return score

    async def send_notification(self, notification: Dict[str, Any]) -> bool:
        """Send one notification by email when SMTP is configured."""
        body = self._format_notification_body(notification)
        logger.info(f"Sending notification: {body}")

        email = notification.get("email")
        if not email:
            return False

        if not settings.EMAIL_SMTP_HOST or not settings.EMAIL_SMTP_USER:
            logger.info("Email not configured, notification logged only: %s", notification)
            return True

        message = EmailMessage()
        message["Subject"] = f"New Job Match: {notification.get('job_title', 'N/A')}"
        message["From"] = settings.EMAIL_SMTP_USER
        message["To"] = email
        message.set_content(body)

        try:
            await asyncio.to_thread(self._send_smtp, message)
            logger.info(f"Email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _send_smtp(self, message: EmailMessage) -> None:
        with smtplib.SMTP(settings.EMAIL_SMTP_HOST, settings.EMAIL_SMTP_PORT, timeout=30) as server:
            if settings.EMAIL_SMTP_USE_TLS:
                server.starttls()
            if settings.EMAIL_SMTP_PASSWORD:
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
            server.send_message(message)

    def _format_notification_body(self, notification: Dict[str, Any]) -> str:
        """Format the notification email body."""
        return f"""
New Job Match Alert!

Position: {notification.get('job_title', 'N/A')}
Company: {notification.get('company', 'N/A')}
Location: {notification.get('location', 'N/A')}
Match Score: {notification.get('match_score', 0)}/10

Apply Link: {notification.get('apply_link', 'N/A')}

---
You received this because you have Job Match Alerts enabled.
Manage your preferences in your TazaKhabar profile.
        """.strip()

    async def process_notification_queue(self) -> int:
        """
        Send every queued notification and mark it as sent or failed.

        Returns:
            Number of notifications sent.
        """
        queued: List[Dict[str, Any]] = await repos.pending_notifications()
        logger.info(f"Processing {len(queued)} queued notifications")

        sent_count = 0
        for notification in queued:
            job = await repos.job_by_id(notification.get("job_id"))
            if not job:
                logger.warning(f"Job {notification.get('job_id')} not found for notification")
                await repos.update_notification_status(notification["id"], "failed")
                continue

            profile = await repos.get_profile(notification.get("user_id"))
            if not profile or not profile.get("email"):
                logger.warning(f"User {notification.get('user_id')} has no email")
                await repos.update_notification_status(notification["id"], "failed")
                continue

            success = await self.send_notification(
                {
                    "user_id": profile["id"],
                    "email": profile.get("email"),
                    "job_id": job["id"],
                    "job_title": job.get("title"),
                    "company": job.get("company"),
                    "location": job.get("location"),
                    "apply_link": job.get("apply_link"),
                    "match_score": notification.get("match_score"),
                }
            )

            await repos.update_notification_status(
                notification["id"], "sent" if success else "failed"
            )
            if success:
                sent_count += 1

        logger.info(f"Sent {sent_count}/{len(queued)} notifications")
        return sent_count


# Module-level service instance
notification_service = NotificationService()


async def check_and_queue_notifications(since: Optional[str] = None) -> int:
    """Queue notifications for recently scraped jobs."""
    return await notification_service.check_and_queue_notifications(since)
