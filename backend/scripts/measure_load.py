"""Measure the CPU and memory load of the API service, old build vs new build.

The old build is the code at git HEAD (SQLite + APScheduler + keepalive + file
logging). The new build is the current working tree (Pyronites only, no
scheduler, no disk writes).

    python backend/scripts/measure_load.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests

REPO = Path(__file__).resolve().parents[2]
OLD_DIR = Path(r"C:\Users\ashut\AppData\Local\Temp\opencode\old")
PY = sys.executable


def tree(proc: psutil.Process) -> list[psutil.Process]:
    procs = [proc]
    try:
        procs += proc.children(recursive=True)
    except psutil.Error:
        pass
    return procs


def tree_rss(procs: list[psutil.Process]) -> int:
    total = 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return total


def tree_cpu(procs: list[psutil.Process]) -> float:
    total = 0.0
    for p in procs:
        try:
            t = p.cpu_times()
            total += t.user + t.system
        except psutil.Error:
            pass
    return total


def wait_for_health(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)
            if r.status_code < 500:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def run_case(name: str, cwd: Path, port: int, env_extra: dict, rounds: int = 20) -> dict:
    env = {**os.environ, **env_extra}
    env["PYTHONPATH"] = str(cwd)
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    root = psutil.Process(proc.pid)
    ready = wait_for_health(port)
    if not ready:
        proc.terminate()
        return {"name": name, "error": "did not become ready"}

    time.sleep(5)
    procs = tree(root)
    idle_cpu = tree_cpu(procs)
    idle_rss = tree_rss(procs)
    peak_rss = idle_rss

    start_cpu = tree_cpu(procs)
    start = time.time()
    for _ in range(rounds):
        for path in ("/api/jobs", "/api/badge", "/api/news"):
            try:
                requests.get(f"http://127.0.0.1:{port}{path}", timeout=20)
            except requests.RequestException:
                pass
        peak_rss = max(peak_rss, tree_rss(procs))
    wall = time.time() - start
    time.sleep(2)
    end_cpu = tree_cpu(procs)
    peak_rss = max(peak_rss, tree_rss(procs))

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()

    load_cpu = end_cpu - start_cpu
    return {
        "name": name,
        "ready": ready,
        "processes": len(procs),
        "idle_rss_mb": round(idle_rss / 1024 / 1024, 1),
        "peak_rss_mb": round(peak_rss / 1024 / 1024, 1),
        "idle_cpu_seconds": round(idle_cpu, 2),
        "load_cpu_seconds": round(load_cpu, 2),
        "load_wall_seconds": round(wall, 1),
        "requests": rounds * 3,
    }


def main() -> int:
    results = []

    old_env = {
        # the values render.yaml shipped for the old build
        "EMBEDDINGS_ENABLED": "false",
        "NOTEBOOK_SYNC_ENABLED": "false",
        "KEEPALIVE_ENABLED": "true",
        "KEEPALIVE_INTERVAL_SEC": "840",
        "LOG_LEVEL": "INFO",
    }
    new_env = {
        "EMBEDDINGS_ENABLED": "false",
        "LOG_LEVEL": "INFO",
    }

    if (OLD_DIR / "backend").exists():
        results.append(run_case("old (git HEAD, prod settings)", OLD_DIR / "backend", 8111, old_env))
    results.append(run_case("new (working tree)", REPO / "backend", 8112, new_env))

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
