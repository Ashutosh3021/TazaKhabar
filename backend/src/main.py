import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api import jobs_router, news_router, trends_router, badge_router, observation_router, resume_router, profile_router, digest_router, csv_loader_router, qa_router
from src.api import embeddings_router, scrape_router, notebooks_router, health_router, scraper_status_router
from src.api import auth_router
from src.middleware.logging import RequestLoggingMiddleware

# Configure logging. Render captures stdout, so the app never writes to its own
# disk: the free tier disk is small and the data now lives in Pyronites.
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    print("\n" + "=" * 60)
    print(">>> [STARTUP] TazaKhabar backend starting...")
    print(f">>> [CONFIG] CORS origins: {settings.origins_list}")
    print(f">>> [CONFIG] LOG_LEVEL: {settings.LOG_LEVEL}")
    print(f">>> [CONFIG] Pyronites project: {settings.PYRONITES_PROJECT_ID}")

    # Check the Pyronites connection: without it there is no data and no auth.
    try:
        from src.db.pyro import get_pyro

        if await get_pyro().healthy():
            print(">>> [OK] Pyronites connection healthy")
        else:
            logger.warning("Pyronites health check did not report ok")
    except Exception as e:
        logger.warning(f"Pyronites connection check failed: {e}")

    # Load the embedding model when enabled (CPU-bound, loaded once).
    if settings.EMBEDDINGS_ENABLED:
        print(">>> [STARTUP] Loading embedding model...")
        try:
            from src.services.embedding_service import get_embedding_model

            get_embedding_model()
            print(">>> [OK] Embedding model loaded")
        except Exception as e:
            logger.warning(f"Embedding model could not be loaded: {e}")
    else:
        print(">>> [STARTUP] Embeddings disabled (EMBEDDINGS_ENABLED=false)")

    print("=" * 60 + "\n")

    yield

    print("\n" + "=" * 60)
    print(">>> [SHUTDOWN] TazaKhabar backend shutting down")
    print("=" * 60 + "\n")


# Create FastAPI application
app = FastAPI(
    title="TazaKhabar API",
    description="Backend API for TazaKhabar news scraping service",
    version="2.0.0",
    lifespan=lifespan,
)

# Include API routers
print(">>> [SETUP] Registering API routers...")
app.include_router(auth_router)
print("    + /api/auth registered")
app.include_router(jobs_router)
print("    + /api/jobs registered")
app.include_router(news_router)
print("    + /api/news registered")
app.include_router(trends_router)
print("    + /api/trends registered")
app.include_router(badge_router)
print("    + /api/badge registered")
app.include_router(observation_router)
print("    + /api/observation registered")
app.include_router(resume_router)
print("    + /api/resume registered")
app.include_router(profile_router)
print("    + /api/profile registered")
app.include_router(digest_router)
print("    + /api/digest registered")
app.include_router(csv_loader_router)
print("    + /api/csv registered")
app.include_router(qa_router)
print("    + /api/qa registered")
app.include_router(embeddings_router)
print("    + /api/embeddings registered")
app.include_router(scrape_router)
print("    + /api/scrape registered")
app.include_router(notebooks_router)
print("    + /api/notebooks registered")
app.include_router(health_router)
print("    + /health registered")
app.include_router(scraper_status_router)
print("    + /api/scrapers registered")

# Add CORS middleware — must be registered BEFORE other middleware so it wraps all requests.
# Starlette applies middleware in reverse registration order (last added = outermost),
# so we add CORS first to ensure it runs outermost and handles OPTIONS preflight.
print(">>> [SETUP] Configuring CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)
print(">>> [OK] RequestLoggingMiddleware registered")


@app.get("/health")
async def health_check():
    """Health check used by the Render health check."""
    from src.db.pyro import get_pyro

    healthy = False
    try:
        healthy = await get_pyro().healthy()
    except Exception as e:
        logger.warning(f"Health check failed: {e}")

    return {
        "status": "healthy" if healthy else "degraded",
        "database": healthy,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/")
async def root():
    """Root endpoint - returns API info."""
    return {
        "name": "TazaKhabar API",
        "version": "2.0.0",
        "status": "running",
    }
