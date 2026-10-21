"""
Embedding service for TazaKhabar RAG personalization.
Uses sentence-transformers (all-MiniLM-L6-v2) for embedding generation.
"""
import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from src.db import repos
from src.config import settings

logger = logging.getLogger(__name__)

# sentence-transformers is optional on low-memory deployments (e.g. Render free tier)
if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 produces 384-dimensional embeddings
EXPECTED_BYTES = EMBEDDING_DIM * 4  # 4 bytes per float32 = 1536 bytes

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_embedding_model = None


def get_embedding_model() -> Any:
    """
    Get or create the singleton embedding model.
    Loads all-MiniLM-L6-v2 (384 dimensions, 22MB, unit-normalized) on first call.
    """
    if not settings.EMBEDDINGS_ENABLED:
        raise RuntimeError("Embeddings are disabled (EMBEDDINGS_ENABLED=false)")

    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except Exception as e:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install it (and torch) or set EMBEDDINGS_ENABLED=false."
            ) from e

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
    Generate and store the embedding for a user profile.
    Replaces any previous embedding for that user.
    """
    text = generate_user_profile_text(roles, experience, resume_text, preferences)
    embedding_bytes = generate_text_embedding(text)
    await repos.upsert_embedding(user_id, "user_profile", embedding_bytes)
    logger.info(f"Generated and stored user profile embedding for user_id={user_id}")


async def embed_news_item(
    news_id: str,
    title: str,
    summary: str | None,
    news_type: str,
) -> None:
    """
    Generate and store the embedding for a news item.
    Incremental: skips when the item already has an embedding.
    """
    text = f"{news_type.upper()}: {title} {summary or ''}"
    embedding_bytes = generate_text_embedding(text[:2000])

    if await repos.get_embedding(news_id, "news"):
        return

    await repos.upsert_embedding(news_id, "news", embedding_bytes)
    logger.info(f"Generated and stored content embedding for news_id={news_id}")


async def embed_job_item(
    job_id: str,
    title: str,
    company: str,
    location: str | None,
) -> None:
    """
    Generate and store the embedding for a job item.
    Incremental: skips when the item already has an embedding.
    """
    text = f"JOB: {title} at {company} {location or ''}"
    embedding_bytes = generate_text_embedding(text[:2000])

    if await repos.get_embedding(job_id, "job"):
        return

    await repos.upsert_embedding(job_id, "job", embedding_bytes)
    logger.info(f"Generated and stored content embedding for job_id={job_id}")


async def backfill_missing_embeddings(limit: int = 200) -> dict:
    """
    Generate embeddings for jobs and news that do not have one yet.

    Returns:
        dict with counts: {"news_queued": n, "jobs_queued": m}
    """
    missing_news = await repos.news_without_embeddings(limit)
    missing_jobs = await repos.jobs_without_embeddings(limit)

    semaphore = asyncio.Semaphore(5)

    async def _embed_news(item: dict) -> Optional[bytes]:
        async with semaphore:
            try:
                text = f"{(item['type'] or 'news').upper()}: {item['title']} {item.get('summary') or ''}"
                blob = generate_text_embedding(text[:2000])
                await repos.upsert_embedding(item["id"], "news", blob)
                return blob
            except Exception:
                logger.exception(f"Failed to embed news {item['id']}")
                return None

    async def _embed_job(item: dict) -> Optional[bytes]:
        async with semaphore:
            try:
                text = f"JOB: {item['title']} at {item['company']} {item.get('location') or ''}"
                blob = generate_text_embedding(text[:2000])
                await repos.upsert_embedding(item["id"], "job", blob)
                return blob
            except Exception:
                logger.exception(f"Failed to embed job {item['id']}")
                return None

    tasks = [asyncio.create_task(_embed_news(item)) for item in missing_news]
    tasks += [asyncio.create_task(_embed_job(item)) for item in missing_jobs]

    if tasks:
        await asyncio.gather(*tasks)

    logger.info(
        "Backfilled embeddings: news_queued=%s, jobs_queued=%s",
        len(missing_news),
        len(missing_jobs),
    )
    return {"news_queued": len(missing_news), "jobs_queued": len(missing_jobs)}


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
