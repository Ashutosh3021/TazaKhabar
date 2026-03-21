"""
User profile API endpoint.
GET /api/profile — Get user profile with ATS data.
POST /api/profile — Create or update user profile.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.db.database import async_session
from src.db.models import User
from src.db.schemas import ProfileResponse, ProfileUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
async def get_profile(
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """
    Get user profile by X-User-ID header.
    Returns empty profile if user not found.
    """
    print(f"\n>>> [API:GET /api/profile] User: {x_user_id}")

    if not x_user_id:
        return ProfileResponse()

    async with async_session() as session:
        stmt = select(User).where(User.id == x_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None:
        print(f">>> [API:GET /api/profile] User not found, returning empty")
        return ProfileResponse()

    last_analysis_str = (
        user.last_analysis_at.isoformat() if user.last_analysis_at else None
    )

    print(f">>> [API:GET /api/profile] Found user: {user.name}, ats_score={user.ats_score}")

    return ProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        roles=user.roles or [],
        experience_level=user.experience_level,
        ats_score=user.ats_score,
        ats_critical_issues=user.ats_critical_issues or [],
        ats_missing_keywords=user.ats_missing_keywords or [],
        ats_suggested_additions=user.ats_suggested_additions or [],
        last_analysis_at=last_analysis_str,
        resume_text_length=len(user.resume_text) if user.resume_text else None,
        preferences=user.preferences or {},
    )


@router.post("", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdateRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """
    Create or update user profile.
    Requires X-User-ID header.
    Regenerates user embedding on save (placeholder for Plan 02-03).
    """
    print(f"\n>>> [API:POST /api/profile] User: {x_user_id}, data: {data.model_dump()}")

    if not x_user_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-ID header required",
        )

    async with async_session() as session:
        # Upsert user
        stmt = select(User).where(User.id == x_user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            # Create new user
            user = User(
                id=x_user_id,
                name=data.name or "Anonymous",
                email=data.email,
                roles=data.roles,
                experience_level=data.experience_level,
                preferences=data.preferences or {},
            )
            session.add(user)
            print(f">>> [API:POST /api/profile] Created new user")
        else:
            # Update existing
            if data.name is not None:
                user.name = data.name
            if data.email is not None:
                user.email = data.email
            if data.roles is not None:
                user.roles = data.roles
            if data.experience_level is not None:
                user.experience_level = data.experience_level
            if data.preferences is not None:
                user.preferences = data.preferences
            print(f">>> [API:POST /api/profile] Updated user")

        await session.commit()
        # Refresh to get latest state
        await session.refresh(user)

        # Trigger embedding regeneration on profile save
        try:
            import asyncio
            from src.services.embedding_service import generate_user_embedding

            loop = asyncio.get_running_loop()
            loop.create_task(
                generate_user_embedding(
                    user_id=user.id,
                    roles=user.roles or [],
                    experience=user.experience_level,
                    resume_text=user.resume_text,
                    preferences=user.preferences or {},
                )
            )
            print(f">>> [API:POST /api/profile] Triggered embedding regeneration")
        except ImportError:
            print(f">>> [API:POST /api/profile] Embedding service import failed (may be circular)")
        except Exception as e:
            print(f">>> [API:POST /api/profile] Embedding regeneration failed: {e}")

        last_analysis_str = (
            user.last_analysis_at.isoformat() if user.last_analysis_at else None
        )

        return ProfileResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            roles=user.roles or [],
            experience_level=user.experience_level,
            ats_score=user.ats_score,
            ats_critical_issues=user.ats_critical_issues or [],
            ats_missing_keywords=user.ats_missing_keywords or [],
            ats_suggested_additions=user.ats_suggested_additions or [],
            last_analysis_at=last_analysis_str,
            resume_text_length=len(user.resume_text) if user.resume_text else None,
            preferences=user.preferences or {},
        )
