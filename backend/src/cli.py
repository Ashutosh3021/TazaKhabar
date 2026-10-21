"""
CLI utilities for TazaKhabar backend.

Commands:
    python -m src.cli check-pyronites   # check the Pyronites connection
    python -m src.cli check-all         # check every external dependency
    python -m src.cli ci-run            # run the scrapers + trends (GitHub Actions)
"""
import asyncio
import sys
import argparse
from datetime import datetime

from src.config import settings


async def check_pyronites() -> int:
    """Check the Pyronites connection and report the project state."""
    print("\n" + "=" * 70)
    print("PYRONITES CONNECTION CHECK")
    print("=" * 70)
    print(f"Check timestamp: {datetime.now().isoformat()}\n")

    try:
        from src.db.pyro import get_pyro

        client = get_pyro()
        healthy = await client.healthy()
        print("  URL:      ", settings.PYRONITES_URL)
        print("  Project:  ", settings.PYRONITES_PROJECT_ID)
        print("  Health:   ", "ok" if healthy else "failed")

        tables = await client.table_names()
        print(f"  Tables:    {len(tables)}")
        for table in tables:
            print(f"    - {table}")

        print("\n" + "=" * 70)
        return 0 if healthy else 1

    except Exception as e:
        print(f"ERROR: {e}\n")
        print("=" * 70)
        return 1


async def check_llm() -> int:
    """Report whether the LLM keys are configured."""
    print("\n" + "=" * 70)
    print("LLM CONFIGURATION")
    print("=" * 70)
    groq = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_key_here")
    openrouter = bool(
        settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY != "your_key_here"
    )
    print(f"  Groq:       {'configured' if groq else 'not configured'}")
    print(f"  OpenRouter: {'configured' if openrouter else 'not configured'}")
    print("=" * 70)
    return 0 if (groq or openrouter) else 1


async def ci_run() -> int:
    """
    Scrape HN and summarize the new items. This is the GitHub Actions entrypoint
    for the 2-hour scrape cycle.
    """
    print("\n" + "=" * 70)
    print("SCRAPE RUN")
    print("=" * 70)

    from src.services.scraper_runner import run_all_scrapers_now

    results = await run_all_scrapers_now()
    for name, outcome in results.items():
        print(f"  {name:16} {outcome}")

    failed = [name for name, outcome in results.items() if not outcome.startswith("ok")]

    print("=" * 70)
    return 1 if failed else 0


async def ci_trends() -> int:
    """Recount the weekly keywords and write the market observation (daily)."""
    print("\n" + "=" * 70)
    print("TRENDS + OBSERVATION")
    print("=" * 70)

    from src.services.scraper_runner import compute_trends_and_observation

    observation = await compute_trends_and_observation()
    if observation:
        print(f"  observation: {observation[:120]}...")

    print("=" * 70)
    return 0


async def ci_embeddings() -> int:
    """Backfill the content embeddings (daily, needs sentence-transformers)."""
    print("\n" + "=" * 70)
    print("EMBEDDING BACKFILL")
    print("=" * 70)

    from src.services.embedding_service import backfill_missing_embeddings

    result = await backfill_missing_embeddings()
    print(f"  {result}")

    print("=" * 70)
    return 0


async def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TazaKhabar Backend CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.add_parser("check-pyronites", help="Check the Pyronites connection")
    subparsers.add_parser("check-llm", help="Check the LLM key configuration")
    subparsers.add_parser("check-all", help="Check every external dependency")
    subparsers.add_parser("ci-run", help="Run the scrapers (every 2 hours)")
    subparsers.add_parser("ci-trends", help="Recount trends and write the observation (daily)")
    subparsers.add_parser("ci-embeddings", help="Backfill the content embeddings (daily)")

    args = parser.parse_args()

    if args.command == "check-pyronites":
        return await check_pyronites()
    if args.command == "check-llm":
        return await check_llm()
    if args.command == "check-all":
        return max(await check_pyronites(), await check_llm())
    if args.command == "ci-run":
        return await ci_run()
    if args.command == "ci-trends":
        return await ci_trends()
    if args.command == "ci-embeddings":
        return await ci_embeddings()

    parser.print_help()
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
