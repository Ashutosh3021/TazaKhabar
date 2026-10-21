"""
Session handling for the browser-facing API.

The browser never talks to Pyronites directly and never sees ``PYRONITES_KEY``.
Instead the backend authenticates against Pyronites and hands the browser an
httpOnly cookie that carries the Pyronites session, signed so it cannot be
edited client side. Every request that needs an identity re-validates the
session against Pyronites, so a forged cookie only produces a 401.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, Dict, Optional, Tuple

import httpx

from src.config import settings

# Pyronites sets one of these on login/signup. The exact name is discovered at
# runtime from the response, this list is only used as a fallback.
SESSION_COOKIE_NAMES = ("session_token", "session", "pyronites_session", "access_token")


class PyroAuthError(Exception):
    """Raised when Pyronites rejects the credentials."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


def _secret() -> bytes:
    raw = settings.AUTH_SESSION_SECRET or settings.PYRONITES_KEY
    return (raw or "tazakhabar-insecure-dev-secret").encode("utf-8")


def encode_session(cookie_header: str) -> str:
    """Sign a cookie header so the browser cannot tamper with it."""
    payload = base64.urlsafe_b64encode(cookie_header.encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{signature}"


def decode_session(token: Optional[str]) -> Optional[str]:
    """Return the original cookie header, or None when the token is invalid."""
    if not token or "." not in token:
        return None
    payload, signature = token.split(".", 1)
    expected = hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected):
        return None
    padding = "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(payload + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _cookie_header(response: httpx.Response) -> str:
    """Flatten the cookies Pyronites set into a single Cookie header value."""
    pairs = []
    for cookie in response.cookies.jar:
        pairs.append(f"{cookie.name}={cookie.value}")
    if not pairs:
        for name in SESSION_COOKIE_NAMES:
            value = response.cookies.get(name)
            if value:
                pairs.append(f"{name}={value}")
                break
    return "; ".join(pairs)


class PyroAuth:
    """Client for the unscoped Pyronites auth endpoints."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        self.url = url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _post_credentials(
        self, path: str, email: str, password: str
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        response = await self._client.post(
            path, json={"email": email, "password": password}
        )
        if response.status_code >= 400:
            detail: Any
            try:
                body = response.json()
                detail = body.get("message") or body.get("detail") or response.text
            except ValueError:
                detail = response.text
            raise PyroAuthError(str(detail)[:200], response.status_code)

        cookie_header = _cookie_header(response)
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        # Some deployments return the token in the body instead of a cookie.
        if not cookie_header and isinstance(payload, dict):
            for field in ("session_token", "access_token", "token"):
                value = payload.get(field)
                if isinstance(value, str) and value:
                    cookie_header = f"session_token={value}"
                    break
        return (payload if isinstance(payload, dict) else {}), cookie_header

    async def signup(self, email: str, password: str) -> Tuple[Dict[str, Any], str]:
        payload, cookie_header = await self._post_credentials(
            "/auth/signup", email, password
        )
        return payload, cookie_header

    async def login(self, email: str, password: str) -> Tuple[Dict[str, Any], str]:
        payload, cookie_header = await self._post_credentials(
            "/auth/login", email, password
        )
        return payload, cookie_header

    async def logout(self, cookie_header: str) -> None:
        headers = {"Cookie": cookie_header} if cookie_header else {}
        try:
            await self._client.post("/auth/logout", headers=headers)
        except httpx.HTTPError:
            pass

    async def me(self, cookie_header: str) -> Optional[Dict[str, Any]]:
        """Resolve the signed-in user from a forwarded session cookie."""
        if not cookie_header:
            return None
        headers = {"Cookie": cookie_header}
        try:
            response = await self._client.get("/auth/me", headers=headers)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    async def forgot_password(self, email: str) -> bool:
        response = await self._client.post("/auth/forgot-password", json={"email": email})
        return response.status_code < 400


_auth_client: PyroAuth | None = None


def get_pyro_auth() -> PyroAuth:
    """Return the shared Pyronites auth client."""
    global _auth_client
    if _auth_client is None:
        if not settings.PYRONITES_URL:
            raise PyroAuthError("PYRONITES_URL is not configured")
        _auth_client = PyroAuth(settings.PYRONITES_URL, settings.PYRONITES_TIMEOUT_SEC)
    return _auth_client


def user_id(user: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract the stable user id from a Pyronites user payload."""
    if not user:
        return None
    for field in ("id", "user_id", "userId", "sub"):
        value = user.get(field)
        if value:
            return str(value)
    return None
