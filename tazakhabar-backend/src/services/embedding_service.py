"""
Embedding service for TazaKhabar RAG personalization.
Uses sentence-transformers (all-MiniLM-L6-v2) for embedding generation.
"""
import logging
import uuid

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import delete, select

from src.db.database import async_session
from src.db.models import Embedding

logger = logging.getLogger(__name__)

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
    """
    model = get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.astype(np.float32).tobytes()


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
