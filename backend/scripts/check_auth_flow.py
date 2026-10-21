"""End-to-end check of the Pyronites-backed auth endpoints.

Runs the real signup / login / me / logout flow against the configured
Pyronites backend using a throwaway account.

    python backend/scripts/check_auth_flow.py
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Local overrides: the browser cookie must be readable over plain http on
# localhost, and SameSite=None requires Secure.
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
os.environ.setdefault("AUTH_COOKIE_SAMESITE", "lax")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.auth import router as auth_router  # noqa: E402
from src.config import settings  # noqa: E402

SMOKE_EMAIL = f"tazakhabar-smoke-{uuid.uuid4().hex[:8]}@example.com"
SMOKE_PASSWORD = "TazaKhabar-Smoke-2026"

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' -> ' + detail) if detail else ''}")


def main() -> int:
    print(f"backend   : {settings.PYRONITES_URL}")
    print(f"project   : {settings.PYRONITES_PROJECT_ID}")
    print(f"smoke user: {SMOKE_EMAIL}\n")

    app = FastAPI()
    app.include_router(auth_router)

    with TestClient(app) as client:
        # 1. signup creates the account and returns a session cookie
        response = client.post(
            "/api/auth/signup",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
        )
        ok = response.status_code == 200 and response.json().get("authenticated")
        check("signup returns an authenticated session", bool(ok), f"HTTP {response.status_code}")

        cookie_names = [c.name for c in client.cookies.jar]
        check(
            "session cookie is set",
            settings.AUTH_SESSION_COOKIE in cookie_names,
            ", ".join(cookie_names) or "no cookies",
        )

        # 2. the session resolves to a user
        response = client.get("/api/auth/me")
        body = response.json()
        check(
            "me resolves the signed-in user",
            response.status_code == 200 and body.get("authenticated") and body.get("user", {}).get("id"),
            f"user={body.get('user')}",
        )

        # 3. a second signup on the same account falls back to login
        response = client.post(
            "/api/auth/signup",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
        )
        check(
            "repeat signup falls back to login",
            response.status_code == 200 and response.json().get("authenticated"),
            f"HTTP {response.status_code}",
        )

        # 4. logout clears the session
        response = client.post("/api/auth/logout")
        check(
            "logout clears the session",
            response.status_code == 200 and not response.json().get("authenticated"),
            f"HTTP {response.status_code}",
        )

        response = client.get("/api/auth/me")
        check(
            "me is anonymous after logout",
            response.status_code == 200 and not response.json().get("authenticated"),
        )

        # 5. wrong password is rejected
        response = client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": "definitely-not-the-password"},
        )
        check(
            "login with a wrong password is rejected",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )

        # 6. login again works
        response = client.post(
            "/api/auth/login",
            json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD},
        )
        check(
            "login with the right password works",
            response.status_code == 200 and response.json().get("authenticated"),
            f"HTTP {response.status_code}",
        )

    failed = [name for name, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("failed:", "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
