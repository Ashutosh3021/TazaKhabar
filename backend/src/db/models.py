"""
SQLAlchemy 2.0 async models for TazaKhabar backend.
Postgres-aware schema with UUID PKs, TIMESTAMPTZ, JSON, explicit defaults.

UUID strategy
-------------
All primary-key `id` columns (and FK-like id columns such as user_id / job_id)
use sqlalchemy.Uuid(as_uuid=False, native_uuid=True).

  - native_uuid=True  → Postgres receives the value as the native UUID type,
                         which matches the `uuid` column definition created by
                         Supabase / the initial migration.  No VARCHAR cast
                         errors.
  - as_uuid=False     → Python side stores/returns a plain str (hex without
                        dashes), keeping the rest of the codebase unchanged.

The generate_uuid() helper returns uuid4().hex (32-char no-dash hex string).
SQLAlchemy's Uuid type with native_uuid=True handles the str → uuid cast
transparently on asyncpg.
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, LargeBinary, String, Text
from sqlalchemy import JSON
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def generate_uuid() -> str:
    """Generate a new UUID string (32-char hex, no dashes)."""
    return uuid.uuid4().hex


# Reusable column type: native Postgres UUID, Python-side str
_UUID = Uuid(as_uuid=False, native_uuid=True)


class Job(Base):
    """Job listings from HN Who Is Hiring threads."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    hn_item_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True, nullable=True)
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
    # LLM-processed fields
    cleaned_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cleaned_company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


class News(Base):
    """News items from HN Ask HN, Show HN, and Top Stories."""
    __tablename__ = "news"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    hn_item_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20))  # "ask_hn", "show_hn", "top_story"
    title: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    summarized: Mapped[bool] = mapped_column(Boolean, default=False)
    summarized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    report_version: Mapped[str] = mapped_column(String(10), default="2")


class Trend(Base):
    """Weekly trend tracking for keywords."""
    __tablename__ = "trends"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    keyword: Mapped[str] = mapped_column(String(100), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    week_start: Mapped[datetime] = mapped_column(DateTime)
    week_end: Mapped[datetime] = mapped_column(DateTime)
    percentage_change: Mapped[float] = mapped_column(Float, default=0.0)
    direction: Mapped[str] = mapped_column(String(20), default="neutral")


class User(Base):
    """User accounts and preferences."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_level: Mapped[str] = mapped_column(String(10), default="I")
    resume_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ats_critical_issues: Mapped[list[str]] = mapped_column(JSON, default=list)
    ats_missing_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    ats_suggested_additions: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrendPrediction(Base):
    """Predicted future counts for keywords."""
    __tablename__ = "trend_predictions"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    keyword: Mapped[str] = mapped_column(String(100), index=True)
    horizon_weeks: Mapped[int] = mapped_column(Integer)
    predicted_count: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RateLimit(Base):
    """Rate limiting tracking per user."""
    __tablename__ = "rate_limits"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(_UUID, nullable=True, index=True)
    date: Mapped[str] = mapped_column(String(10))  # "YYYY-MM-DD"
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    last_request_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Report(Base):
    """Scraper run reports."""
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    version: Mapped[str] = mapped_column(String(10))  # "1" or "2"
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    new_items: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, completed, failed
    scraper_name: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)


class Observation(Base):
    """Daily market trend narrative generated by LLM."""
    __tablename__ = "observations"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    week_start: Mapped[datetime] = mapped_column(DateTime)
    text: Mapped[str] = mapped_column(String(2000))
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Embedding(Base):
    """Vector embeddings for jobs, news, and resumes."""
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    item_id: Mapped[str] = mapped_column(_UUID, index=True)
    item_type: Mapped[str] = mapped_column(String(20))  # "job", "news", "resume"
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """Notification queue for job match alerts."""
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(_UUID, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(_UUID, index=True)
    job_id: Mapped[str] = mapped_column(_UUID)
    match_score: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued, sent, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
