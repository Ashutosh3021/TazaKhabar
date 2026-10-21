"""End-to-end check of the TazaKhabar API against the live Pyronites backend.

Creates a throwaway account, then verifies the auth gate, the profile round
trip, the feed endpoints and the badge behaviour.

    python backend/scripts/check_api_flow.py
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
os.environ.setdefault("AUTH_COOKIE_SAMESITE", "lax")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api import (  # noqa: E402
    auth_router,
    badge_router,
    digest_router,
    jobs_router,
    news_router,
    profile_router,
    qa_router,
    trends_router,
)
from src.auth_session import issue_session  # noqa: E402

SMOKE_EMAIL = f"tazakhabar-api-{uuid.uuid4().hex[:8]}@example.com"
SMOKE_PASSWORD = "TazaKhabar-Smoke-2026"

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' -> ' + detail) if detail else ''}")


def build_app() -> FastAPI:
    app = FastAPI()
    for router in (
        auth_router,
        badge_router,
        digest_router,
        jobs_router,
        news_router,
        profile_router,
        qa_router,
        trends_router,
    ):
        app.include_router(router)
    return app


def main() -> int:
    print(f"smoke user: {SMOKE_EMAIL}\n")

    with TestClient(build_app()) as client:
        # --- auth gate ------------------------------------------------------
        response = client.get("/api/profile")
        check(
            "profile requires a session",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )

        response = client.get(
            "/api/profile", headers={"X-User-ID": "someone-elses-id"}
        )
        check(
            "a spoofed X-User-ID header grants nothing",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )

        response = client.post("/api/qa/chat", json={"message": "hello"})
        check(
            "chat requires a session",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )

        # --- sign in (the session is issued by the OAuth callback) ---------
        user_id = "test-account-0001"
        client.cookies.set("tk_session", issue_session(user_id, SMOKE_EMAIL))

        response = client.get("/api/auth/me")
        check(
            "me returns the signed-in user",
            response.status_code == 200 and response.json().get("authenticated"),
            f"HTTP {response.status_code}",
        )

        # --- profile round trip ---------------------------------------------
        response = client.post(
            "/api/profile",
            json={
                "name": "Smoke Tester",
                "roles": ["Backend Dev"],
                "experience_level": "II",
                "preferences": {"remote_only": True},
            },
        )
        body = response.json()
        check(
            "profile is saved",
            response.status_code == 200 and body.get("name") == "Smoke Tester",
            f"HTTP {response.status_code}",
        )

        response = client.get("/api/profile")
        body = response.json()
        check(
            "profile is read back",
            body.get("id") == user_id and body.get("roles") == ["Backend Dev"],
            f"roles={body.get('roles')}",
        )

        # --- feeds ----------------------------------------------------------
        for path in ("/api/jobs", "/api/news", "/api/trends", "/api/digest", "/api/badge"):
            response = client.get(path)
            check(
                f"GET {path} responds",
                response.status_code == 200,
                f"HTTP {response.status_code} {response.text[:120]}",
            )

        # --- badge ----------------------------------------------------------
        response = client.get("/api/badge")
        before = response.json()
        response = client.post("/api/badge/seen")
        check(
            "marking the feed as seen resets the badge",
            response.status_code == 200 and response.json().get("new_jobs") == 0,
            f"before={before}",
        )

        # --- qa profile -----------------------------------------------------
        response = client.get("/api/qa/profile")
        body = response.json()
        check(
            "qa profile reflects the stored profile",
            response.status_code == 200 and body.get("has_profile") is True,
            f"body={str(body)[:140]}",
        )

        # --- logout ---------------------------------------------------------
        response = client.post("/api/auth/logout")
        check("logout works", response.status_code == 200, f"HTTP {response.status_code}")
        client.cookies.clear()

        response = client.get("/api/profile")
        check(
            "profile is locked again after logout",
            response.status_code == 401,
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
