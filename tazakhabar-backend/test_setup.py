"""
Test script to verify all components are working correctly.
Run with: python test_setup.py
"""
import asyncio
import sys


async def test_csv_loader():
    """Test CSV loader service."""
    print("\n" + "="*60)
    print("TEST 1: CSV Loader Service")
    print("="*60)
    
    from src.services.csv_loader_service import get_csv_stats, load_jobs_from_csv
    
    # Get CSV stats
    stats = await get_csv_stats()
    print(f"Jobs CSV exists: {stats['jobs_csv_exists']}")
    print(f"Jobs count: {stats['jobs_count']}")
    print(f"Company CSV exists: {stats['company_csv_exists']}")
    print(f"Companies count: {stats['companies_count']}")
    
    if stats['sample_jobs']:
        print("\nSample jobs:")
        for job in stats['sample_jobs'][:3]:
            print(f"  - {job['title']} @ {job['company']}")
    
    return stats['jobs_count'] > 0


async def fix_database_schema():
    """Fix database schema for new columns."""
    print("\n[Fixing database schema...]")
    from src.db.database import engine
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        # Check if table exists and its schema
        try:
            result = await conn.execute(text("PRAGMA table_info(jobs)"))
            columns = {row[1]: row for row in result.fetchall()}
            
            # If hn_item_id exists and is NOT NULL (type contains INTEGER NOT NULL)
            if 'hn_item_id' in columns:
                col_info = columns['hn_item_id']
                # col_info: (cid, name, type, notnull, dflt_value, pk)
                # notnull = 1 means NOT NULL
                if col_info[3] == 1:  # notnull is 1
                    # SQLite doesn't support ALTER COLUMN, so we need to recreate table
                    print("  Recreating jobs table to fix hn_item_id nullable...")
                    
                    # Rename old table
                    await conn.execute(text("ALTER TABLE jobs RENAME TO jobs_old"))
                    
                    # Create new table with nullable hn_item_id
                    await conn.execute(text("""
                        CREATE TABLE jobs (
                            id VARCHAR(36) PRIMARY KEY,
                            hn_item_id INTEGER,
                            title VARCHAR(500) NOT NULL,
                            company VARCHAR(200) NOT NULL,
                            location VARCHAR(200) NOT NULL DEFAULT 'N/A',
                            tags JSON NOT NULL DEFAULT '[]',
                            email_contact VARCHAR(500),
                            apply_link VARCHAR(1000),
                            is_ghost_job INTEGER NOT NULL DEFAULT 0,
                            deadline VARCHAR(50),
                            posted_at TIMESTAMP NOT NULL,
                            scraped_at TIMESTAMP NOT NULL,
                            report_version VARCHAR(10) NOT NULL DEFAULT '2',
                            cleaned_title VARCHAR(500),
                            cleaned_company VARCHAR(200),
                            role VARCHAR(100),
                            description TEXT,
                            processed INTEGER NOT NULL DEFAULT 0
                        )
                    """))
                    
                    # Copy data from old table
                    await conn.execute(text("""
                        INSERT INTO jobs (id, hn_item_id, title, company, location, tags, email_contact, apply_link, is_ghost_job, deadline, posted_at, scraped_at, report_version, cleaned_title, cleaned_company, processed)
                        SELECT id, hn_item_id, title, company, location, tags, email_contact, apply_link, is_ghost_job, deadline, posted_at, scraped_at, report_version, cleaned_title, cleaned_company, processed
                        FROM jobs_old
                    """))
                    
                    # Drop old table
                    await conn.execute(text("DROP TABLE jobs_old"))
                    print("  Fixed: jobs table recreated with nullable hn_item_id")
            
            # Add role column if missing
            if 'role' not in columns:
                await conn.execute(text("ALTER TABLE jobs ADD COLUMN role VARCHAR(100)"))
                print("  Added: role column")
            
            # Add description column if missing
            if 'description' not in columns:
                await conn.execute(text("ALTER TABLE jobs ADD COLUMN description TEXT"))
                print("  Added: description column")
                
        except Exception as e:
            print(f"  Schema check: {e}")
    
    print("[Schema fix complete]")


async def test_database():
    """Test database and models."""
    print("\n" + "="*60)
    print("TEST 2: Database & Models")
    print("="*60)
    
    from src.db.database import create_all_tables
    from src.db.models import Job
    from sqlalchemy import inspect
    
    # Create tables (will also migrate)
    await create_all_tables()
    print("Database tables created/verified")
    
    # Check Job model columns
    from src.db import models
    job_columns = [c.name for c in models.Job.__table__.columns]
    print(f"Job model columns: {', '.join(job_columns)}")
    
    # Verify new columns exist
    required_cols = ['role', 'description', 'hn_item_id']
    for col in required_cols:
        if col in job_columns:
            print(f"  [OK] {col} column exists")
        else:
            print(f"  [FAIL] {col} column MISSING")
            return False
    
    return True


async def test_qa_api():
    """Test Q&A API endpoints."""
    print("\n" + "="*60)
    print("TEST 3: Q&A API")
    print("="*60)
    
    from src.api.qa import router
    
    # List all routes
    routes = [r.path for r in router.routes]
    print(f"Q&A routes: {routes}")
    
    required_routes = [
        'profile',
        'matches', 
        'market-velocity',
        'network-influence',
        'action-required',
        'chat'
    ]
    
    for route in required_routes:
        exists = any(route in r for r in routes)
        if exists:
            print(f"  [OK] /{route}")
        else:
            print(f"  [FAIL] /{route} MISSING")
            return False
    
    return True


async def test_trends():
    """Test trends service."""
    print("\n" + "="*60)
    print("TEST 4: Trends Service")
    print("="*60)
    
    from src.services.trend_service import (
        TECH_KEYWORDS,
        DECLINING_KEYWORDS,
        _get_sample_trends_with_roles,
        _get_declining_roles_sample
    )
    
    print(f"TECH_KEYWORDS count: {len(TECH_KEYWORDS)}")
    print(f"DECLINING_KEYWORDS count: {len(DECLINING_KEYWORDS)}")
    
    # Test sample data
    sample = _get_sample_trends_with_roles()
    booming = [s for s in sample if s['direction'] == 'booming']
    declining = [s for s in sample if s['direction'] == 'declining']
    
    print(f"Sample booming roles: {[s['skill'] for s in booming]}")
    print(f"Sample declining roles: {[s['skill'] for s in declining]}")
    
    return True


async def test_csv_to_db():
    """Test loading CSV to database."""
    print("\n" + "="*60)
    print("TEST 5: CSV to Database Load")
    print("="*60)
    
    from src.services.csv_loader_service import load_jobs_from_csv
    from src.db.database import async_session
    from sqlalchemy import select, func
    from src.db.models import Job
    
    # Load first 10 jobs
    result = await load_jobs_from_csv(limit=10, clear_existing=True)
    print(f"Loaded: {result['success']} jobs")
    print(f"Errors: {len(result['errors'])}")
    
    # Count jobs in DB
    async with async_session() as session:
        count_result = await session.execute(select(func.count(Job.id)))
        db_count = count_result.scalar()
        print(f"Jobs in database: {db_count}")
        
        # Get sample job
        job_result = await session.execute(select(Job).limit(1))
        job = job_result.scalar_one_or_none()
        
        if job:
            print(f"\nSample job from DB:")
            print(f"  Title: {job.title}")
            print(f"  Company: {job.company}")
            print(f"  Role: {job.role}")
            print(f"  Location: {job.location}")
            print(f"  Apply Link: {'Yes' if job.apply_link else 'No'}")
    
    return result['success'] > 0


async def test_api_endpoints():
    """Test all API endpoints are registered."""
    print("\n" + "="*60)
    print("TEST 6: API Endpoints")
    print("="*60)
    
    from src.main import app
    
    all_routes = [r.path for r in app.routes]
    
    required_apis = [
        '/api/jobs',
        '/api/news',
        '/api/trends',
        '/api/profile',
        '/api/resume/analyse',
        '/api/digest',
        '/api/csv/stats',
        '/api/csv/load-jobs',
        '/api/qa/profile',
        '/api/qa/matches',
        '/api/qa/market-velocity',
        '/api/qa/network-influence',
        '/api/qa/action-required',
        '/api/qa/chat',
    ]
    
    all_ok = True
    for api in required_apis:
        # Check if route exists
        exists = any(api in r for r in all_routes)
        status = "[OK]" if exists else "[FAIL]"
        print(f"  {status} {api}")
        if not exists:
            all_ok = False
    
    return all_ok


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("TAZAKHABAR VERIFICATION TEST")
    print("="*60)
    
    # Fix database schema first
    await fix_database_schema()
    
    tests = [
        ("CSV Loader", test_csv_loader),
        ("Database & Models", test_database),
        ("Q&A API", test_qa_api),
        ("Trends Service", test_trends),
        ("CSV to DB", test_csv_to_db),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\nERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}]: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! System is ready.")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Please check errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
