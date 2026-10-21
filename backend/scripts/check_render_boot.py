"""Boot the app exactly like Render does and probe it.

    <python> backend/scripts/check_render_boot.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
PORT = 8199


def main() -> int:
    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
        "AUTH_COOKIE_SECURE": "true",
        "AUTH_COOKIE_SAMESITE": "none",
        "ALLOWED_ORIGINS": "https://tazakhabar.vercel.app",
        "EMBEDDINGS_ENABLED": "false",
        "LOG_LEVEL": "INFO",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    ready = False
    deadline = time.time() + 120
    while time.time() < deadline:
        if proc.poll() is not None:
            print("process exited early:")
            print(proc.stdout.read() if proc.stdout else "")
            return 1
        try:
            if requests.get(f"http://127.0.0.1:{PORT}/health", timeout=10).status_code < 500:
                ready = True
                break
        except requests.RequestException:
            pass
        time.sleep(2)

    if not ready:
        proc.terminate()
        print("did not become ready")
        return 1

    print("health   ->", requests.get(f"http://127.0.0.1:{PORT}/health", timeout=60).text)
    jobs = requests.get(f"http://127.0.0.1:{PORT}/api/jobs?limit=2", timeout=60).json()
    print(f"jobs     -> total={jobs['meta']['total']} returned={len(jobs['data'])}")
    news = requests.get(f"http://127.0.0.1:{PORT}/api/news?limit=2", timeout=60).json()
    print(f"news     -> total={news['meta']['total']} returned={len(news['data'])}")
    badge = requests.get(f"http://127.0.0.1:{PORT}/api/badge", timeout=60).json()
    print("badge    ->", badge)
    profile = requests.get(f"http://127.0.0.1:{PORT}/api/profile", timeout=60)
    print(f"profile  -> HTTP {profile.status_code} (401 expected without a session)")
    trends = requests.get(f"http://127.0.0.1:{PORT}/api/trends", timeout=120)
    print(f"trends   -> HTTP {trends.status_code} {trends.text[:80]}")

    proc.terminate()
    try:
        out = proc.stdout.read() if proc.stdout else ""
    except Exception:
        out = ""
    print("\n--- server log ---")
    print("\n".join(out.splitlines()[-15:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
