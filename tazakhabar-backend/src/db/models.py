"""
SQLAlchemy 2.0 async models for TazaKhabar backend.
Postgres-aware schema with UUID PKs, TIMESTAMPTZ, JSON, explicit defaults.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, LargeBinary, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return uuid.uuid4().hex


class Job(Base):
    """Job listings from HN Who Is Hiring threads."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    hn_item_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200), default="N/A")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    email_contact: Mapped[str | None] = mapped_column(String(500), nullable=True)
    apply_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_ghost_job: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[str | None] = mapped_column(String(50), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    report_version: Mapped[str] = mapped_column(String(10), default="2")


class News(Base):
    """News items from HN Ask HN, Show HN, and Top Stories."""
    __tablename__ = "news"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    hn_item_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20))  # "ask_hn", "show_hn", "top_story"
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    summarized: Mapped[bool] = mapped_column(Boolean, default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    report_version: Mapped[str] = mapped_column(String(10), default="2")


class Trend(Base):
    """Weekly trend tracking for keywords."""
    __tablename__ = "trends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    keyword: Mapped[str] = mapped_column(String(100), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    week_start: Mapped[datetime] = mapped_column(DateTime)
    week_end: Mapped[datetime] = mapped_column(DateTime)
    percentage_change: Mapped[float] = mapped_column(Float, default=0.0)


class User(Base):
    """User accounts and preferences."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_level: Mapped[str] = mapped_column(String(10), default="I")
    resume_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RateLimit(Base):
    """Rate limiting tracking per user."""
    __tablename__ = "rate_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    date: Mapped[str] = mapped_column(String(10))  # "YYYY-MM-DD"
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    last_request_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Report(Base):
    """Scraper run reports."""
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    version: Mapped[str] = mapped_column(String(10))  # "1" or "2"
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    new_items: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, completed, failed


class Embedding(Base):
    """Vector embeddings for jobs, news, and resumes."""
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    item_type: Mapped[str] = mapped_column(String(20))  # "job", "news", "resume"
    embedding: Mapped[bytes] = mapped_column(LargeBinary)  # BLOB, stored as bytes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """Notification queue for job match alerts."""
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36))
    match_score: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, sent, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
