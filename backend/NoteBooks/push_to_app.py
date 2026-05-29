"""
Call from Jupyter notebooks after writing CSV files so the FastAPI app ingests data immediately.

Usage (run backend on localhost:8000 first):

    from push_to_app import sync_jobs_to_app
    sync_jobs_to_app()

Or after each chunk save in job_scraper.ipynb:

    from push_to_app import sync_jobs_to_app
    sync_jobs_to_app()
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_BASE = os.environ.get("TAZA_API_URL", "http://localhost:8000")


def _post(path: str, timeout: int = 300) -> dict:
    url = f"{API_BASE.rstrip('/')}{path}"
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Sync failed {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach API at {url}. Start the backend: "
            "uvicorn src.main:app --reload --port 8000"
        ) from e


def sync_jobs_to_app(force: bool = False) -> dict:
    """Load jobs_output.csv into the app database now."""
    q = "?force=true" if force else ""
    result = _post(f"/api/notebooks/sync{q}")
    print(">>> [push_to_app] jobs sync:", result.get("jobs", result))
    return result


def sync_hn_to_app() -> dict:
    """Run HN scrapers (tazakhabar_scraper.ipynb equivalent) into the app DB."""
    result = _post("/api/notebooks/sync-hn", timeout=600)
    print(">>> [push_to_app] HN sync:", result)
    return result
