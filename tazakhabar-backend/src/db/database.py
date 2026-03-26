"""
SQLAlchemy 2.0 async setup with aiosqlite for SQLite.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
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


def _sqlalchemy_type_to_sqlite(col_type: str) -> str:
    """
    Map SQLAlchemy column type strings to SQLite-compatible column types.
    Falls back to TEXT for unknown types.
    """
    upper = col_type.upper()
    if "INT" in upper or "INTEGER" in upper:
        return "INTEGER"
    if "BIGINT" in upper or "SMALLINT" in upper:
        return "INTEGER"
    if "FLOAT" in upper or "REAL" in upper or "DOUBLE" in upper or "DECIMAL" in upper:
        return "REAL"
    if "BOOL" in upper:
        return "INTEGER"
    if "BLOB" in upper or "BINARY" in upper or "BYTEA" in upper:
        return "BLOB"
    # TEXT, VARCHAR, CHAR, JSON, DATE, DATETIME, TIMESTAMP, UUID → TEXT
    return "TEXT"


async def _migrate_missing_columns(conn) -> None:
    """
    Inspect live SQLite tables and add any columns that exist in SQLAlchemy
    models but are missing from the live schema (e.g., Phase 2 columns added
    to an existing database that was created before the model was updated).
    """
    from . import models  # noqa: F401

    for table_name, table in Base.metadata.tables.items():
        # Get columns that exist in the live SQLite table
        existing_cols = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text(f"PRAGMA table_info({table_name})")
            ).fetchall()
        )
        existing_col_names = {row[1] for row in existing_cols}  # PRAGMA returns (cid, name, type, notnull, ...)

        for col in table.columns:
            if col.name in existing_col_names:
                continue  # Column already exists — skip

            # Build ALTER TABLE ADD COLUMN statement
            col_type = _sqlalchemy_type_to_sqlite(str(col.type))
            nullable = " NOT NULL" if not col.nullable else ""
            default = ""
            if col.default is not None:
                # Only add a literal default if it's a plain value (int, str, bool, etc.).
                # Skip callable defaults (e.g. list, dict, uuid4, datetime.utcnow)
                # and complex expressions — SQLite ALTER TABLE can't handle them.
                raw_arg = getattr(col.default, "arg", None)
                is_callable_default = callable(raw_arg) if raw_arg is not None else True
                if not is_callable_default:
                    default_text = str(raw_arg)
                    if default_text not in ("None", "null"):
                        default = f" DEFAULT {default_text}"

            sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default}{nullable}"
            try:
                await conn.execute(text(sql))
                logger.info(f"[MIGRATION] Added column {table_name}.{col.name} ({col_type})")
            except Exception as e:
                logger.warning(f"[MIGRATION] Could not add {table_name}.{col.name}: {e}")


async def create_all_tables() -> None:
    """Create all tables defined in models, then migrate any missing columns."""
    from . import models  # noqa: F401
    async with engine.begin() as conn:
        # Step 1: create_all creates new tables but does NOT alter existing ones
        await conn.run_sync(Base.metadata.create_all)
        logger.info("All database tables created/verified")

        # Step 2: migrate — add any columns that exist in models but not in live DB
        await _migrate_missing_columns(conn)

    logger.info("All database tables and columns are up to date")


async def init_db() -> None:
    """Alias for create_all_tables."""
    await create_all_tables()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
