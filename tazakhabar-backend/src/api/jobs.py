"""
Job feed REST API endpoint.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.models import Job
from src.db.schemas import (
    ErrorResponse,
    JobFilterParams,
    JobResponse,
    PaginatedResponse,
    PaginationMeta,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Role-to-keyword mapping for filters
ROLE_KEYWORDS = {
    "AI/ML": ["machine learning", "ml", "ai", "deep learning", "nlp", "llm", "gpt", "artificial intelligence", "data science", "neural", "tensorflow", "pytorch", "reinforcement"],
    "Frontend": ["frontend", "front-end", "react", "vue", "angular", "ui", "ux", "css", "javascript", "typescript", "next.js", "svelte"],
    "Backend": ["backend", "back-end", "api", "server", "database", "postgres", "postgresql", "node", "python", "go", "rust", "java", "golang"],
    "Fullstack": ["fullstack", "full-stack", "full stack", "mern", "mean", "全栈"],
}

STARTUP_KEYWORDS = ["series a", "series b", "series c", "series d", "seed", "stealth", "y combinator", "yc", "startup"]
REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "anywhere", "distributed"]


def _job_matches_role(job_tags: list[str], role: str) -> bool:
    """Check if job tags match a role's keywords."""
    keywords = ROLE_KEYWORDS.get(role, [])
    tags_lower = [t.lower() for t in job_tags]
    return any(kw.lower() in tags_lower for kw in keywords)


def _infer_location_type(location: str) -> str:
    """Infer location type from location text."""
    loc_lower = location.lower()
    for kw in REMOTE_KEYWORDS:
        if kw in loc_lower:
            return "Remote"
    if "hybrid" in loc_lower:
        return "Hybrid"
    return "On-site"


def _row_to_response(row: Job) -> JobResponse:
    """Map SQLAlchemy Job row to JobResponse."""
    # Use cleaned data if available, otherwise fallback to raw
    title = row.cleaned_title if row.cleaned_title else row.title
    company = row.cleaned_company if row.cleaned_company else row.company
    
    return JobResponse(
        id=row.id,
        title=title,
        role=",".join(row.tags) if row.tags else "N/A",
        company=company,
        location=row.location or "N/A",
        locationType=_infer_location_type(row.location or ""),
        companySize="N/A",
        salary="N/A",
        fundingStage="N/A",
        deadline=row.deadline,
        skills=row.tags or [],
        postedDays=max(0, (datetime.utcnow() - row.posted_at).days),
        hiringStatus="HIRING_ACTIVE",
        saved=False,
        applied=False,
        experienceTier="I",
        emailAvailable=bool(row.email_contact),
        applyAvailable=bool(row.apply_link),
    )


@router.get(
    "",
    response_model=PaginatedResponse[JobResponse],
    responses={500: {"model": ErrorResponse}},
)
async def get_jobs(
    roles: list[str] = Query(default=[]),
    remote: bool = Query(default=False),
    startup_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[JobResponse]:
    """
    Get paginated job listings with optional filters.

    - **roles**: Filter by role keywords (AI/ML, Frontend, Backend, Fullstack)
    - **remote**: Filter to remote-only jobs
    - **startup_only**: Filter to startup-stage companies (requires funding_stage field)
    - **skip**: Number of records to skip (pagination offset)
    - **limit**: Maximum records to return (max 100)
    """
    try:
        print(f"\n>>> [API:GET /api/jobs] Request received")
        print(f"    Filters -> roles: {roles}, remote: {remote}, startup_only: {startup_only}")
        print(f"    Pagination -> skip: {skip}, limit: {limit}")
        
        # Build base filter — only active report version
        base_filter = Job.report_version == "2"
        print(f"    Filter: report_version = '2'")

        # Remote filter (AND) — apply at DB level using LIKE
        if remote:
            remote_conditions = [Job.location.ilike(f"%{kw}%") for kw in REMOTE_KEYWORDS]
            base_filter = base_filter & or_(*remote_conditions)
            print(f"    Filter: remote jobs (location matches: {REMOTE_KEYWORDS})")

        # Build count query
        count_query = select(func.count(Job.id)).where(base_filter)
        count_result = await db.execute(count_query)
        db_total = count_result.scalar() or 0
        print(f"    DB total count: {db_total} jobs")

        # Build data query with ordering and pagination
        query = (
            select(Job)
            .where(base_filter)
            .order_by(Job.scraped_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        rows = result.scalars().all()
        print(f"    DB returned: {len(rows)} jobs")

        # Apply role filter in Python (OR within roles)
        # NOTE: SQL applied skip/limit before this. For correct has_more, use db_total
        # (all rows matching DB filters, before Python filtering). This means when role
        # filters are applied, has_more may overcount — acceptable for MVP.
        if roles:
            filtered = [r for r in rows if any(_job_matches_role(r.tags or [], role) for role in roles)]
            print(f"    After role filter ({roles}): {len(filtered)} jobs")
        else:
            filtered = rows

        # Apply startup filter (deferred — requires funding_stage column)
        if startup_only:
            print(f"    WARNING: startup_only filter requires 'funding_stage' column (not yet added)")

        # has_more uses db_total (correct for unfiltered results; may overcount with role filters)
        jobs_data = [_row_to_response(r) for r in filtered]
        has_more = (skip + limit) < db_total
        
        print(f">>> [API:GET /api/jobs] Response: {len(jobs_data)} jobs (total: {db_total}, has_more: {has_more})")

        return PaginatedResponse(
            data=jobs_data,
            meta=PaginationMeta(
                total=db_total,
                skip=skip,
                limit=limit,
                has_more=has_more,
            ),
        )

    except Exception as e:
        print(f">>> [API:GET /api/jobs] ERROR: {e}")
        import traceback
        print(f">>> [API:GET /api/jobs] TRACE: {traceback.format_exc()}")
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch jobs", "code": "DB_ERROR", "detail": str(e)},
        )
