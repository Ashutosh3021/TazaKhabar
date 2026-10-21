"""
OAuth 2.0 authorization code flow for Google and GitHub.

The API is the OAuth client: it builds the authorize URL, exchanges the code
for tokens, reads the profile and returns a normalised identity. The browser
never sees a client secret.

Why the app does not use the Pyronites OAuth endpoints: those hard-code their
own callback URL (``pyrocore-backend.onrender.com/auth/oauth/...``) and hand the
session to that host with a host-only cookie, which this API (a different
host) can never read.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx


@dataclass(frozen=True)
class OAuthProvider:
    id: str
    name: str
    authorize_url: str
    token_url: str
    scope: str
    use_pkce: bool = False


PROVIDERS: Dict[str, OAuthProvider] = {
    "google": OAuthProvider(
        id="google",
        name="Google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scope="openid email profile",
        use_pkce=True,
    ),
    "github": OAuthProvider(
        id="github",
        name="GitHub",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scope="read:user user:email",
    ),
}


class OAuthError(RuntimeError):
    """Raised when the provider rejects the flow or the profile cannot be read."""


def get_provider(provider_id: str) -> OAuthProvider:
    provider = PROVIDERS.get((provider_id or "").lower())
    if provider is None:
        raise OAuthError(f"Unknown provider: {provider_id}")
    return provider


def client_id(provider: OAuthProvider) -> str:
    from src.config import settings

    if provider.id == "google":
        return settings.GOOGLE_CLIENT_ID
    return settings.GITHUB_CLIENT_ID


def client_secret(provider: OAuthProvider) -> str:
    from src.config import settings

    if provider.id == "google":
        return settings.GOOGLE_CLIENT_SECRET
    return settings.GITHUB_CLIENT_SECRET


def is_configured(provider: OAuthProvider) -> bool:
    return bool(client_id(provider) and client_secret(provider))


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("ascii").rstrip("=")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorize_url(
    provider: OAuthProvider, redirect_uri: str, state: str
) -> tuple[str, Optional[str]]:
    """Build the provider authorize URL. Returns (url, code_verifier)."""
    params: Dict[str, str] = {
        "client_id": client_id(provider),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
    }

    code_verifier: Optional[str] = None
    if provider.use_pkce:
        code_verifier, challenge = _pkce_pair()
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"

    if provider.id == "google":
        params["prompt"] = "select_account"

    return f"{provider.authorize_url}?{urlencode(params)}", code_verifier


async def exchange_code(
    provider: OAuthProvider,
    code: str,
    redirect_uri: str,
    code_verifier: Optional[str] = None,
) -> Dict[str, Any]:
    """Exchange the authorization code for an access token."""
    data = {
        "client_id": client_id(provider),
        "client_secret": client_secret(provider),
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            provider.token_url,
            data=data,
            headers={"Accept": "application/json"},
        )
    if response.status_code >= 400:
        raise OAuthError(
            f"{provider.name} rejected the code: {response.status_code} {response.text[:200]}"
        )
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise OAuthError(f"{provider.name} returned no access token: {str(payload)[:200]}")
    return payload


async def fetch_profile(
    provider: OAuthProvider, access_token: str
) -> Dict[str, Any]:
    """Read the user profile from the provider."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        if provider.id == "google":
            response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo", headers=headers
            )
            if response.status_code >= 400:
                raise OAuthError(
                    f"Google profile request failed: {response.status_code} {response.text[:200]}"
                )
            raw = response.json()
            return {
                "provider": "google",
                "provider_id": str(raw.get("sub") or ""),
                "email": (raw.get("email") or "").strip().lower(),
                "email_verified": bool(raw.get("email_verified")),
                "name": raw.get("name") or raw.get("given_name") or "",
                "avatar_url": raw.get("picture") or "",
            }

        # GitHub
        response = await client.get("https://api.github.com/user", headers=headers)
        if response.status_code >= 400:
            raise OAuthError(
                f"GitHub profile request failed: {response.status_code} {response.text[:200]}"
            )
        raw = response.json()
        email = (raw.get("email") or "").strip().lower()
        verified = bool(email)

        if not email:
            emails = await client.get("https://api.github.com/user/emails", headers=headers)
            if emails.status_code < 400 and isinstance(emails.json(), list):
                for entry in emails.json():
                    if entry.get("primary") and entry.get("verified"):
                        email = (entry.get("email") or "").strip().lower()
                        verified = True
                        break

        return {
            "provider": "github",
            "provider_id": str(raw.get("id") or ""),
            "email": email,
            "email_verified": verified,
            "name": raw.get("name") or raw.get("login") or "",
            "avatar_url": raw.get("avatar_url") or "",
        }
