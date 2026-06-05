"""
Entry point for running TazaKhabar backend CLI commands.

Usage:
    python -m backend check-supabase    # Check Supabase connection
    python -m backend check-database    # Check database connection
    python -m backend check-all         # Check all connections

Or from the backend directory:
    python -m src.cli check-supabase
    python -m src.cli check-database
    python -m src.cli check-all
"""
import asyncio
import sys

# Add the backend directory to the path
sys.path.insert(0, '.')

from src.cli import main

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
