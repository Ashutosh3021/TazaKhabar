"""
Job feed REST API endpoint.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import optional_user
from src.db import repos
from src.db.schemas import (
    ErrorResponse,
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


def _infer_location_type(location: str) -> str:
    """Infer location type from location text."""
    loc_lower = location.lower()
    for kw in REMOTE_KEYWORDS:
        if kw in loc_lower:
            return "Remote"
    if "hybrid" in loc_lower:
        return "Hybrid"
    return "On-site"


def _infer_role_from_tags(tags: List[str]) -> str:
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
        (["mobile", "react native", "flutter"], "Mobile Dev"),
        (["qa", "test", "quality"], "QA Engineer"),
        (["security", "appsec", "infosec"], "Security"),
    ]

    for keywords, role in role_mappings:
        if any(kw in tags_str for kw in keywords):
            return role

    return "Other"


def _row_to_response(row: Dict[str, Any]) -> JobResponse:
    """Map a stored job row to the API response."""
    title = row.get("cleaned_title") or row.get("title")
    company = row.get("cleaned_company") or row.get("company")

    role = row.get("role")
    if not role and row.get("tags"):
        role = _infer_role_from_tags(row["tags"])
    if not role:
        role = "Other"

    posted_at = row.get("posted_at")
    posted_days = 0
    if posted_at:
        try:
            parsed = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            posted_days = max(0, (datetime.utcnow() - parsed).days)
        except ValueError:
            posted_days = 0

    email_contact = row.get("email_contact")
    apply_link = row.get("apply_link")

    return JobResponse(
        id=row["id"],
        title=title or "",
        role=role,
        company=company or "Unknown",
        location=row.get("location") or "N/A",
        locationType=_infer_location_type(row.get("location") or ""),
        companySize="N/A",
        salary="N/A",
        fundingStage="N/A",
        deadline=row.get("deadline"),
        skills=row.get("tags") or [],
        postedDays=posted_days,
        hiringStatus="HIRING_ACTIVE",
        saved=False,
        applied=False,
        experienceTier="I",
        emailAvailable=bool(email_contact and email_contact not in ["", "detected"]),
        applyAvailable=bool(apply_link and apply_link not in ["", "detected"]),
        applyLink=apply_link,
        description=row.get("description"),
        is_ghost_job=bool(row.get("is_ghost_job")),
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
    personalize: bool = Query(default=False),
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> PaginatedResponse[JobResponse]:
    """
    Get paginated job listings with optional filters.

    - **roles**: Filter by role keywords
    - **remote**: Filter to remote-only jobs
    - **skip**: Number of records to skip (pagination offset)
    - **limit**: Maximum records to return (max 100)
    - **personalize**: Rank by similarity to the signed-in user's profile
    """
    try:
        rows: List[Dict[str, Any]]
        personalized = False

        if personalize and user:
            rows, personalized = await _personalized_jobs(user["id"], skip, limit)

        if personalized:
            total = await repos.count_jobs(roles=roles, remote=remote)
        else:
            rows, total = await repos.list_jobs_page(
                roles=roles, remote=remote, skip=skip, limit=limit
            )

        if startup_only:
            logger.warning("startup_only filter needs a funding_stage column; ignoring")

        has_more = (skip + limit) < total
        jobs_data = [_row_to_response(r) for r in rows]

        meta_obj = PaginationMeta(
            total=total,
            skip=skip,
            limit=limit,
            has_more=has_more,
        )
        return {
            "data": jobs_data,
            "meta": {**meta_obj.model_dump(), "personalized": bool(personalized)},
        }

    except Exception as e:
        logger.exception("GET /api/jobs failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to fetch jobs", "code": "DB_ERROR", "detail": str(e)},
        )


async def _personalized_jobs(
    user_id: str, skip: int, limit: int
) -> tuple[List[Dict[str, Any]], bool]:
    """Rank jobs by cosine similarity to the user's profile embedding."""
    from src.services.embedding_service import cosine_similarity_bytes

    user_emb = await repos.get_embedding(user_id, "user_profile")
    if not user_emb:
        return [], False

    candidates = await repos.jobs_for_embedding(limit=200)
    if not candidates:
        return [], False

    candidate_ids = [c["id"] for c in candidates]
    emb_map = await repos.get_embeddings(candidate_ids, "job")

    scored: List[tuple[str, float]] = []
    for candidate in candidates:
        blob = emb_map.get(candidate["id"])
        score = cosine_similarity_bytes(user_emb, blob) if blob else 0.0
        scored.append((candidate["id"], score))

    scored.sort(key=lambda item: item[1], reverse=True)
    page_ids = [item[0] for item in scored[skip : skip + limit]]

    rows = await repos.jobs_by_ids(page_ids)
    order = {row_id: index for index, row_id in enumerate(page_ids)}
    rows.sort(key=lambda r: order.get(r["id"], 0))
    return rows, True
