"""
SQLAlchemy 2.0 async setup with aiosqlite for SQLite.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

# Async session factory
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def create_all_tables() -> None:
    """Create all tables defined in models."""
    from . import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created successfully")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
