"""
FastAPI dependencies: verified identity.

Identity is always resolved from the Pyronites session cookie. The old
``X-User-ID`` header is gone: it was client supplied, so anyone could claim
any user id.
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

from src.auth_session import decode_session, get_pyro_auth, user_id
from src.config import settings


def _cookie_header(request: Request) -> Optional[str]:
    token = request.cookies.get(settings.AUTH_SESSION_COOKIE)
    return decode_session(token)


async def resolve_user(request: Request) -> Optional[Dict[str, Any]]:
    """Return the verified Pyronites user for this request, if any."""
    cookie_header = _cookie_header(request)
    if not cookie_header:
        return None
    payload = await get_pyro_auth().me(cookie_header)
    if not payload:
        return None
    resolved = dict(payload)
    resolved["id"] = user_id(payload)
    return resolved if resolved.get("id") else None


async def require_user(request: Request) -> Dict[str, Any]:
    """Require a signed-in user. Raises 401 for anonymous callers."""
    user = await resolve_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """Return the user when signed in, otherwise None."""
    return await resolve_user(request)
