"""
FastAPI API routes.
"""
from src.api.jobs import router as jobs_router
from src.api.news import router as news_router
from src.api.trends import router as trends_router
from src.api.badge import router as badge_router
from src.api.refresh import router as refresh_router
from src.api.observation import router as observation_router
from src.api.resume import router as resume_router
from src.api.profile import router as profile_router

__all__ = [
    "jobs_router",
    "news_router",
    "trends_router",
    "badge_router",
    "refresh_router",
    "observation_router",
    "resume_router",
    "profile_router",
]
