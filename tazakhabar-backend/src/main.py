import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api import jobs_router, news_router, trends_router, badge_router, refresh_router
from src.middleware.logging import RequestLoggingMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("TazaKhabar backend starting")
    
    # Import and create database tables
    from src.db.database import create_all_tables
    await create_all_tables()
    logger.info("Database tables created/verified")
    
    # Import and start scheduler
    from src.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    logger.info("Scraper scheduler started")
    
    yield
    
    # Shutdown
    logger.info("TazaKhabar backend shutting down")
    stop_scheduler()
    logger.info("Scraper scheduler stopped")


# Create FastAPI application
app = FastAPI(
    title="TazaKhabar API",
    description="Backend API for TazaKhabar news scraping service",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routers
app.include_router(jobs_router)
app.include_router(news_router)
app.include_router(trends_router)
app.include_router(badge_router)
app.include_router(refresh_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Railway deployment.
    
    Returns:
        dict: Health status with timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
