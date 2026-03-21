"""
Resume analysis API endpoint.
POST /api/resume/analyse — Upload resume, get ATS score and suggestions.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.database import async_session
from src.db.models import User
from src.db.schemas import ResumeAnalyseResponse
from src.services.llm_service import check_rate_limit, increment_rate_limit
from src.services.resume_service import (
    analyze_resume_ats,
    extract_keywords_from_resume,
    extract_text,
    generate_suggested_additions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
REANALYSIS_GAP = timedelta(days=30)
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


@router.post("/analyse", response_model=ResumeAnalyseResponse)
async def analyse_resume(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> ResumeAnalyseResponse:
    """
    Analyze a resume and return ATS score, critical issues, and keyword suggestions.

    - PDF and TXT files only, max 5MB
    - Rate limited: 5/day anonymous, 20/day registered
    - Re-analysis blocked within 30 days
    """
    print(f"\n>>> [API:POST /api/resume/analyse] File: {file.filename}, user: {x_user_id}")

    # 1. Check rate limit
    allowed, retry_after = await check_rate_limit(x_user_id)
    if not allowed:
        print(f">>> [API:POST /api/resume/analyse] Rate limit exceeded")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # 2. Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        print(f">>> [API:POST /api/resume/analyse] Unsupported content type: {content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Please upload PDF or TXT.",
        )

    # 3. Read and size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        print(f">>> [API:POST /api/resume/analyse] File too large: {len(content)} bytes")
        raise HTTPException(
            status_code=400,
            detail="File exceeds 5MB limit. Please reduce file size.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # 4. Check 30-day re-analysis gate
    if x_user_id:
        async with async_session() as session:
            stmt = select(User).where(User.id == x_user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user and user.last_analysis_at:
                gap = datetime.utcnow() - user.last_analysis_at
                if gap < REANALYSIS_GAP:
                    days_left = (REANALYSIS_GAP - gap).days
                    print(f">>> [API:POST /api/resume/analyse] Re-analysis cooldown: {days_left} days left")
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": f"Re-analysis available in {days_left} days",
                            "code": "REANALYSIS_COOLDOWN",
                            "days_remaining": days_left,
                        },
                    )

    # 5. Extract text
    filename = file.filename or "resume"
    try:
        text = await extract_text(content, filename)
    except ValueError as e:
        print(f">>> [API:POST /api/resume/analyse] Extraction failed: {e}")
        raise HTTPException(status_code=422, detail=str(e))

    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Resume text too short to analyze. Please ensure the file contains readable text.",
        )

    print(f">>> [API:POST /api/resume/analyse] Extracted {len(text)} chars from {filename}")

    # 6. Increment rate limit BEFORE LLM call
    await increment_rate_limit(x_user_id)

    # 7. ATS scoring
    ats_result = await analyze_resume_ats(text)
    print(f">>> [API:POST /api/resume/analyse] ATS score: {ats_result['score']}")

    # 8. Extract keywords
    resume_keywords = await extract_keywords_from_resume(text)
    print(f">>> [API:POST /api/resume/analyse] Resume keywords found: {len(resume_keywords)}")

    # 9. Get user roles and booming keywords for suggestions
    user_roles = []
    if x_user_id:
        async with async_session() as session:
            stmt = select(User).where(User.id == x_user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user_roles = user.roles or []

    # Use top TECH_KEYWORDS as booming keywords proxy
    from src.services.trend_service import TECH_KEYWORDS

    # 10. Generate suggested additions
    suggested = await generate_suggested_additions(
        resume_keywords=resume_keywords,
        user_roles=user_roles,
        booming_keywords=TECH_KEYWORDS[:20],
    )
    print(f">>> [API:POST /api/resume/analyse] Suggestions: {suggested}")

    # 11. Store in user profile if user_id provided
    if x_user_id:
        async with async_session() as session:
            stmt = select(User).where(User.id == x_user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                user.resume_text = text
                user.ats_score = ats_result["score"]
                user.ats_critical_issues = ats_result["critical_issues"]
                user.ats_missing_keywords = ats_result["missing_keywords"]
                user.ats_suggested_additions = suggested
                user.last_analysis_at = datetime.utcnow()
                await session.commit()
                print(f">>> [API:POST /api/resume/analyse] Stored in user profile")
            else:
                print(f">>> [API:POST /api/resume/analyse] User not found in DB, skipping storage")

    return ResumeAnalyseResponse(
        ats_score=ats_result["score"],
        critical_issues=ats_result["critical_issues"],
        missing_keywords=ats_result["missing_keywords"],
        suggested_additions=suggested,
        resume_text_length=len(text),
    )
