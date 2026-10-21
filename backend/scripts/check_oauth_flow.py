"""Verify the OAuth sign-in flow without a real provider login.

    python backend/scripts/check_oauth_flow.py

Checks: provider list, authorize redirect (URL shape, state cookie, PKCE),
callback rejection of a bad state, session token signing, and the auth gate.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
os.environ.setdefault("AUTH_COOKIE_SAMESITE", "lax")
os.environ.setdefault("API_PUBLIC_URL", "https://tazakhabar-backend.onrender.com")
os.environ.setdefault("FRONTEND_URL", "https://tazakhabar.vercel.app")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api import auth_router, badge_router, profile_router  # noqa: E402
from src.auth_session import issue_session, read_session  # noqa: E402

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' -> ' + detail) if detail else ''}")


def main() -> int:
    app = FastAPI()
    for router in (auth_router, badge_router, profile_router):
        app.include_router(router)

    with TestClient(app) as client:
        # 1. providers
        response = client.get("/api/auth/providers")
        body = response.json()
        providers = {p["id"]: p for p in body.get("providers", [])}
        check(
            "google and github are offered",
            "google" in providers and "github" in providers,
            ", ".join(providers),
        )
        check(
            "providers report as configured",
            all(p["configured"] for p in providers.values()),
        )

        # 2. the authorize redirect
        response = client.get(
            "/api/auth/oauth/google", follow_redirects=False
        )
        location = response.headers.get("location", "")
        check(
            "google start redirects to the provider",
            response.status_code == 307 and location.startswith("https://accounts.google.com/"),
            f"HTTP {response.status_code}",
        )
        check(
            "the redirect uri points at this API",
            "redirect_uri=https%3A%2F%2Ftazakhabar-backend.onrender.com%2Fapi%2Fauth%2Foauth%2Fgoogle%2Fcallback" in location,
        )
        check(
            "the authorize url carries state and PKCE",
            "state=" in location and "code_challenge=" in location,
        )
        state_cookie = client.cookies.get("tk_oauth_state")
        check("the state is stored in a signed cookie", bool(state_cookie))

        # 3. a callback with a state that does not match is refused
        response = client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "bogus", "state": "google:wrong-nonce"},
            follow_redirects=False,
        )
        check(
            "a mismatched state is rejected",
            response.status_code == 307 and "error=invalid_state" in response.headers.get("location", ""),
            response.headers.get("location", ""),
        )

        # 4. a callback without a code is rejected
        response = client.get(
            "/api/auth/oauth/google/callback", params={}, follow_redirects=False
        )
        check(
            "a callback without a code is rejected",
            response.status_code == 307 and "error=missing_code" in response.headers.get("location", ""),
        )

        # 5. the session token
        token = issue_session("account-123", "person@example.com")
        payload = read_session(token)
        check(
            "a signed session token verifies",
            bool(payload) and payload.get("uid") == "account-123",
        )
        check(
            "a tampered session token is refused",
            read_session(token[:-2] + "xy") is None,
        )
        check(
            "an expired session token is refused",
            read_session(issue_session("account-123", "p@example.com", ttl_seconds=-10)) is None,
        )

        # 6. the auth gate uses the session cookie
        response = client.get("/api/profile")
        check(
            "the profile endpoint needs a session",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )

        client.cookies.set("tk_session", token)
        response = client.get("/api/profile")
        check(
            "a valid session opens the profile endpoint",
            response.status_code == 200,
            f"HTTP {response.status_code}",
        )

        response = client.get("/api/auth/me")
        body = response.json()
        check(
            "me reports the signed-in user",
            body.get("authenticated") is True and body.get("user", {}).get("id") == "account-123",
            str(body)[:120],
        )

        # 7. logout clears it
        response = client.post("/api/auth/logout")
        check("logout works", response.status_code == 200, f"HTTP {response.status_code}")

    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("failed:", "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
