"""
CSV Loader API endpoint for loading jobs from AmbitionBox CSV files.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from src.services.csv_loader_service import load_jobs_from_csv, get_csv_stats

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
    limit: int = Query(default=100, ge=1, le=1000, description="Max jobs to load"),
    clear_existing: bool = Query(default=False, description="Clear existing jobs before loading"),
):
    """
    Load jobs from jobs_output.csv into the database.
    
    - **limit**: Maximum number of jobs to load (1-1000)
    - **clear_existing**: Whether to clear existing jobs before loading
    """
    try:
        logger.info(f"Loading jobs from CSV: limit={limit}, clear_existing={clear_existing}")
        result = await load_jobs_from_csv(limit=limit, clear_existing=clear_existing)
        
        if result["success"] > 0:
            return {
                "status": "success",
                "message": f"Loaded {result['success']} jobs from CSV",
                "data": result,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to load jobs: {result.get('errors', ['Unknown error'])}",
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading CSV jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
