"""Measure the CPU cost of one full scrape cycle, the work that used to run on
Render and now runs in GitHub Actions.

    python backend/scripts/measure_scrape.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))


def clear_thread_state() -> None:
    """Forget the last Who Is Hiring thread so the full parse runs."""
    from src.db.pyro import get_pyro

    async def run() -> None:
        client = get_pyro()
        await client.exec("DELETE FROM \"scraper_state\" WHERE state_key = 'last_wih_thread'")

    asyncio.run(run())


def main() -> int:
    clear_thread_state()

    from src.cli import main as cli_main

    sys.argv = ["src.cli", "ci-run"]
    t0 = os.times()
    start = time.time()
    rc = asyncio.run(cli_main())
    wall = time.time() - start
    t1 = os.times()

    cpu = (t1.user - t0.user) + (t1.system - t0.system)
    cycles_per_day = 12  # one cycle every 2 hours

    print(
        json.dumps(
            {
                "exit_code": rc,
                "wall_seconds": round(wall, 1),
                "cpu_seconds": round(cpu, 1),
                "cpu_pct_of_one_core_during_run": round(cpu / wall * 100, 1),
                "cycles_per_day": cycles_per_day,
                "cpu_seconds_per_day": round(cpu * cycles_per_day, 1),
                "avg_cpu_pct_of_one_core_over_day": round(
                    cpu * cycles_per_day / 86400 * 100, 2
                ),
                "render_free_tier_cpu_budget_pct": round(
                    cpu * cycles_per_day / 86400 / 0.1 * 100, 1
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
