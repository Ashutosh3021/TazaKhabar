"""
Job feed REST API endpoint.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Header
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
    "ML Engineer": ["machine learning", "ml", "ai", "deep learning", "nlp", "llm", "gpt", "artificial intelligence", "tensorflow", "pytorch", "reinforcement", "mle"],
    "Data Science": ["data science", "data scientist", "data analysis", "analytics", "statistical"],
    "Gen AI": ["gen ai", "generative ai", "gpt", "openai", "chatgpt", "prompt"],
    "Frontend Dev": ["frontend", "front-end", "react", "vue", "angular", "ui", "ux", "css", "javascript", "typescript", "next.js", "svelte"],
    "Backend Dev": ["backend", "back-end", "api", "server", "database", "postgres", "postgresql", "node", "python", "go", "rust", "java", "golang"],
    "Full Stack": ["fullstack", "full-stack", "full stack", "mern", "mean", "全栈"],
    "DevOps/SRE": ["devops", "sre", "site reliability", "kubernetes", "docker", "terraform", "ansible"],
    "Cloud Architect": ["cloud", "aws", "azure", "gcp", "cloud architect", "solution architect"],
    "Data Engineer": ["data engineer", "etl", "pipeline", "airflow", "dbt", "data pipeline"],
    "Data Analyst": ["data analyst", "analytics", "excel", "bi", "tableau", "visualization"],
    "Product Manager": ["product manager", "pm", "product owner", "product management"],
    "Mobile Dev": ["mobile", "react native", "flutter", "ios", "android", "mobile developer"],
    "QA Engineer": ["qa", "quality", "test", "testing", "automation test", "selenium", "cypress"],
    "Security": ["security", "appsec", "infosec", "cybersecurity", "security engineer"],
}

STARTUP_KEYWORDS = ["series a", "series b", "series c", "series d", "seed", "stealth", "y combinator", "yc", "startup"]
REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "anywhere", "distributed"]


def _job_matches_role(job_tags: list[str], job_role: str | None, role: str) -> bool:
    """Check if job tags or role match a role's keywords."""
    # First check if the job's LLM-extracted role matches directly
    if job_role and role.lower() in job_role.lower():
        return True
    
    # Then check keywords in tags
    keywords = ROLE_KEYWORDS.get(role, [])
    if not keywords:
        return False
    
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
    
    # Use LLM-extracted role if available, otherwise try to infer from tags
    role = row.role
    if not role and row.tags:
        role = _infer_role_from_tags(row.tags)
    if not role:
        role = "Other"
    
    return JobResponse(
        id=row.id,
        title=title,
        role=role,
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
        emailAvailable=bool(row.email_contact and row.email_contact not in ["", "detected"]),
        applyAvailable=bool(row.apply_link and row.apply_link not in ["", "detected"]),
        applyLink=row.apply_link,  # Direct apply link from CSV
        description=row.description,  # Include job description from CSV
    )


def _infer_role_from_tags(tags: list[str]) -> str:
    """Infer standardized role from job tags."""
    if not tags:
        return "Other"
    
    tags_lower = [t.lower() for t in tags]
    tags_str = " ".join(tags_lower)
    
    role_mappings = [
        (["ml", "machine learning", "deep learning", "ai", "nlp", "llm"], "ML Engineer"),
        (["data science", "data scientist", "data analysis"], "Data Science"),
        (["gen ai", "generative ai", "gpt", "llm"], "Gen AI"),
        (["frontend", "react", "vue", "angular", "ui"], "Frontend Dev"),
        (["backend", "api", "server", "database", "postgres"], "Backend Dev"),
        (["fullstack", "full-stack", "mern", "mean"], "Full Stack"),
        (["devops", "sre", "kubernetes", "docker"], "DevOps/SRE"),
        (["cloud", "aws", "azure", "gcp"], "Cloud Architect"),
        (["data engineer", "etl", "pipeline"], "Data Engineer"),
        (["data analyst", "analytics", "excel"], "Data Analyst"),
        (["product manager", "pm"], "Product Manager"),
        (["mobile", "react native", "flutter", "ios", "android"], "Mobile Dev"),
        (["qa", "test", "quality"], "QA Engineer"),
        (["security", "appsec", "infosec"], "Security"),
    ]
    
    for keywords, role in role_mappings:
        if any(kw in tags_str for kw in keywords):
            return role
    
    return "Other"


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
    personalize: bool = Query(default=False),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
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

        # Apply role filter at SQL level (BUG FIX [M10])
        role_filter_applied = False
        role_conditions = []
        if roles:
            for r in roles:
                role_conditions.append(Job.role.ilike(f"%{r}%"))
            if role_conditions:
                base_filter = base_filter & or_(*role_conditions)
                role_filter_applied = True
                print(f"    Applied SQL role filter: {roles}")

        # Build count query AFTER all filters (so has_more is correct)
        count_query = select(func.count()).select_from(select(Job).where(base_filter).subquery())
        count_result = await db.execute(count_query)
        db_total = count_result.scalar() or 0
        print(f"    DB total count after filters: {db_total} jobs")

        # Personalization path
        personalized = False
        if personalize and x_user_id:
            try:
                from src.db.models import Embedding
                from src.services.embedding_service import cosine_similarity_bytes

                # Fetch user embedding
                user_emb_row = await db.execute(
                    select(Embedding).where(
                        Embedding.item_type == "user_profile",
                        Embedding.item_id == x_user_id,
                    )
                )
                user_emb = user_emb_row.scalar_one_or_none()

                if user_emb and user_emb.embedding:
                    # Candidate selection (recent up to 200)
                    candidate_query = select(Job.id).where(base_filter).order_by(Job.scraped_at.desc()).limit(200)
                    cand_res = await db.execute(candidate_query)
                    candidate_ids = [r[0] for r in cand_res.all()]

                    if candidate_ids:
                        emb_rows = await db.execute(
                            select(Embedding).where(
                                Embedding.item_type == "job",
                                Embedding.item_id.in_(candidate_ids),
                            )
                        )
                        emb_list = emb_rows.scalars().all()
                        emb_map = {e.item_id: e.embedding for e in emb_list}

                        # Score candidates
                        scored = []
                        for jid in candidate_ids:
                            emb = emb_map.get(jid)
                            score = cosine_similarity_bytes(user_emb.embedding, emb) if emb is not None else 0.0
                            scored.append((jid, score))

                        scored.sort(key=lambda x: x[1], reverse=True)

                        # Paginate scored list
                        total_scored = len(scored)
                        page_slice = scored[skip: skip + limit]
                        page_ids = [str(jid) for jid, _ in page_slice]
                        has_more = (skip + limit) < total_scored

                        # Fetch jobs by page_ids preserving order
                        if page_ids:
                            q = select(Job).where(Job.id.in_(page_ids))
                            rows_res = await db.execute(q)
                            rows_map = {r.id: r for r in rows_res.scalars().all()}
                            rows = [rows_map[jid] for jid in page_ids if jid in rows_map]
                        else:
                            rows = []

                        personalized = True
                    else:
                        # No candidates found, fall back to normal SQL pagination
                        personalized = False
                else:
                    personalized = False
            except Exception as e:
                logger.warning(f"Personalization failed, falling back to default ordering: {e}")
                personalized = False

        if not personalize or not personalized:
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
            has_more = (skip + limit) < db_total

        # Apply startup filter (deferred — requires funding_stage column)
        if startup_only:
            print(f"    WARNING: startup_only filter requires 'funding_stage' column (not yet added)")

        jobs_data = [_row_to_response(r) for r in rows]

        # Include personalization flag in meta for client awareness (BUG FIX [M10])
        meta_obj = PaginationMeta(
            total=db_total,
            skip=skip,
            limit=limit,
            has_more=has_more,
        )
        # Return as dict to allow adding 'personalized' flag into meta
        return {
            "data": jobs_data,
            "meta": {**meta_obj.__dict__, "personalized": bool(personalized)},
        }

    except Exception as e:
        print(f">>> [API:GET /api/jobs] ERROR: {e}")
        import traceback
        print(f">>> [API:GET /api/jobs] TRACE: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch jobs", "code": "DB_ERROR", "detail": str(e)},
        )
