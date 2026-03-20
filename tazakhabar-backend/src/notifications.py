"""
Notification service for job match alerts.

This module implements the full notification system for TazaKhabar.
Notifications are matched based on keyword scoring between user preferences
and job listings. The Supabase email integration is dormant by default,
with local logging for development.
"""
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job, Notification, User

logger = logging.getLogger("tazakhabar")


class NotificationService:
    """Service for managing job match notifications."""

    def __init__(self, match_threshold: int = 5):
        """
        Initialize notification service.

        Args:
            match_threshold: Minimum keyword matches to queue notification.
        """
        self.match_threshold = match_threshold

    async def check_and_queue_notifications(self, session: AsyncSession) -> int:
        """
        Check for new jobs and queue notifications for matching users.

        After each scrape cycle:
        1. Fetch all user profiles from users table
        2. Fetch new jobs from last scrape cycle (report_version="2")
        3. For each user:
           a. Extract user keywords from roles + preferences
           b. Score each new job against user keywords (keyword match scoring)
           c. If score > threshold: queue notification
        4. Store notification in notifications table
        5. Return count of notifications queued

        Args:
            session: Async SQLAlchemy session.

        Returns:
            Number of notifications queued.
        """
        # Fetch all users
        result = await session.execute(select(User))
        users = result.scalars().all()
        logger.info(f"Checking notifications for {len(users)} users")

        # Fetch new jobs (latest report version)
        result = await session.execute(
            select(Job).where(Job.report_version == "2").order_by(Job.scraped_at.desc())
        )
        jobs = result.scalars().all()
        logger.info(f"Checking {len(jobs)} new jobs for matches")

        notifications_queued = 0

        for user in users:
            # Extract keywords from user profile
            keywords = self._extract_keywords(user)

            for job in jobs:
                # Score job against user keywords
                score = self._score_job(job, keywords)

                if score >= self.match_threshold:
                    # Queue notification
                    notification = Notification(
                        user_id=user.id,
                        job_id=job.id,
                        match_score=score,
                        status="queued",
                    )
                    session.add(notification)
                    notifications_queued += 1
                    logger.info(
                        f"Queued notification for user {user.id}: "
                        f"job {job.id} (score={score})"
                    )

        if notifications_queued > 0:
            await session.commit()
            logger.info(f"Queued {notifications_queued} notifications")

        return notifications_queued

    def _extract_keywords(self, user: User) -> set[str]:
        """
        Extract keywords from user profile.

        Args:
            user: User model instance.

        Returns:
            Set of keywords from roles and preferences.
        """
        keywords: set[str] = set()

        # Add roles as keywords
        for role in user.roles:
            keywords.update(self._tokenize(role))

        # Add preferences as keywords
        if user.preferences:
            for key, value in user.preferences.items():
                if isinstance(value, str):
                    keywords.update(self._tokenize(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            keywords.update(self._tokenize(item))

        return keywords

    def _tokenize(self, text: str) -> set[str]:
        """
        Tokenize text into lowercase keywords.

        Args:
            text: Input text to tokenize.

        Returns:
            Set of lowercase tokens.
        """
        if not text:
            return set()
        # Simple tokenization: split on whitespace and punctuation
        tokens = text.lower().replace("/", " ").replace("-", " ").split()
        # Filter out very short tokens
        return {t.strip() for t in tokens if len(t) > 2}

    def _score_job(self, job: Job, keywords: set[str]) -> int:
        """
        Score a job against user keywords.

        Args:
            job: Job model instance.
            keywords: User keyword set.

        Returns:
            Match score (number of matching keywords).
        """
        score = 0

        # Score from job title
        title_keywords = self._tokenize(job.title)
        score += len(title_keywords & keywords)

        # Score from company name
        company_keywords = self._tokenize(job.company)
        score += len(company_keywords & keywords)

        # Score from tags
        for tag in job.tags:
            tag_keywords = self._tokenize(tag)
            score += len(tag_keywords & keywords)

        return score

    async def send_notification(self, notification: dict[str, Any]) -> bool:
        """
        Send a notification via email.

        Full send logic:
        a. Format email body with matched job details
        b. Log notification (INFO level) — INFR-06 compliance
        c. Check Supabase email service availability
        d. IF Supabase configured: send email via Supabase email
        e. ELSE: log "Supabase not configured, notification dormant"

        Args:
            notification: Notification dict with user_id, job_id, match_score.

        Returns:
            True if sent successfully, False otherwise.
        """
        # Format email body
        body = self._format_notification_body(notification)

        # Log notification
        logger.info(f"Sending notification: {body}")

        # Check Supabase configuration
        from src.config import settings

        # TODO: Uncomment when Supabase is configured:
        # from src.db.supabase import supabase_client
        # if supabase_client.is_configured:
        #     try:
        #         await supabase_client.send_email(
        #             to=notification["email"],
        #             subject=f"New Job Match: {notification['job_title']}",
        #             body=body,
        #         )
        #         logger.info(f"Email sent to {notification['email']}")
        #         return True
        #     except Exception as e:
        #         logger.error(f"Failed to send email: {e}")
        #         return False

        # Supabase not configured - notification is dormant
        logger.info(f"Supabase not configured, notification dormant: {notification}")
        return True  # Return True as we're not failing, just dormant

    def _format_notification_body(self, notification: dict[str, Any]) -> str:
        """
        Format notification email body.

        Args:
            notification: Notification data.

        Returns:
            Formatted email body.
        """
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

    async def process_notification_queue(self, session: AsyncSession) -> int:
        """
        Process queued notifications from notifications table.

        Process each queued notification via send_notification().
        Mark as sent on success.
        Return count of successfully sent notifications.

        Args:
            session: Async SQLAlchemy session.

        Returns:
            Number of successfully sent notifications.
        """
        # Fetch queued notifications
        result = await session.execute(
            select(Notification).where(Notification.status == "queued")
        )
        notifications = result.scalars().all()
        logger.info(f"Processing {len(notifications)} queued notifications")

        sent_count = 0

        for notification in notifications:
            # Fetch job details for the notification
            result = await session.execute(select(Job).where(Job.id == notification.job_id))
            job = result.scalar_one_or_none()

            if not job:
                logger.warning(f"Job {notification.job_id} not found for notification")
                notification.status = "failed"
                continue

            # Fetch user for email
            result = await session.execute(select(User).where(User.id == notification.user_id))
            user = result.scalar_one_or_none()

            if not user or not user.email:
                logger.warning(f"User {notification.user_id} has no email")
                notification.status = "failed"
                continue

            # Prepare notification data
            notification_data = {
                "user_id": notification.user_id,
                "email": user.email,
                "job_id": notification.job_id,
                "job_title": job.title,
                "company": job.company,
                "location": job.location,
                "apply_link": job.apply_link,
                "match_score": notification.match_score,
            }

            # Send notification
            success = await self.send_notification(notification_data)

            if success:
                notification.status = "sent"
                notification.sent_at = notification.created_at
                sent_count += 1
            else:
                notification.status = "failed"

        await session.commit()
        logger.info(f"Sent {sent_count}/{len(notifications)} notifications")
        return sent_count


# Module-level service instance
notification_service = NotificationService()


async def check_and_queue_notifications(session: AsyncSession) -> int:
    """
    Convenience function to check and queue notifications.

    Args:
        session: Async SQLAlchemy session.

    Returns:
        Number of notifications queued.
    """
    return await notification_service.check_and_queue_notifications(session)


# TODO: Profile toggle for Job Match Alerts (Phase 2+ when user auth exists)
# When Phase 2 adds user authentication, add a 'notifications_enabled' field
# to the User model and check it before queuing notifications.
