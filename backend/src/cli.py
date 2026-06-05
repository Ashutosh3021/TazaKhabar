"""
CLI utilities for TazaKhabar backend.

Provides command-line tools for health checks, diagnostics, and maintenance tasks.
"""
import asyncio
import sys
import argparse
from datetime import datetime

from src.db.supabase import supabase_client
from src.config import settings


async def check_supabase():
    """Check Supabase connection status and report details."""
    print("\n" + "=" * 70)
    print("SUPABASE CONNECTION CHECK")
    print("=" * 70)
    print(f"Check timestamp: {datetime.now().isoformat()}\n")

    try:
        connection_status = await supabase_client.check_supabase_connection()

        # Storage Section
        print("📦 SUPABASE STORAGE")
        print("-" * 70)
        if connection_status['storage']['configured']:
            print(f"  Configuration: ✓ Configured")
            print(f"  URL: {settings.SUPABASE_URL}")
            print(f"  Bucket: {settings.SUPABASE_STORAGE_BUCKET}")
            if connection_status['storage']['connected']:
                print(f"  Connection: ✓ Connected")
            else:
                error_msg = connection_status['storage']['error'] or "Unknown error"
                print(f"  Connection: ✗ Failed")
                print(f"  Error: {error_msg}")
        else:
            print(f"  Configuration: ✗ Not configured")
            print("  Missing environment variables:")
            if not settings.SUPABASE_URL:
                print("    - SUPABASE_URL")
            if not settings.SUPABASE_SERVICE_ROLE_KEY:
                print("    - SUPABASE_SERVICE_ROLE_KEY")
            if not settings.SUPABASE_STORAGE_BUCKET:
                print("    - SUPABASE_STORAGE_BUCKET")
        print()

        # Email Section
        print("📧 SUPABASE EMAIL (SMTP)")
        print("-" * 70)
        if connection_status['email']['configured']:
            print(f"  Configuration: ✓ Configured")
            print(f"  SMTP Host: {settings.EMAIL_SMTP_HOST}")
            print(f"  SMTP Port: {settings.EMAIL_SMTP_PORT}")
            print(f"  SMTP User: {settings.EMAIL_SMTP_USER}")
            print(f"  From Address: {settings.SUPABASE_EMAIL_FROM}")
            if connection_status['email']['connected']:
                print(f"  Connection: ✓ Connected")
            else:
                error_msg = connection_status['email']['error'] or "Unknown error"
                print(f"  Connection: ✗ Failed")
                print(f"  Error: {error_msg}")
        else:
            print(f"  Configuration: ✗ Not configured")
            print("  Missing environment variables:")
            if not settings.EMAIL_SMTP_HOST:
                print("    - EMAIL_SMTP_HOST")
            if not settings.EMAIL_SMTP_USER:
                print("    - EMAIL_SMTP_USER")
            if not settings.EMAIL_SMTP_PASSWORD:
                print("    - EMAIL_SMTP_PASSWORD")
            if not settings.SUPABASE_EMAIL_FROM:
                print("    - SUPABASE_EMAIL_FROM")
        print()

        # Overall Status
        print("🔍 OVERALL STATUS")
        print("-" * 70)
        status_map = {
            'connected': ('✓', '🟢 CONNECTED', 'All Supabase services are connected'),
            'partial': ('⚠', '🟡 PARTIAL', 'Some Supabase services are unavailable'),
            'disconnected': ('✗', '🔴 DISCONNECTED', 'Supabase services are not connected'),
            'not_configured': ('⚠', '🟡 NOT CONFIGURED', 'Supabase is not configured')
        }
        
        symbol, status_label, description = status_map.get(
            connection_status['overall_status'],
            ('?', '❓ UNKNOWN', 'Unknown status')
        )
        
        print(f"  {status_label}")
        print(f"  {description}")
        print()

        print("=" * 70)
        return 0 if connection_status['overall_status'] == 'connected' else 1

    except Exception as e:
        print(f"❌ ERROR: {e}\n")
        print("=" * 70)
        return 1


async def check_database():
    """Check database connection status."""
    print("\n" + "=" * 70)
    print("DATABASE CONNECTION CHECK")
    print("=" * 70)
    print(f"Check timestamp: {datetime.now().isoformat()}\n")

    try:
        from sqlalchemy import text
        from src.db.database import engine
        
        print("📊 DATABASE CONFIGURATION")
        print("-" * 70)
        db_url = settings.DATABASE_URL
        # Mask sensitive parts of the URL
        if "@" in db_url:
            db_url_display = db_url.split("@")[1]
        else:
            db_url_display = db_url
        
        print(f"  Database URL: {db_url_display}")
        print()

        print("🔍 CONNECTION STATUS")
        print("-" * 70)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            print("  ✓ Connected")
            print("  ✓ Connection pool is operational")
            print()
            print("=" * 70)
            return 0
        except Exception as e:
            print(f"  ✗ Connection failed: {e}")
            print()
            print("=" * 70)
            return 1

    except Exception as e:
        print(f"❌ ERROR: {e}\n")
        print("=" * 70)
        return 1


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TazaKhabar Backend Diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.cli check-supabase    # Check Supabase connection
  python -m src.cli check-database    # Check database connection
  python -m src.cli check-all         # Check all connections
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    subparsers.add_parser('check-supabase', help='Check Supabase connection')
    subparsers.add_parser('check-database', help='Check database connection')
    subparsers.add_parser('check-all', help='Check all connections')

    args = parser.parse_args()

    if args.command == 'check-supabase':
        return await check_supabase()
    elif args.command == 'check-database':
        return await check_database()
    elif args.command == 'check-all':
        supabase_result = await check_supabase()
        db_result = await check_database()
        return max(supabase_result, db_result)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
