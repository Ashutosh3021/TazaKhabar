"""
Embedding service for TazaKhabar RAG personalization.
Uses sentence-transformers (all-MiniLM-L6-v2) for embedding generation.
"""
import logging
import uuid
import asyncio

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job, News, Embedding

from src.db.database import async_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 produces 384-dimensional embeddings
EXPECTED_BYTES = EMBEDDING_DIM * 4  # 4 bytes per float32 = 1536 bytes

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """
    Get or create the singleton embedding model.
    Loads all-MiniLM-L6-v2 (384 dimensions, 22MB, unit-normalized) on first call.
    """
    global _embedding_model
    if _embedding_model is None:
        print(">>> [EMBEDDING] Loading sentence-transformers model (first run takes ~5s)...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print(f">>> [OK] Embedding model loaded: all-MiniLM-L6-v2 (384 dims)")
    return _embedding_model


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------


def generate_text_embedding(text: str) -> bytes:
    """
    Generate embedding for text and return as bytes for BLOB storage.

    Uses unit-normalized output — dot product = cosine similarity.
    Validates output is exactly 1536 bytes (384 dims * 4 bytes).
    """
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    embedding_bytes = embedding.astype(np.float32).tobytes()
    
    # Validate embedding size
    if len(embedding_bytes) != EXPECTED_BYTES:
        raise ValueError(f"Embedding size mismatch: expected {EXPECTED_BYTES} bytes, got {len(embedding_bytes)}")
    
    return embedding_bytes


def generate_content_embedding(item_type: str, item_id: str, text: str) -> bytes:
    """
    Generate embedding for a news or job item.
    Combines type and text for richer embedding.
    """
    combined = f"{item_type.upper()}: {text[:2000]}"
    return generate_text_embedding(combined)


def generate_user_profile_text(
    user_roles: list[str],
    experience_level: str,
    resume_text: str | None,
    preferences: dict | None,
) -> str:
    """
    Combine user data into a single text for embedding.
    """
    parts = [
        f"Target roles: {', '.join(user_roles) if user_roles else 'software engineer'}",
        f"Experience level: {experience_level}",
    ]
    if resume_text:
        parts.append(f"Background: {resume_text[:2000]}")
    if preferences:
        parts.append(f"Preferences: {preferences}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Embedding storage
# ---------------------------------------------------------------------------


async def generate_user_embedding(
    user_id: str,
    roles: list[str],
    experience: str,
    resume_text: str | None = None,
    preferences: dict | None = None,
) -> None:
    """
    Generate and store embedding for a user profile.
    Upserts: deletes old embedding, inserts new one.
    """
    text = generate_user_profile_text(roles, experience, resume_text, preferences)
    embedding_bytes = generate_text_embedding(text)

    async with async_session() as session:
        # Delete old user profile embedding
        await session.execute(
            delete(Embedding).where(
                Embedding.item_id == user_id,
                Embedding.item_type == "user_profile",
            )
        )
        # Insert new embedding
        session.add(
            Embedding(
                id=uuid.uuid4().hex,
                item_id=user_id,
                item_type="user_profile",
                embedding=embedding_bytes,
            )
        )
        await session.commit()
    logger.info(f"Generated and stored user profile embedding for user_id={user_id}")


async def embed_news_item(
    news_id: str,
    title: str,
    summary: str | None,
    news_type: str,
) -> None:
    """
    Generate and store embedding for a news item.
    Incremental: skips if already embedded.
    """
    # Combine title + summary + type
    text = f"{news_type.upper()}: {title} {summary or ''}"
    embedding_bytes = generate_text_embedding(text[:2000])

    async with async_session() as session:
        # Check if already embedded
        existing = await session.execute(
            select(Embedding).where(
                Embedding.item_id == news_id,
                Embedding.item_type == "news",
            )
        )
        if existing.scalar_one_or_none():
            return  # Already embedded

        session.add(
            Embedding(
                id=uuid.uuid4().hex,
                item_id=news_id,
                item_type="news",
                embedding=embedding_bytes,
            )
        )
        await session.commit()
    logger.info(f"Generated and stored content embedding for news_id={news_id}")


async def embed_job_item(
    job_id: str,
    title: str,
    company: str,
    location: str | None,
) -> None:
    """
    Generate and store embedding for a job item.
    Incremental: skips if already embedded.
    """
    text = f"JOB: {title} at {company} {location or ''}"
    embedding_bytes = generate_text_embedding(text[:2000])

    async with async_session() as session:
        existing = await session.execute(
            select(Embedding).where(
                Embedding.item_id == job_id,
                Embedding.item_type == "job",
            )
        )
        if existing.scalar_one_or_none():
            return

        session.add(
            Embedding(
                id=uuid.uuid4().hex,
                item_id=job_id,
                item_type="job",
                embedding=embedding_bytes,
            )
        )
        await session.commit()

    logger.info(f"Generated and stored content embedding for job_id={job_id}")


async def backfill_missing_embeddings(session: AsyncSession) -> dict:
    """
    Find News and Job items missing embeddings and generate them with limited concurrency.

    Returns:
        dict with counts: {"news_queued": n, "jobs_queued": m}

    BUG FIX [M9]: provide idempotent embedding backfill and limited concurrency.
    """
    # Fetch existing embedding ids for news and jobs
    existing_news_res = await session.execute(select(Embedding.item_id).where(Embedding.item_type == "news"))
    existing_news_ids = {r[0] for r in existing_news_res.all()}

    existing_job_res = await session.execute(select(Embedding.item_id).where(Embedding.item_type == "job"))
    existing_job_ids = {r[0] for r in existing_job_res.all()}

    # Find missing news
    if existing_news_ids:
        news_stmt = select(News).where(~News.id.in_(existing_news_ids))
    else:
        news_stmt = select(News)
    news_res = await session.execute(news_stmt)
    missing_news = news_res.scalars().all()

    # Find missing jobs
    if existing_job_ids:
        job_stmt = select(Job).where(~Job.id.in_(existing_job_ids))
    else:
        job_stmt = select(Job)
    job_res = await session.execute(job_stmt)
    missing_jobs = job_res.scalars().all()

    news_queued = 0
    jobs_queued = 0

    semaphore = asyncio.Semaphore(5)

    async def _wrap_embed_news(n_id, title, summary, n_type):
        async with semaphore:
            try:
                await embed_news_item(n_id, title, summary, n_type)
            except Exception:
                logger.exception(f"Failed to embed news {n_id}")

    async def _wrap_embed_job(j_id, title, company, location):
        async with semaphore:
            try:
                await embed_job_item(j_id, title, company, location)
            except Exception:
                logger.exception(f"Failed to embed job {j_id}")

    tasks = []
    for n in missing_news:
        tasks.append(asyncio.create_task(_wrap_embed_news(n.id, getattr(n, "title", ""), getattr(n, "summary", None), getattr(n, "type", "news"))))
        news_queued += 1

    for j in missing_jobs:
        tasks.append(asyncio.create_task(_wrap_embed_job(j.id, getattr(j, "title", ""), getattr(j, "company", ""), getattr(j, "location", None))))
        jobs_queued += 1

    if tasks:
        # Wait for all scheduled embedding tasks to complete
        await asyncio.gather(*tasks)

    logger.info(f"Backfilled embeddings: news_queued={news_queued}, jobs_queued={jobs_queued}")
    return {"news_queued": news_queued, "jobs_queued": jobs_queued}


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


def cosine_similarity_bytes(embedding_a: bytes, embedding_b: bytes) -> float:
    """
    Compute cosine similarity between two BLOB embeddings.
    Both vectors are unit-normalized, so dot product = cosine similarity.
    Returns value in [-1, 1].
    """
    vec_a = np.frombuffer(embedding_a, dtype=np.float32)
    vec_b = np.frombuffer(embedding_b, dtype=np.float32)
    return float(np.dot(vec_a, vec_b))


def normalize_similarity(sim: float) -> int:
    """
    Normalize cosine similarity from [-1, 1] to [0, 100].
    """
    normalized = (sim + 1) / 2 * 100
    return int(max(0, min(100, normalized)))


# ---------------------------------------------------------------------------
# Module initialization print
# ---------------------------------------------------------------------------
print("[OK] embedding_service.py loaded — sentence-transformers ready")
