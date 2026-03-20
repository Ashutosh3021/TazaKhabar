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
    return JobResponse(
        id=row.id,
        title=row.title,
        role=",".join(row.tags) if row.tags else "N/A",
        company=row.company,
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
        # Build base filter — only active report version
        base_filter = Job.report_version == "1"

        # Remote filter (AND) — apply at DB level using LIKE
        if remote:
            remote_conditions = [Job.location.ilike(f"%{kw}%") for kw in REMOTE_KEYWORDS]
            base_filter = base_filter & or_(*remote_conditions)

        # Build count query
        count_query = select(func.count(Job.id)).where(base_filter)
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

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

        # Apply role filter in Python (OR within roles)
        filtered = rows
        if roles:
            filtered = [r for r in filtered if any(_job_matches_role(r.tags or [], role) for role in roles)]

        # Apply startup filter in Python (AND) — requires funding_stage field in Job model
        # Note: startup_only filter is non-functional until Job model has funding_stage column
        if startup_only:
            # Deferred: add funding_stage to Job model in future phase
            # Placeholder: pass through all results
            pass

        # Adjust total to filtered count for accurate pagination
        total = len(filtered)
        jobs_data = [_row_to_response(r) for r in filtered]
        has_more = (skip + limit) < total

        return PaginatedResponse(
            data=jobs_data,
            meta=PaginationMeta(
                total=total,
                skip=skip,
                limit=limit,
                has_more=has_more,
            ),
        )

    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch jobs", "code": "DB_ERROR", "detail": str(e)},
        )
