import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api import jobs_router, news_router, trends_router, badge_router, refresh_router, observation_router, resume_router, profile_router, digest_router
from src.middleware.logging import RequestLoggingMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/tazakhabar.log"),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    print("\n" + "=" * 60)
    print(">>> [STARTUP] TazaKhabar backend starting...")
    print(f">>> [CONFIG] CORS origins: {settings.origins_list}")
    print(f">>> [CONFIG] LOG_LEVEL: {settings.LOG_LEVEL}")
    print(">>> [CONFIG] Database URL: {0}".format(
        settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL
    ))
    
    # Import and create database tables
    print(">>> [STARTUP] Creating database tables...")
    from src.db.database import create_all_tables
    try:
        await create_all_tables()
        print(">>> [OK] Database tables created/verified")
    except Exception as e:
        print(f">>> [ERROR] Database initialization failed: {e}")
        raise
    
    # Load embedding model at startup (CPU-bound, loaded once)
    print(">>> [STARTUP] Loading embedding model...")
    from src.services.embedding_service import get_embedding_model
    model = get_embedding_model()
    print(">>> [OK] Embedding model loaded")

    # Import and start scheduler
    print(">>> [STARTUP] Starting scraper scheduler...")
    from src.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    print(">>> [OK] Scraper scheduler started successfully")
    print("=" * 60 + "\n")
    
    yield
    
    # Shutdown
    print("\n" + "=" * 60)
    print(">>> [SHUTDOWN] TazaKhabar backend shutting down...")
    print(">>> [SHUTDOWN] Stopping scraper scheduler...")
    stop_scheduler()
    print(">>> [OK] Scraper scheduler stopped gracefully")
    print(">>> [OK] Shutdown complete")
    print("=" * 60 + "\n")


# Create FastAPI application
app = FastAPI(
    title="TazaKhabar API",
    description="Backend API for TazaKhabar news scraping service",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routers
print(">>> [SETUP] Registering API routers...")
app.include_router(jobs_router)
print("    + /api/jobs registered")
app.include_router(news_router)
print("    + /api/news registered")
app.include_router(trends_router)
print("    + /api/trends registered")
app.include_router(badge_router)
print("    + /api/badge registered")
app.include_router(refresh_router)
print("    + /api/refresh registered")
app.include_router(observation_router)
print("    + /api/observation registered")
app.include_router(resume_router)
print("    + /api/resume registered")
app.include_router(profile_router)
print("    + /api/profile registered")
app.include_router(digest_router)
print("    + /api/digest registered")

# Add CORS middleware
print(">>> [SETUP] Configuring CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)
print(">>> [OK] RequestLoggingMiddleware registered")


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
