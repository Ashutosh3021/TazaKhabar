"""
Market observation API endpoint.
Returns the latest LLM-generated market trend narrative.
"""
import logging

from fastapi import APIRouter

from src.db import repos
from src.db.schemas import ObservationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observation", tags=["observation"])


@router.get("", response_model=ObservationResponse)
async def get_observation() -> ObservationResponse:
    """
    Get the most recent market observation.

    Returns fallback=True with empty text when no observation has been written
    yet, so the frontend can suppress the block instead of showing a
    placeholder.
    """
    try:
        observation = await repos.latest_observation()
        if not observation:
            return ObservationResponse(text="", generated_at=None, fallback=True)

        return ObservationResponse(
            text=observation.get("text") or "",
            generated_at=observation.get("generated_at"),
            fallback=False,
        )
    except Exception:
        logger.exception("GET /api/observation failed")
        return ObservationResponse(text="", generated_at=None, fallback=True)
