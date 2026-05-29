"""
CSV Loader API endpoint for loading jobs from AmbitionBox CSV files.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from src.services.csv_loader_service import get_csv_stats
from src.services.notebook_sync_service import sync_jobs_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/csv", tags=["csv"])


@router.get("/stats")
async def get_csv_statistics():
    """
    Get statistics about the CSV files.
    """
    try:
        stats = await get_csv_stats()
        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Error getting CSV stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-jobs")
async def load_csv_jobs(
    force: bool = Query(default=True, description="Force sync even if CSV unchanged"),
):
    """
    Load jobs from jobs_output.csv into the database (same as POST /api/notebooks/sync).

    Prefer POST /api/notebooks/sync from notebooks; the app also auto-syncs every 15s.
    """
    try:
        logger.info("Manual CSV load via /api/csv/load-jobs")
        result = await sync_jobs_csv(force=force)

        if result.get("status") == "skipped":
            raise HTTPException(status_code=400, detail=result.get("reason", "CSV not found"))

        if result.get("status") == "unchanged":
            return {
                "status": "success",
                "message": "jobs_output.csv already synced",
                "data": result,
            }

        if result.get("success", 0) > 0 or result.get("status") == "synced":
            return {
                "status": "success",
                "message": f"Loaded {result.get('success', 0)} jobs from CSV",
                "data": result,
            }

        raise HTTPException(
            status_code=400,
            detail=f"No jobs loaded: {result.get('errors', ['Unknown error'])}",
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading CSV jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
