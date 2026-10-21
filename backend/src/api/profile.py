"""
User profile API endpoint.
GET /api/profile — Get the signed-in user's profile with ATS data.
POST /api/profile — Create or update the signed-in user's profile.

Identity comes from the Pyronites session, never from a client supplied header.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import require_user
from src.db import repos
from src.db.schemas import ProfileResponse, ProfileUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _to_response(profile: Dict[str, Any] | None) -> ProfileResponse:
    if not profile:
        return ProfileResponse()
    return ProfileResponse(
        id=profile.get("id"),
        name=profile.get("name"),
        email=profile.get("email"),
        roles=profile.get("roles") or [],
        experience_level=profile.get("experience_level") or "I",
        ats_score=profile.get("ats_score"),
        ats_critical_issues=profile.get("ats_critical_issues") or [],
        ats_missing_keywords=profile.get("ats_missing_keywords") or [],
        ats_suggested_additions=profile.get("ats_suggested_additions") or [],
        last_analysis_at=profile.get("last_analysis_at"),
        resume_text_length=len(profile.get("resume_text") or "") or None,
        resume_path=profile.get("resume_path"),
        preferences=profile.get("preferences") or {},
    )


@router.get("", response_model=ProfileResponse)
async def get_profile(user: Dict[str, Any] = Depends(require_user)) -> ProfileResponse:
    """Return the profile of the signed-in user, empty when not set up yet."""
    profile = await repos.get_profile(user["id"])
    return _to_response(profile)


@router.post("", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdateRequest,
    user: Dict[str, Any] = Depends(require_user),
) -> ProfileResponse:
    """Create or update the signed-in user's profile."""
    updates: Dict[str, Any] = {
        "name": data.name,
        "email": data.email or user.get("email"),
        "roles": data.roles,
        "experience_level": data.experience_level,
        "resume_path": data.resume_path,
        "preferences": data.preferences or {},
    }
    profile = await repos.save_profile(user["id"], updates)
    logger.info("Profile updated for user=%s", user["id"])
    return _to_response(profile)
