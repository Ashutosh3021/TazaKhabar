"""
Q&A API endpoints for career bot functionality.
- Job role matching based on user profile and resume
- Market velocity for user's skills
- Network influence score
- Chat with LLM about career
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import optional_user, require_user
from src.db import repos
from src.services.llm_service import check_and_increment, check_rate_limit, generate_with_retry
from src.services.trend_service import TECH_KEYWORDS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qa", tags=["qa"])

# Chat limit per verified user per day.
CHAT_DAILY_LIMIT = 20


# ============================================================================
# Helper Functions
# ============================================================================


async def get_user_profile(user_id: str | None) -> Dict[str, Any]:
    """Get user profile data for the signed-in user."""
    if not user_id:
        return {}

    profile = await repos.get_profile(user_id)
    if not profile:
        return {}

    return {
        "name": profile.get("name"),
        "roles": profile.get("roles") or [],
        "experience_level": profile.get("experience_level"),
        "ats_score": profile.get("ats_score"),
        "ats_critical_issues": profile.get("ats_critical_issues") or [],
        "ats_missing_keywords": profile.get("ats_missing_keywords") or [],
        "ats_suggested_additions": profile.get("ats_suggested_additions") or [],
        "resume_text": profile.get("resume_text"),
        "preferences": profile.get("preferences") or {},
    }


def calculate_skill_match(user_skills: list[str], job_tags: list[str]) -> float:
    """Calculate match percentage between user skills and job requirements."""
    if not user_skills or not job_tags:
        return 0.0

    user_skills_lower = [s.lower() for s in user_skills]
    job_tags_lower = [t.lower() for t in job_tags]

    matches = sum(1 for skill in job_tags_lower if any(skill in ts or ts in skill for ts in user_skills_lower))
    return min(100, (matches / len(job_tags)) * 100)


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/profile")
async def get_qa_profile(user: Optional[Dict[str, Any]] = Depends(optional_user)) -> dict:
    """Get user profile data for the Q&A page."""
    profile = await get_user_profile(user.get("id") if user else None)

    if not profile:
        return {
            "has_profile": False,
            "message": "No profile found. Please complete onboarding and upload resume.",
        }

    return {
        "has_profile": True,
        "name": profile.get("name"),
        "roles": profile.get("roles", []),
        "experience_level": profile.get("experience_level"),
        "ats_score": profile.get("ats_score"),
        "has_resume": bool(profile.get("resume_text")),
        "suggested_skills": profile.get("ats_suggested_additions", []),
        "missing_skills": profile.get("ats_missing_keywords", []),
    }


@router.get("/matches")
async def get_role_matches(
    limit: int = 5,
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> dict:
    """Get job role recommendations based on the user profile and resume."""
    profile = await get_user_profile(user.get("id") if user else None)

    if not profile or not profile.get("roles"):
        return {
            "matches": [],
            "message": "No profile found. Please complete onboarding.",
        }

    user_roles = profile.get("roles", [])
    user_skills = profile.get("ats_suggested_additions", []) + profile.get("ats_missing_keywords", [])
    experience_level = profile.get("experience_level", "I")

    role_counts = await repos.role_counts()

    matches = []
    for role, count in role_counts:
        if not role or role == "Other":
            continue

        role_lower = role.lower()
        role_match = 0
        for user_role in user_roles:
            if user_role.lower() in role_lower or role_lower in user_role.lower():
                role_match = 90
                break

        exp_bonus = 5 if experience_level in ["II", "III"] else 0
        match_score = min(100, role_match + exp_bonus)

        if match_score > 0 or count > 5:
            sample_job = await repos.sample_job_for_role(role)
            skills = (sample_job or {}).get("tags") or []
            matches.append(
                {
                    "role": role,
                    "match_percentage": match_score,
                    "job_count": count,
                    "skills": skills[:5],
                    "why": f"Based on your profile as {'/'.join(user_roles[:2])}, this role has {count} open positions.",
                    "locked": match_score < 70,
                }
            )

    matches.sort(key=lambda x: x["match_percentage"], reverse=True)

    return {
        "matches": matches[:limit],
        "total_available": len(matches),
    }


@router.get("/market-velocity")
async def get_market_velocity(
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> dict:
    """Get market velocity (demand) for the user's skills."""
    profile = await get_user_profile(user.get("id") if user else None)

    user_skills = profile.get("ats_suggested_additions", []) + profile.get("ats_missing_keywords", [])
    if not user_skills:
        user_skills = TECH_KEYWORDS[:10]

    velocity_data = []
    for skill in user_skills[:5]:
        count = await repos.count_jobs_matching(skill)
        velocity = min(30, count * 0.5)
        velocity_data.append(
            {
                "skill": skill,
                "demand_count": count,
                "velocity": round(velocity, 1),
                "trend": "up" if velocity > 10 else "stable",
            }
        )

    velocity_data.sort(key=lambda x: x["velocity"], reverse=True)
    total_velocity = sum(v["velocity"] for v in velocity_data) / max(len(velocity_data), 1)

    return {
        "overall_velocity": round(total_velocity, 1),
        "skills": velocity_data,
        "region": "EMEA",
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/network-influence")
async def get_network_influence(
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> dict:
    """Calculate the user's network influence based on profile and resume."""
    profile = await get_user_profile(user.get("id") if user else None)

    if not profile:
        return {"score": 0, "percentile": "N/A", "factors": []}

    score = 0
    factors = []

    ats_score = profile.get("ats_score", 0)
    if ats_score:
        ats_points = min(30, ats_score * 0.3)
        score += ats_points
        factors.append(
            {
                "name": "Resume Quality",
                "value": f"+{int(ats_points)} pts",
                "description": f"ATS Score: {ats_score}/100",
            }
        )

    exp_level = profile.get("experience_level", "I")
    exp_mapping = {"I": 5, "II": 15, "III": 20, "IV": 25}
    exp_points = exp_mapping.get(exp_level, 5)
    score += exp_points
    factors.append(
        {
            "name": "Experience Level",
            "value": f"+{exp_points} pts",
            "description": f"Level {exp_level}",
        }
    )

    skills_count = len(profile.get("ats_suggested_additions", []) + profile.get("ats_missing_keywords", []))
    skill_points = min(25, skills_count * 5)
    score += skill_points
    factors.append(
        {
            "name": "Skill Diversity",
            "value": f"+{skill_points} pts",
            "description": f"{skills_count} skills identified",
        }
    )

    if profile.get("resume_text"):
        resume_len = len(profile["resume_text"])
        resume_points = min(20, resume_len // 500)
        score += resume_points
        factors.append(
            {
                "name": "Profile Completeness",
                "value": f"+{resume_points} pts",
                "description": f"Resume: {resume_len} chars",
            }
        )

    percentile = (
        "TOP 5%" if score >= 70 else "TOP 15%" if score >= 50 else "TOP 30%" if score >= 30 else "N/A"
    )

    return {"score": score, "percentile": percentile, "factors": factors}


@router.post("/chat")
async def chat_with_bot(
    message: dict,
    user: Dict[str, Any] = Depends(require_user),
) -> dict:
    """
    Chat with the career bot. The LLM answers using the signed-in user's profile.

    Rate limited per verified user.
    """
    user_message = message.get("message", "")
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is required")

    allowed, retry_after = await check_rate_limit(user["id"])
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily chat limit reached",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    profile = await get_user_profile(user["id"])

    context_parts = []
    if profile:
        if profile.get("name"):
            context_parts.append(f"User: {profile['name']}")
        if profile.get("roles"):
            context_parts.append(f"Target Roles: {', '.join(profile['roles'])}")
        if profile.get("experience_level"):
            context_parts.append(f"Experience Level: {profile['experience_level']}")
        if profile.get("ats_score"):
            context_parts.append(f"Resume ATS Score: {profile['ats_score']}")
        if profile.get("ats_suggested_additions"):
            context_parts.append(f"Skills to Add: {', '.join(profile['ats_suggested_additions'][:5])}")

    context = "\n".join(context_parts) if context_parts else "No profile data available"

    system_prompt = """You are TazaKhabar's Career Bot - an AI career advisor.
Your role is to help users find the best job roles based on their profile, resume, and market trends.
Be concise, actionable, and supportive. Use bullet points when giving recommendations.
Keep responses focused on career advice, job matching, and skill development.
Never make up specific job numbers or salaries - use general terms instead."""

    user_prompt = f"""Context:
{context}

User Question: {user_message}

Provide a helpful career-focused response:"""

    await check_and_increment(user["id"])

    try:
        response = await generate_with_retry(user_prompt, system_prompt)
        return {
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=502, detail="The career bot is unavailable right now.")


@router.get("/action-required")
async def get_action_required(
    user: Optional[Dict[str, Any]] = Depends(optional_user),
) -> dict:
    """Get the skills and actions the user needs to improve their profile."""
    profile = await get_user_profile(user.get("id") if user else None)

    if not profile:
        return {"actions": [], "message": "No profile found"}

    actions = []

    missing_skills = profile.get("ats_missing_keywords", [])
    if missing_skills:
        actions.append(
            {
                "type": "skill",
                "priority": "high",
                "title": f"Add '{missing_skills[0]}' Skills",
                "description": f"Your resume is missing '{missing_skills[0]}' which is commonly requested.",
                "action_text": "GO TO VERIFICATION",
                "link": "/profile",
            }
        )

    critical_issues = profile.get("ats_critical_issues", [])
    if critical_issues:
        actions.append(
            {
                "type": "resume_fix",
                "priority": "high",
                "title": f"Fix: {critical_issues[0]}",
                "description": critical_issues[0],
                "action_text": "UPLOAD NEW RESUME",
                "link": "/profile",
            }
        )

    if not profile.get("resume_text"):
        actions.append(
            {
                "type": "upload_resume",
                "priority": "critical",
                "title": "Upload Your Resume",
                "description": "Get personalized job recommendations by uploading your resume.",
                "action_text": "UPLOAD RESUME",
                "link": "/profile",
            }
        )

    if not profile.get("roles"):
        actions.append(
            {
                "type": "complete_profile",
                "priority": "medium",
                "title": "Complete Your Profile",
                "description": "Add your target roles to get better job matches.",
                "action_text": "ADD ROLES",
                "link": "/profile",
            }
        )

    return {"actions": actions[:3]}
