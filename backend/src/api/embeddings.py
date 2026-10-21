"""
Embedding management API (admin).

The backfill is also run by the GitHub Actions workflow; this endpoint stays
available for a manual run from an authenticated admin session.
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from src.api.deps import require_user
from src.services.embedding_service import backfill_missing_embeddings
from src.services.trend_service import run_predictions_backfill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


@router.post("/backfill")
async def embeddings_backfill(
    user: dict = Depends(require_user),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    """
    Generate the missing embeddings and backfill trend predictions.

    Requires a signed-in user and the admin token when ADMIN_TOKEN is set.
    """
    from src.config import settings

    if settings.ADMIN_TOKEN and x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin token required")

    try:
        emb_result = await backfill_missing_embeddings()
        preds = await run_predictions_backfill()
        return {
            "status": "ok",
            "embeddings": emb_result,
            "trend_predictions_processed": preds,
        }
    except Exception as e:
        logger.exception("Error during embeddings backfill")
        return {"status": "error", "error": str(e)}
