import logging
import sys
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

from src.config import settings
from src.api import jobs_router, news_router, trends_router, badge_router, refresh_router, observation_router, resume_router, profile_router, digest_router, csv_loader_router, qa_router
from src.api import embeddings_router, scrape_router, notebooks_router
from src.middleware.logging import RequestLoggingMiddleware

# Ensure log directory exists before FileHandler is created (Render filesystem starts empty)
try:
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # Fall back to stdout-only logging if we can't create the directory
    pass

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(settings.LOG_DIR / "tazakhabar.log")),
    ],
)
logger = logging.getLogger(__name__)

def _derive_keepalive_url() -> str:
    if settings.KEEPALIVE_URL:
        return settings.KEEPALIVE_URL.strip()
    if settings.RENDER_EXTERNAL_URL:
        return settings.RENDER_EXTERNAL_URL.rstrip("/") + "/health"
    return ""

async def _keepalive_loop(stop_event: asyncio.Event) -> None:
    url = _derive_keepalive_url()
    if not url:
        logger.warning("KEEPALIVE_ENABLED=true but no KEEPALIVE_URL / RENDER_EXTERNAL_URL set; keep-alive disabled")
        return

    interval = max(60, int(settings.KEEPALIVE_INTERVAL_SEC))
    logger.info("Keep-alive enabled: pinging %s every %ss", url, interval)

    timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while not stop_event.is_set():
            try:
                r = await client.get(url, headers={"User-Agent": "tazakhabar-keepalive/1.0"})
                logger.info("Keep-alive ping: %s -> %s", url, r.status_code)
            except Exception as e:
                logger.warning("Keep-alive ping failed (%s): %s", url, e)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass


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

    # Check Supabase connection
    print(">>> [STARTUP] Checking Supabase connection...")
    from src.db.supabase import supabase_client
    try:
        connection_status = await supabase_client.check_supabase_connection()
        
        # Storage status
        if connection_status['storage']['configured']:
            if connection_status['storage']['connected']:
                print(">>> [OK] Supabase storage: Connected")
            else:
                error_msg = connection_status['storage']['error'] or "Unknown error"
                print(f">>> [WARN] Supabase storage: Not connected - {error_msg}")
        else:
            print(">>> [WARN] Supabase storage: Not configured (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, or SUPABASE_STORAGE_BUCKET missing)")
        
        # Email status
        if connection_status['email']['configured']:
            if connection_status['email']['connected']:
                print(">>> [OK] Supabase email (SMTP): Connected")
            else:
                error_msg = connection_status['email']['error'] or "Unknown error"
                print(f">>> [WARN] Supabase email (SMTP): Not connected - {error_msg}")
        else:
            print(">>> [WARN] Supabase email (SMTP): Not configured (EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD, or SUPABASE_EMAIL_FROM missing)")
        
        # Overall status
        overall_msg = {
            'connected': 'Supabase connected successfully',
            'partial': 'Supabase partially connected (some services unavailable)',
            'disconnected': 'Supabase connection failed',
            'not_configured': 'Supabase not configured'
        }
        print(f">>> [SUPABASE] {overall_msg.get(connection_status['overall_status'], 'Unknown status')}")
    except Exception as e:
        print(f">>> [ERROR] Supabase connection check failed: {e}")
        logger.exception("Supabase connection check error")
    
    # Load embedding model at startup (CPU-bound, loaded once)
    if settings.EMBEDDINGS_ENABLED:
        print(">>> [STARTUP] Loading embedding model...")
        from src.services.embedding_service import get_embedding_model
        model = get_embedding_model()
        print(">>> [OK] Embedding model loaded")
    else:
        print(">>> [STARTUP] Embeddings disabled (EMBEDDINGS_ENABLED=false)")

    # Notebook pipeline: jobs_output.csv → database (also polled in background)
    print(">>> [STARTUP] Syncing notebook CSV outputs...")
    try:
        from src.services.notebook_sync_service import (
            start_notebook_watcher,
            sync_all_notebook_outputs,
        )

        sync_result = await sync_all_notebook_outputs(force=False)
        jobs = sync_result.get("jobs", {})
        print(
            f">>> [NOTEBOOK] jobs_output.csv → DB: status={jobs.get('status')}, "
            f"loaded={jobs.get('success', 0)}"
        )
        start_notebook_watcher()
        print(">>> [OK] Notebook CSV watcher started")
    except Exception as e:
        print(f">>> [NOTEBOOK] Warning: Could not sync notebook CSVs: {e}")

    # Import and start scheduler
    print(">>> [STARTUP] Starting scraper scheduler...")
    from src.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    print(">>> [OK] Scraper scheduler started successfully")

    # Optional keep-alive loop (Render free tier warm-up)
    keepalive_stop: asyncio.Event | None = None
    keepalive_task: asyncio.Task | None = None
    if settings.KEEPALIVE_ENABLED:
        keepalive_stop = asyncio.Event()
        keepalive_task = asyncio.create_task(_keepalive_loop(keepalive_stop))
    print("=" * 60 + "\n")
    
    yield
    
    # Shutdown
    print("\n" + "=" * 60)
    print(">>> [SHUTDOWN] TazaKhabar backend shutting down...")
    print(">>> [SHUTDOWN] Stopping scraper scheduler...")
    stop_scheduler()
    from src.services.notebook_sync_service import stop_notebook_watcher

    await stop_notebook_watcher()

    if keepalive_stop is not None:
        keepalive_stop.set()
    if keepalive_task is not None:
        try:
            await keepalive_task
        except Exception:
            logger.exception("Keep-alive task failed during shutdown")
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
    """
    Health check endpoint for Railway deployment.
    
    Returns:
        dict: Health status with timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/")
async def root():
    """Root endpoint - returns API info."""
    return {
        "name": "TazaKhabar API",
        "version": "1.0.0",
        "status": "running",
    }
