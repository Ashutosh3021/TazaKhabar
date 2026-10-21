"""
Session handling for the browser.

The session is a signed token in an httpOnly cookie: ``<payload>.<signature>``
where the payload is base64url JSON and the signature is an HMAC-SHA256 over
it. The API verifies the signature and the expiry on every request, so a
forged cookie only produces a 401.

Sign in happens through Google or GitHub (see ``src/services/oauth_service.py``);
no password is ever stored or transmitted.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

from src.config import settings

SESSION_VERSION = "v1"


def _secret() -> bytes:
    raw = settings.AUTH_SESSION_SECRET or settings.PYRONITES_KEY
    return (raw or "tazakhabar-insecure-dev-secret").encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()[:32]


def issue_session(user_id: str, email: str, ttl_seconds: int | None = None) -> str:
    """Create a signed session token for a user."""
    ttl = ttl_seconds or settings.AUTH_SESSION_TTL_SEC
    payload = {
        "uid": user_id,
        "email": email,
        "exp": int(time.time()) + ttl,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{SESSION_VERSION}.{encoded}.{_sign(encoded)}"


def read_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the session payload, or None when the token is invalid or expired."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != SESSION_VERSION:
        return None

    _, encoded, signature = parts
    if not hmac.compare_digest(signature, _sign(encoded)):
        return None

    padding = "=" * (-len(encoded) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if int(payload.get("exp") or 0) < int(time.time()):
        return None
    if not payload.get("uid"):
        return None
    return payload


def sign_state(value: str) -> str:
    """Sign a short lived value (the OAuth state nonce)."""
    return f"{value}.{_sign(value)}"


def read_state(value: Optional[str]) -> Optional[str]:
    """Return the signed value, or None when the signature does not match."""
    if not value or "." not in value:
        return None
    raw, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(raw)):
        return None
    return raw
