"""
Health check API endpoints.

Reports the state of the Pyronites backend that holds the data.
"""
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

from src.config import settings
from src.db.pyro import get_pyro

router = APIRouter(prefix="/health", tags=["health"])


class StorageHealthResponse(BaseModel):
    """Response model for the storage health check."""

    storage: Dict[str, Any]
    email: Dict[str, Any]
    overall_status: str
    timestamp: str


class SystemHealthResponse(BaseModel):
    """Response model for overall system health."""

    status: str
    pyronites: Dict[str, Any]
    database: Dict[str, Any]
    timestamp: str


@router.get("/pyronites", response_model=StorageHealthResponse)
async def pyronites_health() -> StorageHealthResponse:
    """Check the Pyronites backend connection."""
    timestamp = datetime.utcnow().isoformat()
    try:
        healthy = await get_pyro().healthy()
        return StorageHealthResponse(
            storage={"configured": True, "connected": healthy},
            email={"configured": bool(settings.EMAIL_SMTP_HOST), "connected": False},
            overall_status="connected" if healthy else "error",
            timestamp=timestamp,
        )
    except Exception as e:
        return StorageHealthResponse(
            storage={"configured": True, "connected": False, "error": str(e)},
            email={"configured": bool(settings.EMAIL_SMTP_HOST), "connected": False},
            overall_status="error",
            timestamp=timestamp,
        )


@router.get("/detailed", response_model=SystemHealthResponse)
async def detailed_health() -> SystemHealthResponse:
    """Detailed health information for monitoring and diagnostics."""
    timestamp = datetime.utcnow().isoformat()

    try:
        healthy = await get_pyro().healthy()
        tables = await get_pyro().table_names()
        backend = {
            "configured": True,
            "connected": healthy,
            "url": settings.PYRONITES_URL,
            "project_id": settings.PYRONITES_PROJECT_ID,
            "tables": len(tables),
        }
    except Exception as e:
        healthy = False
        backend = {"configured": True, "connected": False, "error": str(e)}

    return SystemHealthResponse(
        status="healthy" if healthy else "degraded",
        pyronites=backend,
        database={
            "type": "pyronites",
            "project_id": settings.PYRONITES_PROJECT_ID,
        },
        timestamp=timestamp,
    )
