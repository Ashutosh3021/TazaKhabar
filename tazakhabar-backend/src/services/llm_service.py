"""
LLM service for TazaKhabar using Google Gemini.
Handles news summarization, rate limiting, and market observation generation.
"""
import asyncio
import logging
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential

from google import genai
from google.genai import Client
from google.genai import types
from sqlalchemy import select

from src.config import settings
from src.db.database import async_session
from src.db.models import News, RateLimit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_client: Client | None = None
_verified_model: str | None = None

# ---------------------------------------------------------------------------
# Rate limiting constants
# ---------------------------------------------------------------------------
DAILY_LIMITS = {"anonymous": 5, "registered": 20}

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SUMMARIZATION_SYSTEM = (
    "You are a tech job market analyst. Write 2-3 sentence summaries focused on job market impact. Be direct and factual."
)

SUMMARIZATION_PROMPT = """Summarize this HN post for tech workers. Focus on job market impact. Keep to 2-3 sentences. Return ONLY the summary text.

Title: {title}
URL: {url}
Score: {score}

Summary:"""

OBSERVATION_SYSTEM = (
    "You are a tech job market analyst. Write actionable insights for tech workers."
)

OBSERVATION_PROMPT = """Based on these booming/declining keywords from HN tech job posts, write one paragraph explaining the trend and what tech workers should do. Be direct and actionable.

Booming: {booming}
Declining: {declining}

Observation:"""

# ---------------------------------------------------------------------------
# Gemini client helpers
# ---------------------------------------------------------------------------


def get_client() -> Client:
    """
    Get or create the singleton Gemini client.
    Loaded once at startup from GEMINI_API_KEY.
    """
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info(f"Gemini client initialized with API key: {settings.GEMINI_API_KEY[:8]}...")
    return _client


def _verify_model(client: Client) -> str:
    """
    Verify which Gemini model is available.
    Tries models in order of preference and returns the first that works.
    """
    models_to_try = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Hi",
                config=types.GenerateContentConfig(
                    system_instruction=SUMMARIZATION_SYSTEM,
                    max_output_tokens=10,
                ),
            )
            if response.text:
                logger.info(f"Verified Gemini model: {model_name}")
                return model_name
        except Exception as e:
            logger.warning(f"Model {model_name} not available: {e}")
            continue

    raise RuntimeError("No working Gemini model found (tried: gemini-2.0-flash, gemini-2.5-flash, gemini-1.5-flash)")


def get_verified_model() -> str:
    """Get the verified model name, lazily checking on first call."""
    global _verified_model
    if _verified_model is None:
        _verified_model = _verify_model(get_client())
    return _verified_model


# ---------------------------------------------------------------------------
# Retry-wrapped LLM call
# ---------------------------------------------------------------------------


def _is_retryable_error(exc: Exception) -> bool:
    """Return True if the error looks like a rate-limit or resource-exhausted error."""
    msg = str(exc).lower()
    return any(kw in msg for kw in ["429", "resource_exhausted", "rate limit", "quota"])


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=30, max=60),
    reraise=True,
    after=lambda state: logger.warning(f"Retry {state.attempt_number} after 30s..."),
)
async def _call_gemini(system_instruction: str, prompt: str) -> str:
    """
    Call Gemini with tenacity retry on 429/resouce-exhausted errors.
    """
    loop = asyncio.get_event_loop()
    model = get_verified_model()
    client = get_client()

    def _sync_call():
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=500,
            ),
        )

    try:
        response = await loop.run_in_executor(None, _sync_call)
        return response.text or ""
    except Exception as exc:
        if _is_retryable_error(exc):
            logger.warning(f"Gemini 429/resource-exhausted, will retry: {exc}")
            raise
        raise


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def check_rate_limit(user_id: str | None) -> tuple[bool, int]:
    """
    Check if user is within their daily rate limit.

    Returns:
        (allowed: bool, retry_after: int seconds)
        retry_after = seconds until midnight UTC if limit exceeded.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    limit = DAILY_LIMITS["registered"] if user_id else DAILY_LIMITS["anonymous"]

    async with async_session() as session:
        # Find existing record
        stmt = select(RateLimit).where(
            RateLimit.user_id == user_id,
            RateLimit.date == today,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            # No record yet, user is within limit
            return True, 0

        if record.request_count >= limit:
            # Calculate seconds until midnight UTC
            now = datetime.utcnow()
            midnight = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
            # Actually calculate midnight properly
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            retry_after = int((tomorrow - now).total_seconds())
            logger.info(f"Rate limit exceeded for user={user_id}: {record.request_count}/{limit}, retry_after={retry_after}s")
            return False, retry_after

        return True, 0


async def increment_rate_limit(user_id: str | None) -> None:
    """
    Increment the rate limit counter for a user.
    Creates a new record if none exists for today.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")

    async with async_session() as session:
        # Try to get existing record
        stmt = select(RateLimit).where(
            RateLimit.user_id == user_id,
            RateLimit.date == today,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            # Create new record
            record = RateLimit(
                user_id=user_id,
                date=today,
                request_count=1,
                last_request_at=datetime.utcnow(),
            )
            session.add(record)
        else:
            # Increment existing
            record.request_count += 1
            record.last_request_at = datetime.utcnow()

        await session.commit()
        logger.debug(f"Rate limit incremented for user={user_id}: {record.request_count}")


async def check_and_increment(user_id: str | None) -> tuple[bool, int]:
    """
    Atomic check-and-increment for rate limiting.
    Both operations happen in a single transaction.
    Returns (allowed, retry_after_seconds).
    """
    allowed, retry_after = await check_rate_limit(user_id)
    if allowed:
        await increment_rate_limit(user_id)
    return allowed, retry_after


# ---------------------------------------------------------------------------
# News summarization
# ---------------------------------------------------------------------------


async def summarize_news_item(news_item_id: str) -> str | None:
    """
    Summarize a single news item using Gemini.

    Returns:
        The summary text, or None if already summarized or error.
    """
    async with async_session() as session:
        stmt = select(News).where(News.id == news_item_id)
        result = await session.execute(stmt)
        news = result.scalar_one_or_none()

        if news is None:
            logger.warning(f"News item not found: {news_item_id}")
            return None

        if news.summarized:
            logger.debug(f"News item already summarized, skipping: {news_item_id}")
            return news.summary

        try:
            prompt = SUMMARIZATION_PROMPT.format(
                title=news.title,
                url=news.url or "N/A",
                score=news.score,
            )
            summary = await _call_gemini(SUMMARIZATION_SYSTEM, prompt)
            summary = summary.strip()

            # Save summary to DB
            news.summary = summary
            news.summarized = True
            news.summarized_at = datetime.utcnow()
            await session.commit()
            logger.info(f"Summarized news item {news_item_id}: {summary[:50]}...")
            return summary
        except Exception as e:
            logger.error(f"Failed to summarize news item {news_item_id}: {e}")
            return None


async def summarize_top_news(top_n: int = 20) -> None:
    """
    Summarize the top N unsummarized news items by score.
    Idempotent — skips items where summarized=True.
    Background task — does NOT block the scraper.
    """
    logger.info(f"[SUMMARIZATION] Starting summarization of top {top_n} news items...")

    async with async_session() as session:
        # Get top N unsummarized items by score
        stmt = (
            select(News)
            .where(News.summarized == False)
            .order_by(News.score.desc())
            .limit(top_n)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()

    if not items:
        logger.info("[SUMMARIZATION] No unsummarized items found")
        return

    logger.info(f"[SUMMARIZATION] Found {len(items)} items to summarize")
    success_count = 0
    error_count = 0

    for item in items:
        summary = await summarize_news_item(item.id)
        if summary:
            success_count += 1
        else:
            error_count += 1

    logger.info(f"[SUMMARIZATION] Complete: {success_count} succeeded, {error_count} failed")


# ---------------------------------------------------------------------------
# Market observation generation
# ---------------------------------------------------------------------------


async def generate_with_retry(prompt: str, system_instruction: str | None = None) -> str:
    """
    General-purpose Gemini call with retry.
    Use this from other services (resume, etc.) instead of raw _call_gemini.

    Args:
        prompt: User prompt text.
        system_instruction: Optional system instruction.

    Returns:
        Gemini response text.
    """
    if system_instruction:
        return await _call_gemini(system_instruction, prompt)
    else:
        return await _call_gemini("", prompt)


async def generate_observation_text(
    booming_keywords: list[str],
    declining_keywords: list[str],
) -> str:
    """
    Generate a market observation paragraph from trending keyword data.

    Args:
        booming_keywords: List of rising keyword strings.
        declining_keywords: List of declining keyword strings.

    Returns:
        LLM-written observation paragraph.
    """
    prompt = OBSERVATION_PROMPT.format(
        booming=", ".join(booming_keywords[:10]),
        declining=", ".join(declining_keywords[:10]),
    )

    try:
        text = await _call_gemini(OBSERVATION_SYSTEM, prompt)
        logger.info(f"Generated observation: {text[:80]}...")
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to generate observation: {e}")
        return "Market analysis temporarily unavailable. Check back soon."


# ---------------------------------------------------------------------------
# Module initialization print
# ---------------------------------------------------------------------------
print("[OK] llm_service.py loaded — Gemini client, retry, rate limiting, summarization ready")
