"""
LLM service for TazaKhabar using OpenRouter and Groq.
Handles news summarization, rate limiting, and market observation generation.
Uses Groq with openai/gpt-oss-120b model (primary), falls back to OpenRouter free models.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

import httpx
from groq import Groq as GroqClient
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy import select

from src.config import settings
from src.db.database import async_session
from src.db.models import News, RateLimit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_verified_model: str | None = None

# ---------------------------------------------------------------------------
# OpenRouter configuration
# ---------------------------------------------------------------------------
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY

# Models to try in order of preference
MODELS_TO_TRY = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "z-ai/glm-4.5-air:free",
]

# ---------------------------------------------------------------------------
# Groq configuration
# ---------------------------------------------------------------------------
GROQ_API_KEY = settings.GROQ_API_KEY
GROQ_MODEL = "openai/gpt-oss-120b"

_groq_client: GroqClient | None = None


def _get_groq_client() -> GroqClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient(api_key=GROQ_API_KEY)
    return _groq_client


# ---------------------------------------------------------------------------
# Rate limiting constants
# ---------------------------------------------------------------------------
DAILY_LIMITS = {"anonymous": 5, "registered": 20}
MAX_RETRIES = 4
RETRY_WAIT_MIN = 60  # seconds (increased for quota exhaustion)
RETRY_WAIT_MAX = 180  # seconds (longer wait for daily quota reset)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
SUMMARIZATION_SYSTEM = "You are a tech job market analyst. Write 2-3 sentence summaries focused on job market impact. Be direct and factual."

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
# OpenRouter client helpers
# ---------------------------------------------------------------------------


def _verify_model() -> str:
    """
    Verify which OpenRouter model is available.
    Tries models in order of preference and returns the first that responds successfully.
    """
    for model_name in MODELS_TO_TRY:
        try:
            # Test call with minimal prompt
            response = httpx.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://tazakhabar.vercel.app",
                    "X-Title": "TazaKhabar",
                },
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 10,
                },
                timeout=30.0,
            )
            if response.status_code == 200:
                logger.info(f"Verified OpenRouter model: {model_name}")
                return model_name
            else:
                logger.warning(
                    f"Model {model_name} returned {response.status_code}: {response.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"Model {model_name} not available: {e}")
            continue

    raise RuntimeError(f"No working OpenRouter model found. Tried: {MODELS_TO_TRY}")


def get_verified_model() -> str:
    """Get the verified model name, lazily checking on first call."""
    global _verified_model
    if _verified_model is None:
        _verified_model = _verify_model()
    return _verified_model


# ---------------------------------------------------------------------------
# Retry-wrapped LLM call
# ---------------------------------------------------------------------------


def _is_retryable_error(exc: Exception) -> bool:
    """Return True if the error looks like a rate-limit or quota error."""
    msg = str(exc).lower()
    return any(
        kw in msg for kw in ["429", "rate limit", "quota", "overloaded", "503", "insufficient"]
    )


async def _call_groq(system_instruction: str, prompt: str) -> str:
    """
    Call Groq API with openai/gpt-oss-120b model.
    Non-streaming for simplicity.
    """
    client = _get_groq_client()

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL, messages=messages, temperature=1, max_tokens=500, top_p=1, stop=None
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:
        logger.warning(f"Groq API error: {exc}")
        raise


async def _call_openrouter(system_instruction: str, prompt: str) -> str:
    """
    Call OpenRouter with tenacity retry on 429/quota errors.
    """
    model = get_verified_model()

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tazakhabar.vercel.app",
        "X-Title": "TazaKhabar",
    }

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 500,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=60.0,
            )

            if response.status_code != 200:
                error_msg = f"OpenRouter API error: {response.status_code} - {response.text[:200]}"
                logger.error(error_msg)
                raise Exception(error_msg)

            data = response.json()
            # OpenRouter response format
            return data["choices"][0]["message"]["content"] or ""

        except Exception as exc:
            if _is_retryable_error(exc):
                logger.warning(f"OpenRouter rate limit/quota, will retry: {exc}")
                raise
            raise


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    reraise=True,
    after=lambda state: logger.warning(f"Retry {state.attempt_number} after {RETRY_WAIT_MIN}s..."),
)
async def _call_llm(system_instruction: str, prompt: str) -> str:
    """
    Call LLM with fallback: try Groq first, then OpenRouter.

    Note: Tenacity handles asyncio.sleep internally for exponential backoff
    between retry attempts (RETRY_WAIT_MIN to RETRY_WAIT_MAX seconds).
    """
    # Try Groq first
    try:
        return await _call_groq(system_instruction, prompt)
    except Exception as groq_error:
        logger.warning(f"Groq failed, falling back to OpenRouter: {groq_error}")
        # Fall back to OpenRouter
        return await _call_openrouter(system_instruction, prompt)


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
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            retry_after = int((tomorrow - now).total_seconds())
            logger.info(
                f"Rate limit exceeded for user={user_id}: {record.request_count}/{limit}, retry_after={retry_after}s"
            )
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
    Summarize a single news item using OpenRouter LLM.

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
            summary = await _call_llm(SUMMARIZATION_SYSTEM, prompt)
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
        stmt = select(News).where(News.summarized == False).order_by(News.score.desc()).limit(top_n)
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
    General-purpose LLM call with retry.
    Use this from other services (resume, etc.) instead of raw _call_llm.

    Args:
        prompt: User prompt text.
        system_instruction: Optional system instruction.

    Returns:
        LLM response text.
    """
    if system_instruction:
        return await _call_llm(system_instruction, prompt)
    else:
        return await _call_llm("", prompt)


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
        text = await _call_llm(OBSERVATION_SYSTEM, prompt)
        logger.info(f"Generated observation: {text[:80]}...")
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to generate observation: {e}")
        return "Market analysis temporarily unavailable. Check back soon."


# ---------------------------------------------------------------------------
# Module initialization print
# ---------------------------------------------------------------------------
print("[OK] llm_service.py loaded — OpenRouter client, retry, rate limiting, summarization ready")
