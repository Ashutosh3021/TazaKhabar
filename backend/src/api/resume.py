"""
Resume analysis API endpoint.
POST /api/resume/analyse — Upload resume, get ATS score and suggestions.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.api.deps import require_user
from src.db import repos
from src.db.pyro import get_pyro
from src.db.schemas import ResumeAnalyseResponse
from src.services.llm_service import check_rate_limit, increment_rate_limit
from src.services.resume_service import (
    analyze_resume_ats,
    extract_keywords_from_resume,
    extract_text,
    generate_suggested_additions,
    chunk_resume_sections,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
REANALYSIS_GAP = timedelta(days=30)
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}


@router.post("/analyse", response_model=ResumeAnalyseResponse)
async def analyse_resume(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_user),
) -> ResumeAnalyseResponse:
    """
    Analyze a resume and return ATS score, critical issues, and keyword suggestions.

    - PDF and TXT files only, max 5MB
    - Rate limited per verified user
    - Re-analysis blocked within 30 days
    """
    user_id = user["id"]

    # 1. Rate limit
    allowed, retry_after = await check_rate_limit(user_id)
    if not allowed:
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
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Please upload PDF or TXT.",
        )

    # 3. Read and size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File exceeds 5MB limit. Please reduce file size.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    # 4. Re-analysis cooldown
    profile = await repos.get_profile(user_id)
    last_analysis = (profile or {}).get("last_analysis_at")
    if last_analysis:
        try:
            previous = datetime.fromisoformat(str(last_analysis).replace("Z", "+00:00"))
            if previous.tzinfo is not None:
                previous = previous.astimezone(timezone.utc).replace(tzinfo=None)
            gap = datetime.utcnow() - previous
            if gap < REANALYSIS_GAP:
                days_left = (REANALYSIS_GAP - gap).days
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": f"Re-analysis available in {days_left} days",
                        "code": "REANALYSIS_COOLDOWN",
                        "days_remaining": days_left,
                    },
                )
        except ValueError:
            pass

    # 5. Extract text
    filename = file.filename or "resume"
    try:
        text = await extract_text(content, filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not text or len(text.strip()) < 50:
        raise HTTPException(
            status_code=422,
            detail="Resume text too short to analyze. Please ensure the file contains readable text.",
        )

    # 6. Count the request before the LLM call
    await increment_rate_limit(user_id)

    # 7. ATS scoring
    ats_result = await analyze_resume_ats(text)

    # 8. Keywords
    resume_keywords = await extract_keywords_from_resume(text)

    # 9. Trending keywords for suggestions
    user_roles = (profile or {}).get("roles") or []
    sections = chunk_resume_sections(text)

    from src.services.trend_service import get_trends

    booming_keywords: list[str] = []
    try:
        trending = await get_trends(limit=20)
        booming = [t.get("skill", "").lower() for t in trending if t.get("direction") == "booming"]
        booming_keywords = booming[:20] if booming else [t.get("skill", "").lower() for t in trending][:20]
    except Exception:
        logger.warning("Could not load trending keywords for suggestions")

    # 10. Suggested additions
    suggested = await generate_suggested_additions(
        resume_keywords=resume_keywords,
        user_roles=user_roles,
        booming_keywords=booming_keywords,
        resume_sections=sections,
    )
    missing_lower = {k.lower() for k in ats_result["missing_keywords"]}
    suggested = [s for s in suggested if s.lower() not in missing_lower]

    # 11. Store the resume and the analysis on the profile
    resume_path = None
    try:
        uploaded = await get_pyro().upload(filename, content, content_type)
        resume_path = uploaded.get("id") or uploaded.get("path")
    except Exception as exc:
        logger.warning("Resume upload to Pyronites storage failed: %s", exc)

    await repos.save_profile(
        user_id,
        {
            "resume_path": resume_path,
            "resume_text": text,
            "ats_score": ats_result["score"],
            "ats_critical_issues": ats_result["critical_issues"],
            "ats_missing_keywords": ats_result["missing_keywords"],
            "ats_suggested_additions": suggested,
            "last_analysis_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 12. Refresh the user embedding in the background
    try:
        import asyncio

        from src.services.embedding_service import generate_user_embedding

        asyncio.get_running_loop().create_task(
            generate_user_embedding(
                user_id=user_id,
                roles=user_roles,
                experience=(profile or {}).get("experience_level") or "I",
                resume_text=text,
                preferences=(profile or {}).get("preferences") or {},
            )
        )
    except Exception as exc:
        logger.warning("Could not schedule user embedding refresh: %s", exc)

    return ResumeAnalyseResponse(
        ats_score=ats_result["score"],
        critical_issues=ats_result["critical_issues"],
        missing_keywords=ats_result["missing_keywords"],
        suggested_additions=suggested,
        resume_text_length=len(text),
    )
