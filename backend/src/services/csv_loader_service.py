"""
CSV Loader Service for loading jobs from AmbitionBox CSV files into the database.
"""
import csv
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.db import repos

logger = logging.getLogger(__name__)

# Paths to CSV files
BASE_DIR = Path(__file__).parent.parent.parent / "NoteBooks"
JOBS_CSV_PATH = BASE_DIR / "jobs_output.csv"
COMPANY_CSV_PATH = BASE_DIR / "company_data.csv"


def extract_role_from_title(title: str) -> str:
    """Extract role from job title."""
    title_lower = title.lower()
    
    role_mappings = [
        (["ml", "machine learning", "deep learning", "ai engineer"], "ML Engineer"),
        (["data science", "data scientist"], "Data Science"),
        (["gen ai", "generative ai", "gpt", "llm developer", "llm"], "Gen AI"),
        (["frontend", "front-end", "react", "vue", "angular", "ui developer"], "Frontend Dev"),
        (["backend", "back-end", "api developer", "server"], "Backend Dev"),
        (["fullstack", "full-stack", "full stack", "mern", "mean"], "Full Stack"),
        (["devops", "sre", "site reliability", "kubernetes", "docker"], "DevOps/SRE"),
        (["cloud", "aws", "azure", "gcp", "architect"], "Cloud Architect"),
        (["data engineer", "etl", "pipeline"], "Data Engineer"),
        (["data analyst", "analytics", "bi"], "Data Analyst"),
        (["product manager", "pm", "product owner"], "Product Manager"),
        (["mobile", "react native", "flutter", "ios", "android"], "Mobile Dev"),
        (["qa", "quality", "test", "testing"], "QA Engineer"),
        (["security", "appsec", "infosec", "cybersecurity"], "Security"),
        (["sap", "salesforce", "oracle", "workday"], "Enterprise Tech"),
        (["sales", "business development", "bdm"], "Sales"),
        (["marketing", "digital marketing"], "Marketing"),
        (["hr", "human resources", "recruiter"], "HR"),
        (["accountant", "finance", "financial"], "Finance"),
    ]
    
    for keywords, role in role_mappings:
        if any(kw in title_lower for kw in keywords):
            return role
    
    return "Other"


def extract_tags_from_title_and_description(title: str, description: str) -> list[str]:
    """Extract tech/role tags from title and description."""
    combined = f"{title} {description}".lower()
    
    tags = set()
    
    tech_keywords = [
        "python", "java", "javascript", "typescript", "react", "angular", "vue",
        "node", "nodejs", "django", "flask", "fastapi", "spring", "rails",
        "aws", "azure", "gcp", "cloud", "docker", "kubernetes", "k8s",
        "sql", "mysql", "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
        "machine learning", "ml", "ai", "deep learning", "nlp", "llm", "gpt",
        "sap", "salesforce", "oracle", "workday", "service now", "servicenow",
        "terraform", "ansible", "jenkins", "ci/cd", "github", "gitlab",
        "html", "css", "tailwind", "redux", "graphql", "rest", "api",
        "agile", "scrum", "jira", "linux", "unix", "shell",
    ]
    
    for tag in tech_keywords:
        if tag in combined:
            tags.add(tag.title() if len(tag) > 3 else tag.upper())
    
    return list(tags)[:10]  # Limit to 10 tags


def infer_location_type(location: str) -> str:
    """Infer location type from location string."""
    if not location:
        return "Unknown"
    
    loc_lower = location.lower()
    
    remote_keywords = ["remote", "work from home", "wfh", "anywhere", "virtual"]
    if any(kw in loc_lower for kw in remote_keywords):
        return "Remote"
    
    hybrid_keywords = ["hybrid", "partially remote"]
    if any(kw in loc_lower for kw in hybrid_keywords):
        return "Hybrid"
    
    return "On-site"


async def load_jobs_from_csv(
    limit: int | None = None,
    clear_existing: bool = False,
    start_row: int = 0,
) -> dict[str, Any]:
    """
    Load jobs from jobs_output.csv into the store.

    Args:
        limit: Maximum number of jobs to load (None = all)
        clear_existing: Whether to clear existing jobs before loading
        start_row: Skip this many data rows (for incremental notebook sync)

    Returns:
        Dict with success count and errors
    """
    if not JOBS_CSV_PATH.exists():
        logger.error(f"Jobs CSV not found: {JOBS_CSV_PATH}")
        return {"success": 0, "errors": ["CSV file not found"], "total": 0}

    logger.info(f"Loading jobs from {JOBS_CSV_PATH}")

    if clear_existing:
        removed = await repos.delete_all_jobs()
        logger.info("Cleared %s existing jobs", removed)

    loaded_count = 0
    skipped_count = 0
    error_count = 0
    errors: list[str] = []

    known = await repos.existing_job_triples()
    now = datetime.utcnow().isoformat()
    new_rows: list[dict[str, Any]] = []

    try:
        with open(JOBS_CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader):
                if i < start_row:
                    skipped_count += 1
                    continue
                if limit is not None and loaded_count >= limit:
                    break

                try:
                    title = (row.get("Job Title") or "").strip()
                    company = (row.get("Company Name") or "").strip()
                    location = (row.get("Location") or "").strip()
                    apply_link = (row.get("Apply Link") or "").strip()
                    description = (row.get("Job Description") or "").strip()[:1000]

                    if not title or not company:
                        continue

                    triple = (title, company, apply_link)
                    if triple in known:
                        loaded_count += 1
                        continue

                    role = extract_role_from_title(title)
                    tags = extract_tags_from_title_and_description(title, description)

                    new_rows.append(
                        {
                            "id": uuid.uuid4().hex,
                            "hn_item_id": None,
                            "title": title,
                            "company": company,
                            "location": location,
                            "tags": tags,
                            "apply_link": apply_link or None,
                            "email_contact": None,
                            "is_ghost_job": False,
                            "deadline": None,
                            "posted_at": now,
                            "scraped_at": now,
                            "cleaned_title": title,
                            "cleaned_company": company,
                            "role": role,
                            "description": description,
                            "processed": True,
                        }
                    )
                    known.add(triple)
                    loaded_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(f"Row {i}: {str(e)}")
                    logger.warning(f"Error loading job row {i}: {e}")

        if new_rows:
            await repos.insert_rows("jobs", new_rows)

    except Exception as e:
        logger.error(f"Error loading CSV: {e}")
        return {"success": loaded_count, "errors": [str(e)], "total": 0}

    logger.info(
        "CSV loading complete: %s loaded, %s skipped, %s errors",
        loaded_count,
        skipped_count,
        error_count,
    )
    return {
        "success": loaded_count,
        "skipped": skipped_count,
        "start_row": start_row,
        "errors": errors,
        "total": loaded_count + error_count,
    }


async def get_csv_stats() -> dict[str, Any]:
    """Get statistics about the CSV files."""
    stats = {
        "jobs_csv_exists": JOBS_CSV_PATH.exists(),
        "company_csv_exists": COMPANY_CSV_PATH.exists(),
        "jobs_count": 0,
        "companies_count": 0,
        "sample_jobs": [],
    }
    
    if JOBS_CSV_PATH.exists():
        with open(JOBS_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            jobs = list(reader)
            stats["jobs_count"] = len(jobs)
            # Get sample of first 5 jobs
            stats["sample_jobs"] = [
                {
                    "title": j.get("Job Title", "")[:50],
                    "company": j.get("Company Name", ""),
                    "location": j.get("Location", ""),
                    "apply_link": bool(j.get("Apply Link", "")),
                }
                for j in jobs[:5]
            ]
    
    if COMPANY_CSV_PATH.exists():
        with open(COMPANY_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            stats["companies_count"] = len(list(reader))
    
    return stats


# Run if executed directly
if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("=== CSV Loader Service ===")
        
        # Get stats
        stats = await get_csv_stats()
        print(f"\nCSV Stats:")
        print(f"  Jobs CSV exists: {stats['jobs_csv_exists']}")
        print(f"  Jobs count: {stats['jobs_count']}")
        print(f"  Company CSV exists: {stats['company_csv_exists']}")
        print(f"  Companies count: {stats['companies_count']}")
        
        if stats['sample_jobs']:
            print(f"\nSample Jobs:")
            for job in stats['sample_jobs']:
                print(f"  - {job['title']} @ {job['company']}")
        
        # Load jobs (load all rows; previously limited to 100)
        print(f"\nLoading all jobs into database...")
        result = await load_jobs_from_csv(limit=None, clear_existing=True)
        # BUG FIX [L1]: removed hardcoded limit to load full CSV instead of only first 100 rows
        print(f"Result: {result['success']} jobs loaded, {len(result['errors'])} errors")
        
    asyncio.run(main())
