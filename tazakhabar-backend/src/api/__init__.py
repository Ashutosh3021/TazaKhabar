"""
FastAPI API routes.
"""
from src.api.jobs import router as jobs_router
from src.api.news import router as news_router

__all__ = ["jobs_router", "news_router"]
