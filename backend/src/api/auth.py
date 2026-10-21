"""
Authentication endpoints backed by Pyronites.

POST /api/auth/signup  - create a Pyronites account (falls back to login)
POST /api/auth/login   - email + password
POST /api/auth/logout  - drop the session
GET  /api/auth/me      - resolve the current session
POST /api/auth/password/forgot - trigger a Pyronites reset email

The browser receives an httpOnly cookie; the Pyronites key never leaves the
server.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.auth_session import (
    PyroAuthError,
    decode_session,
    encode_session,
    get_pyro_auth,
    user_id,
)
from src.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Credentials(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=8, max_length=256)


class ForgotPassword(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)


class SessionUser(BaseModel):
    id: Optional[str] = None
    email: Optional[str] = None
    authenticated: bool = False


class AuthResponse(BaseModel):
    authenticated: bool
    user: SessionUser
    message: Optional[str] = None


def _public_user(payload: Dict[str, Any]) -> SessionUser:
    email = payload.get("email") if isinstance(payload, dict) else None
    nested = payload.get("user") if isinstance(payload, dict) else None
    if isinstance(nested, dict):
        email = email or nested.get("email")
    return SessionUser(id=user_id(payload), email=email, authenticated=True)


def _set_session_cookie(response: Response, cookie_header: str) -> None:
    response.set_cookie(
        key=settings.AUTH_SESSION_COOKIE,
        value=encode_session(cookie_header),
        max_age=settings.AUTH_SESSION_TTL_SEC,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_SESSION_COOKIE,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


async def _authenticate(
    response: Response, email: str, password: str, allow_signup: bool
) -> AuthResponse:
    auth = get_pyro_auth()
    try:
        if allow_signup:
            try:
                payload, cookie_header = await auth.signup(email, password)
            except PyroAuthError as exc:
                if exc.status_code != 409:
                    raise
                # The account exists. Fall back to signing in with the same
                # password, and say clearly what went wrong if that fails.
                try:
                    payload, cookie_header = await auth.login(email, password)
                except PyroAuthError as login_exc:
                    if login_exc.status_code == 401:
                        raise HTTPException(
                            status_code=409,
                            detail=(
                                "This address already has an account. Sign in with its "
                                "passcode, or use 'Forgot passcode' to set a new one."
                            ),
                        ) from login_exc
                    raise
        else:
            payload, cookie_header = await auth.login(email, password)
    except PyroAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if not cookie_header:
        raise HTTPException(status_code=500, detail="Pyronites returned no session")

    _set_session_cookie(response, cookie_header)
    return AuthResponse(authenticated=True, user=_public_user(payload))


@router.post("/signup", response_model=AuthResponse)
async def signup(credentials: Credentials, response: Response) -> AuthResponse:
    """Create an account, or sign in when the account already exists."""
    return await _authenticate(
        response, credentials.email, credentials.password, allow_signup=True
    )


@router.post("/login", response_model=AuthResponse)
async def login(credentials: Credentials, response: Response) -> AuthResponse:
    """Sign in with email and password."""
    return await _authenticate(
        response, credentials.email, credentials.password, allow_signup=False
    )


@router.post("/logout", response_model=AuthResponse)
async def logout(request: Request, response: Response) -> AuthResponse:
    """Invalidate the session on Pyronites and clear the browser cookie."""
    token = request.cookies.get(settings.AUTH_SESSION_COOKIE)
    cookie_header = decode_session(token)
    if cookie_header:
        await get_pyro_auth().logout(cookie_header)
    _clear_session_cookie(response)
    return AuthResponse(authenticated=False, user=SessionUser())


@router.get("/me", response_model=AuthResponse)
async def me(request: Request) -> AuthResponse:
    """Resolve the signed-in user, or report an anonymous session."""
    token = request.cookies.get(settings.AUTH_SESSION_COOKIE)
    cookie_header = decode_session(token)
    if not cookie_header:
        return AuthResponse(authenticated=False, user=SessionUser())
    payload = await get_pyro_auth().me(cookie_header)
    if not payload:
        return AuthResponse(authenticated=False, user=SessionUser())
    return AuthResponse(authenticated=True, user=_public_user(payload))


@router.post("/password/forgot", response_model=AuthResponse)
async def forgot_password(payload: ForgotPassword) -> AuthResponse:
    """Ask Pyronites to email a reset link. Always reports success."""
    try:
        await get_pyro_auth().forgot_password(payload.email)
    except PyroAuthError:
        pass
    return AuthResponse(
        authenticated=False,
        user=SessionUser(),
        message="If that address has an account, a reset link is on its way.",
    )
