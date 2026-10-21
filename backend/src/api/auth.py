"""
Authentication endpoints.

Sign in happens through Google or GitHub. The API is the OAuth client: it
redirects the browser to the provider, handles the callback, links the
identity to an account row and hands out a signed session cookie.

There is no password endpoint: no password is ever stored, sent or accepted.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.auth_session import issue_session, read_session, read_state, sign_state
from src.config import settings
from src.db import repos
from src.services.oauth_service import (
    PROVIDERS,
    OAuthError,
    build_authorize_url,
    exchange_code,
    fetch_profile,
    get_provider,
    is_configured,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

STATE_COOKIE = "tk_oauth_state"
STATE_TTL_SEC = 600


class SessionUser(BaseModel):
    id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: Optional[str] = None
    authenticated: bool = False


class AuthResponse(BaseModel):
    authenticated: bool
    user: SessionUser
    message: Optional[str] = None


def _session_user(session: Dict[str, Any]) -> SessionUser:
    return SessionUser(
        id=session.get("uid"),
        email=session.get("email"),
        authenticated=True,
    )


def _redirect_uri(provider_id: str) -> str:
    """Where the provider sends the browser back to."""
    return f"{settings.API_PUBLIC_URL.rstrip('/')}/api/auth/oauth/{provider_id}/callback"


def _frontend_url(path: str = "") -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}{path}" if path else base


@router.get("/providers")
async def list_providers() -> dict:
    """Which sign-in methods are configured on this deployment."""
    return {
        "providers": [
            {"id": provider.id, "name": provider.name, "configured": is_configured(provider)}
            for provider in PROVIDERS.values()
        ]
    }


@router.get("/oauth/{provider}")
async def start_oauth(provider: str) -> RedirectResponse:
    """
    Start the OAuth flow: redirect the browser to the provider.

    The state nonce is kept in a short lived signed cookie and compared on the
    way back, which is what stops a third party from feeding us their own
    authorization code.
    """
    try:
        oauth_provider = get_provider(provider)
    except OAuthError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not is_configured(oauth_provider):
        raise HTTPException(
            status_code=503,
            detail=f"{oauth_provider.name} sign-in is not configured on this deployment",
        )

    nonce = secrets.token_urlsafe(24)
    state = f"{oauth_provider.id}:{nonce}"
    redirect_uri = _redirect_uri(oauth_provider.id)
    url, code_verifier = build_authorize_url(oauth_provider, redirect_uri, state)

    response = RedirectResponse(url, status_code=307)
    response.set_cookie(
        key=STATE_COOKIE,
        value=sign_state(f"{nonce}:{code_verifier or ''}"),
        max_age=STATE_TTL_SEC,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )
    return response


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request) -> RedirectResponse:
    """
    Handle the provider callback: validate the state, exchange the code, link
    the account and start the session.
    """
    try:
        oauth_provider = get_provider(provider)
    except OAuthError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    error = request.query_params.get("error")
    if error:
        return RedirectResponse(_frontend_url(f"/auth?error={error}"), status_code=307)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return RedirectResponse(_frontend_url("/auth?error=missing_code"), status_code=307)

    # The state cookie holds the nonce and the PKCE verifier, signed.
    stored = read_state(request.cookies.get(STATE_COOKIE))
    if not stored:
        return RedirectResponse(_frontend_url("/auth?error=invalid_state"), status_code=307)

    stored_nonce, _, stored_verifier = stored.partition(":")
    prefix = f"{oauth_provider.id}:"
    if not state.startswith(prefix):
        return RedirectResponse(_frontend_url("/auth?error=invalid_state"), status_code=307)
    if not secrets.compare_digest(state[len(prefix) :], stored_nonce):
        return RedirectResponse(_frontend_url("/auth?error=invalid_state"), status_code=307)

    try:
        token_payload = await exchange_code(
            oauth_provider,
            code,
            _redirect_uri(oauth_provider.id),
            code_verifier=stored_verifier or None,
        )
        profile = await fetch_profile(oauth_provider, token_payload["access_token"])
    except OAuthError as exc:
        logger.warning("OAuth callback failed: %s", exc)
        return RedirectResponse(_frontend_url("/auth?error=oauth_failed"), status_code=307)

    account = await repos.upsert_account(
        provider=profile["provider"],
        provider_id=profile["provider_id"],
        email=profile["email"],
        name=profile["name"],
        avatar_url=profile["avatar_url"],
        email_verified=profile["email_verified"],
    )

    session_token = issue_session(account["id"], account.get("email") or "")

    response = RedirectResponse(_frontend_url("/auth/callback"), status_code=307)
    response.set_cookie(
        key=settings.AUTH_SESSION_COOKIE,
        value=session_token,
        max_age=settings.AUTH_SESSION_TTL_SEC,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )
    response.delete_cookie(key=STATE_COOKIE, path="/")
    return response


@router.get("/me", response_model=AuthResponse)
async def me(request: Request) -> AuthResponse:
    """Resolve the current session."""
    session = read_session(request.cookies.get(settings.AUTH_SESSION_COOKIE))
    if not session:
        return AuthResponse(authenticated=False, user=SessionUser())
    return AuthResponse(authenticated=True, user=_session_user(session))


@router.post("/logout", response_model=AuthResponse)
async def logout(response: Response) -> AuthResponse:
    """Clear the session cookie."""
    response.delete_cookie(
        key=settings.AUTH_SESSION_COOKIE,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return AuthResponse(authenticated=False, user=SessionUser())
