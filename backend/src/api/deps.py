"""
FastAPI dependencies: verified identity.

Identity comes from the signed session cookie the API issues after a Google or
GitHub sign in. The cookie is verified on every request, so a forged value only
produces a 401.
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from src.auth_session import read_session
from src.config import settings


def _session(request: Request) -> Optional[Dict[str, Any]]:
    payload = read_session(request.cookies.get(settings.AUTH_SESSION_COOKIE))
    if not payload:
        return None
    return {
        "id": payload.get("uid"),
        "email": payload.get("email"),
        "expires_at": payload.get("exp"),
    }


async def resolve_user(request: Request) -> Optional[Dict[str, Any]]:
    """Return the signed-in user for this request, if any."""
    return _session(request)


async def require_user(request: Request) -> Dict[str, Any]:
    """Require a signed-in user. Raises 401 for anonymous callers."""
    session = _session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session


async def optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Return the user when signed in, otherwise None."""
    return _session(request)
