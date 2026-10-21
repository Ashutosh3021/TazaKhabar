"""Delete the throwaway accounts created by the check scripts.

    python backend/scripts/cleanup_smoke_accounts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import settings  # noqa: E402

SMOKE_PREFIXES = ("tazakhabar-smoke-", "tazakhabar-api-")


def read_admin_key() -> str:
    """Read the admin key straight from .env: the app never loads it."""
    for path in (Path(__file__).resolve().parents[2] / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("PYRONITES_ADMIN_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    url = settings.PYRONITES_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.PYRONITES_KEY}"}
    admin_headers = {
        "Authorization": f"Bearer {read_admin_key() or settings.PYRONITES_KEY}"
    }

    response = requests.get(f"{url}/api/users", headers=headers, timeout=60)
    if response.status_code != 200:
        print(f"list users -> {response.status_code} {response.text[:200]}")
        return 1

    users = response.json()
    if isinstance(users, dict):
        users = users.get("users", [])

    removed = 0
    for user in users:
        email = str(user.get("email", ""))
        if not email.startswith(SMOKE_PREFIXES):
            continue
        delete = requests.delete(
            f"{url}/api/users/{user['id']}", headers=admin_headers, timeout=60
        )
        print(f"  {email}: delete -> {delete.status_code}")
        if delete.status_code < 400:
            removed += 1

    # Remove the profile rows those accounts left behind.
    import asyncio

    from src.db.pyro import get_pyro

    async def clean_profiles() -> int:
        client = get_pyro()
        rows = await client.sql(
            "SELECT id FROM \"profiles\" WHERE email LIKE 'tazakhabar-%@example.com'"
        )
        for row in rows:
            await client.exec(f"DELETE FROM \"profiles\" WHERE id = '{row['id']}'")
        return len(rows)

    profiles_removed = asyncio.run(clean_profiles())
    print(f"removed {removed} smoke accounts and {profiles_removed} smoke profiles")

    return 0


if __name__ == "__main__":
    sys.exit(main())
