"""
Sync data written by Jupyter notebooks in backend/NoteBooks/ into the app database.

Workflow:
  scrapper.ipynb       → company_data.csv   (input for job scraper; not loaded to DB)
  job_scraper.ipynb    → jobs_output.csv    → auto-loaded into `jobs` table
  tazakhabar_scraper   → HN scrapers via API or same DB when notebook uses src.db.*

A background task polls CSV mtimes while the backend runs.
Notebooks can also call POST /api/notebooks/sync for immediate ingest.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import settings
from src.services.csv_loader_service import (
    COMPANY_CSV_PATH,
    JOBS_CSV_PATH,
    get_csv_stats,
    load_jobs_from_csv,
)

logger = logging.getLogger(__name__)

NOTEBOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "NoteBooks"
STATE_PATH = NOTEBOOKS_DIR / ".notebook_sync_state.json"

_watcher_task: asyncio.Task | None = None
_sync_lock = asyncio.Lock()


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _count_csv_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    import csv

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        return sum(1 for _ in reader)


async def sync_jobs_csv(force: bool = False) -> dict[str, Any]:
    """
    Load new rows from jobs_output.csv into the database.

    Uses file mtime + row count to only process appended rows when possible.
    """
    key = "jobs_output.csv"
    if not JOBS_CSV_PATH.exists():
        return {"source": key, "status": "skipped", "reason": "file not found"}

    async with _sync_lock:
        stat = JOBS_CSV_PATH.stat()
        mtime_ns = stat.st_mtime_ns
        row_count = _count_csv_data_rows(JOBS_CSV_PATH)

        state = _load_state()
        prev = state.get(key, {})
        prev_mtime = prev.get("mtime_ns")
        prev_rows = int(prev.get("row_count", 0))

        if not force and mtime_ns == prev_mtime and row_count == prev_rows:
            return {
                "source": key,
                "status": "unchanged",
                "csv_rows": row_count,
                "db_rows_synced": prev_rows,
            }

        # Appended rows during a long job_scraper run
        start_row = 0
        if not force and prev_mtime is not None and row_count > prev_rows:
            start_row = prev_rows
        elif not force and prev_mtime is not None and row_count < prev_rows:
            # CSV was rewritten — re-import from start (upsert handles updates)
            start_row = 0
            logger.info("jobs_output.csv shrank or was replaced; full re-sync")

        result = await load_jobs_from_csv(start_row=start_row, clear_existing=False)
        result.update(
            {
                "source": key,
                "status": "synced",
                "csv_rows": row_count,
                "start_row": start_row,
                "synced_at": datetime.utcnow().isoformat(),
            }
        )

        state[key] = {
            "mtime_ns": mtime_ns,
            "row_count": row_count,
            "last_sync": result["synced_at"],
            "last_loaded": result.get("success", 0),
        }
        _save_state(state)
        logger.info(
            "Notebook sync %s: %s rows in CSV, started at row %s, loaded %s",
            key,
            row_count,
            start_row,
            result.get("success", 0),
        )
        return result


async def sync_all_notebook_outputs(force: bool = False) -> dict[str, Any]:
    """Sync every notebook artifact the app understands."""
    jobs = await sync_jobs_csv(force=force)
    stats = await get_csv_stats()
    return {
        "status": "ok",
        "jobs": jobs,
        "csv_stats": stats,
        "notebooks_dir": str(NOTEBOOKS_DIR),
        "paths": {
            "jobs_output": str(JOBS_CSV_PATH),
            "company_data": str(COMPANY_CSV_PATH),
        },
    }


async def get_notebook_sync_status() -> dict[str, Any]:
    """Status for API / debugging."""
    state = _load_state()
    stats = await get_csv_stats()
    jobs_stat = JOBS_CSV_PATH.stat() if JOBS_CSV_PATH.exists() else None
    return {
        "watch_enabled": settings.NOTEBOOK_SYNC_ENABLED,
        "poll_interval_sec": settings.NOTEBOOK_SYNC_INTERVAL_SEC,
        "csv_stats": stats,
        "sync_state": state,
        "jobs_csv_mtime": (
            datetime.utcfromtimestamp(jobs_stat.st_mtime).isoformat() if jobs_stat else None
        ),
    }


async def _watch_loop() -> None:
    interval = max(5, settings.NOTEBOOK_SYNC_INTERVAL_SEC)
    logger.info("Notebook CSV watcher started (every %ss)", interval)
    while True:
        try:
            await sync_all_notebook_outputs(force=False)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Notebook sync poll failed: %s", e)
        await asyncio.sleep(interval)


def start_notebook_watcher() -> None:
    """Start background polling for notebook CSV changes."""
    global _watcher_task
    if not settings.NOTEBOOK_SYNC_ENABLED:
        logger.info("Notebook CSV watcher disabled (NOTEBOOK_SYNC_ENABLED=false)")
        return
    if _watcher_task and not _watcher_task.done():
        return
    _watcher_task = asyncio.create_task(_watch_loop(), name="notebook_csv_watcher")


async def stop_notebook_watcher() -> None:
    global _watcher_task
    if _watcher_task and not _watcher_task.done():
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass
    _watcher_task = None
