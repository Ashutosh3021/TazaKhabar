import logging
import sys
import time
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.config import settings


def setup_logging(log_level: str | None = None) -> logging.Logger:
    """
    Configure Python logging module with file and console handlers.
    
    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to settings.LOG_LEVEL.
    
    Returns:
        Configured logger instance.
    """
    if log_level is None:
        log_level = settings.LOG_LEVEL
    
    # Ensure logs directory exists
    settings.LOG_DIR.mkdir(exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        handlers=[
            logging.FileHandler(settings.LOG_DIR / "tazakhabar.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    
    logger = logging.getLogger("tazakhabar")
    logger.info(f"Logging initialized at {log_level} level")
    return logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests with method, path, status, and duration."""

    # Paths to log at DEBUG level instead of INFO (to suppress noise in production)
    _SILENT_PATHS: frozenset[str] = frozenset({"/health", "/", "/favicon.ico"})

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger = logging.getLogger("tazakhabar")

        path = request.url.path
        msg = (
            f"{request.method} {path} "
            f"status={response.status_code} duration_ms={duration_ms:.2f}"
        )

        if path in self._SILENT_PATHS:
            # Health-check and root pings: only visible at DEBUG level
            logger.debug(msg)
        else:
            logger.info(msg)
        
        return response
