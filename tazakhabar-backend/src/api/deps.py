"""
FastAPI dependencies for database sessions.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
