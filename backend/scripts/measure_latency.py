"""Measure per-request latency and CPU for the API service, old build vs new build.

    python backend/scripts/measure_latency.py
"""
from __future__ import annotations

import json
import os
import statistics
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


def tree_cpu(procs: list[psutil.Process]) -> float:
    total = 0.0
    for p in procs:
        try:
            t = p.cpu_times()
            total += t.user + t.system
        except psutil.Error:
            pass
    return total


def wait_for_health(port: int, timeout: float = 120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=10)
            if r.status_code < 500:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def run_case(name: str, cwd: Path, port: int, env_extra: dict, rounds: int = 30) -> dict:
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
    if not wait_for_health(port):
        proc.terminate()
        return {"name": name, "error": "did not become ready"}

    procs = tree(root)

    # warm up: first request may pay a cold start on the upstream backend
    for path in ("/api/jobs", "/api/news", "/api/badge"):
        try:
            requests.get(f"http://127.0.0.1:{port}{path}", timeout=120)
        except requests.RequestException:
            pass

    latencies: list[float] = []
    cpu_start = tree_cpu(procs)
    wall_start = time.time()
    for _ in range(rounds):
        for path in ("/api/jobs", "/api/badge", "/api/news"):
            t0 = time.perf_counter()
            try:
                requests.get(f"http://127.0.0.1:{port}{path}", timeout=120)
            except requests.RequestException:
                continue
            latencies.append((time.perf_counter() - t0) * 1000)
    wall = time.time() - wall_start
    cpu = tree_cpu(procs) - cpu_start
    rss = sum(p.memory_info().rss for p in procs if p.memory_info().rss)

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()

    latencies.sort()
    return {
        "name": name,
        "requests": len(latencies),
        "median_ms": round(statistics.median(latencies), 1) if latencies else None,
        "p90_ms": round(latencies[int(len(latencies) * 0.9)], 1) if latencies else None,
        "max_ms": round(latencies[-1], 1) if latencies else None,
        "cpu_ms_per_request": round(cpu * 1000 / max(len(latencies), 1), 2),
        "rss_mb": round(rss / 1024 / 1024, 1),
        "wall_seconds": round(wall, 1),
    }


def main() -> int:
    old_env = {
        "EMBEDDINGS_ENABLED": "false",
        "NOTEBOOK_SYNC_ENABLED": "false",
        "KEEPALIVE_ENABLED": "true",
        "LOG_LEVEL": "INFO",
    }
    new_env = {"EMBEDDINGS_ENABLED": "false", "LOG_LEVEL": "INFO"}

    results = []
    if (OLD_DIR / "backend").exists():
        results.append(run_case("old (git HEAD)", OLD_DIR / "backend", 8121, old_env))
    results.append(run_case("new (working tree)", REPO / "backend", 8122, new_env))

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
