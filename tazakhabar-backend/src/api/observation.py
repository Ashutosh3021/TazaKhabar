"""
Market observation API endpoint.
Returns the latest LLM-generated market trend narrative.
"""
import logging
from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import select

from src.db.database import async_session
from src.db.models import Observation
from src.db.schemas import ObservationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observation", tags=["observation"])

FALLBACK_TEXT = "Market analysis loading..."


@router.get("", response_model=ObservationResponse)
async def get_observation() -> ObservationResponse:
    """
    Get the most recent market observation.
    Returns fallback text if no observation has been generated yet.
    """
    try:
        async with async_session() as session:
            stmt = (
                select(Observation)
                .order_by(Observation.generated_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            observation = result.scalar_one_or_none()

        if observation is None:
            print(f">>> [API:GET /api/observation] No observation found, returning fallback")
            return ObservationResponse(
                text=FALLBACK_TEXT,
                generated_at=None,
                fallback=True,
            )

        generated_at_str = (
            observation.generated_at.isoformat()
            if observation.generated_at
            else None
        )
        print(f">>> [API:GET /api/observation] Returning observation from {generated_at_str}")

        return ObservationResponse(
            text=observation.text,
            generated_at=generated_at_str,
            fallback=False,
        )

    except Exception as e:
        print(f">>> [API:GET /api/observation] ERROR: {e}")
        import traceback
        print(f">>> [API:GET /api/observation] TRACE: {traceback.format_exc()}")
        logger.error(f"Error fetching observation: {e}")
        return ObservationResponse(
            text=FALLBACK_TEXT,
            generated_at=None,
            fallback=True,
        )
