"""
Embedding management API (admin).
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.services.embedding_service import backfill_missing_embeddings
from src.services.trend_service import run_predictions_backfill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


@router.post("/backfill")
async def embeddings_backfill(
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger backfill for missing embeddings (jobs + news) and trend prediction backfill.
    Admin-only endpoint (no auth applied here; caller should protect in deployment).
    """
    try:
        emb_result = await backfill_missing_embeddings(session)
        preds = await run_predictions_backfill(session)
        return {"status": "ok", "embeddings": emb_result, "trend_predictions_processed": preds}
    except Exception as e:
        logger.error(f"Error during embeddings backfill: {e}")
        return {"status": "error", "error": str(e)}
