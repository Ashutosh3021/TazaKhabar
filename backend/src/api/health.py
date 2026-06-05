"""
Health check API endpoints.

Provides detailed health and connection status information for monitoring.
"""
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.db.supabase import supabase_client
from src.config import settings

router = APIRouter(prefix="/health", tags=["health"])


class SupabaseHealthResponse(BaseModel):
    """Response model for Supabase health check."""
    storage: Dict[str, Any]
    email: Dict[str, Any]
    overall_status: str
    timestamp: str


class SystemHealthResponse(BaseModel):
    """Response model for overall system health."""
    status: str
    supabase: SupabaseHealthResponse
    database: Dict[str, Any]
    timestamp: str


@router.get("/supabase", response_model=SupabaseHealthResponse)
async def supabase_health():
    """
    Check Supabase connection status.
    
    Returns detailed information about Supabase storage and email connectivity.
    Can be called from frontend to display status in browser console.
    """
    try:
        connection_status = await supabase_client.check_supabase_connection()
        return SupabaseHealthResponse(
            storage=connection_status['storage'],
            email=connection_status['email'],
            overall_status=connection_status['overall_status'],
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        return SupabaseHealthResponse(
            storage={'configured': False, 'connected': False, 'error': str(e)},
            email={'configured': False, 'connected': False, 'error': str(e)},
            overall_status='error',
            timestamp=datetime.utcnow().isoformat(),
        )


@router.get("/detailed", response_model=SystemHealthResponse)
async def detailed_health():
    """
    Get detailed system health including Supabase and database status.
    
    Returns comprehensive health information for monitoring and diagnostics.
    """
    try:
        connection_status = await supabase_client.check_supabase_connection()
    except Exception as e:
        connection_status = {
            'storage': {'configured': False, 'connected': False, 'error': str(e)},
            'email': {'configured': False, 'connected': False, 'error': str(e)},
            'overall_status': 'error'
        }

    # Check database
    database_status = {
        'configured': bool(settings.DATABASE_URL),
        'url_type': 'sqlite' if 'sqlite' in settings.DATABASE_URL else 'postgresql',
    }

    return SystemHealthResponse(
        status='healthy' if connection_status['overall_status'] != 'error' else 'degraded',
        supabase=SupabaseHealthResponse(
            storage=connection_status['storage'],
            email=connection_status['email'],
            overall_status=connection_status['overall_status'],
            timestamp=datetime.utcnow().isoformat(),
        ),
        database=database_status,
        timestamp=datetime.utcnow().isoformat(),
    )
