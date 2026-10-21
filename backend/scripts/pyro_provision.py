"""Provision the TazaKhabar Pyronites project: app key, tables, smoke test.

Idempotent. Run from the repo root:

    python backend/scripts/pyro_provision.py

Reads PYRONITES_URL / PYRONITES_PROJECT_ID / PYRONITES_ADMIN_KEY from the
repo-root .env file (git-ignored). Raw keys are written to .env, never printed.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

# Column types allowed by Pyronites: TEXT INTEGER REAL BLOB NUMERIC BOOLEAN DATETIME DATE JSON
TABLES: Dict[str, Dict[str, Any]] = {
    "profiles": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},  # Pyronites user id
            {"name": "name", "type": "TEXT"},
            {"name": "email", "type": "TEXT"},
            {"name": "roles", "type": "JSON"},
            {"name": "experience_level", "type": "TEXT"},
            {"name": "resume_path", "type": "TEXT"},
            {"name": "resume_text", "type": "TEXT"},
            {"name": "ats_score", "type": "INTEGER"},
            {"name": "ats_critical_issues", "type": "JSON"},
            {"name": "ats_missing_keywords", "type": "JSON"},
            {"name": "ats_suggested_additions", "type": "JSON"},
            {"name": "last_analysis_at", "type": "DATETIME"},
            {"name": "preferences", "type": "JSON"},
            {"name": "feed_last_seen_at", "type": "DATETIME"},
            {"name": "created_at", "type": "DATETIME"},
        ],
    },
    # "users" is reserved on Pyronites, hence "accounts".
    "accounts": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "provider", "type": "TEXT"},
            {"name": "provider_id", "type": "TEXT"},
            {"name": "email", "type": "TEXT"},
            {"name": "name", "type": "TEXT"},
            {"name": "avatar_url", "type": "TEXT"},
            {"name": "email_verified", "type": "BOOLEAN"},
            {"name": "created_at", "type": "DATETIME"},
            {"name": "last_login_at", "type": "DATETIME"},
        ],
    },
    "jobs": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "hn_item_id", "type": "INTEGER"},
            {"name": "title", "type": "TEXT"},
            {"name": "company", "type": "TEXT"},
            {"name": "location", "type": "TEXT"},
            {"name": "tags", "type": "JSON"},
            {"name": "email_contact", "type": "TEXT"},
            {"name": "apply_link", "type": "TEXT"},
            {"name": "is_ghost_job", "type": "BOOLEAN"},
            {"name": "deadline", "type": "TEXT"},
            {"name": "posted_at", "type": "DATETIME"},
            {"name": "scraped_at", "type": "DATETIME"},
            {"name": "cleaned_title", "type": "TEXT"},
            {"name": "cleaned_company", "type": "TEXT"},
            {"name": "role", "type": "TEXT"},
            {"name": "description", "type": "TEXT"},
            {"name": "processed", "type": "BOOLEAN"},
        ],
    },
    "news": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "hn_item_id", "type": "INTEGER"},
            {"name": "type", "type": "TEXT"},
            {"name": "title", "type": "TEXT"},
            {"name": "url", "type": "TEXT"},
            {"name": "score", "type": "INTEGER"},
            {"name": "comment_count", "type": "INTEGER"},
            {"name": "summary", "type": "TEXT"},
            {"name": "summarized", "type": "BOOLEAN"},
            {"name": "summarized_at", "type": "DATETIME"},
            {"name": "scraped_at", "type": "DATETIME"},
        ],
    },
    "trends": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "keyword", "type": "TEXT"},
            {"name": "count", "type": "INTEGER"},
            {"name": "week_start", "type": "DATETIME"},
            {"name": "week_end", "type": "DATETIME"},
            {"name": "percentage_change", "type": "REAL"},
            {"name": "direction", "type": "TEXT"},
        ],
    },
    "trend_predictions": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "keyword", "type": "TEXT"},
            {"name": "horizon_weeks", "type": "INTEGER"},
            {"name": "predicted_count", "type": "INTEGER"},
            {"name": "confidence", "type": "REAL"},
            {"name": "predicted_at", "type": "DATETIME"},
        ],
    },
    "rate_limits": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "user_id", "type": "TEXT"},
            {"name": "date", "type": "TEXT"},
            {"name": "request_count", "type": "INTEGER"},
            {"name": "last_request_at", "type": "DATETIME"},
        ],
    },
    "observations": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "week_start", "type": "DATETIME"},
            {"name": "text", "type": "TEXT"},
            {"name": "generated_at", "type": "DATETIME"},
        ],
    },
    "embeddings": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "item_id", "type": "TEXT"},
            {"name": "item_type", "type": "TEXT"},
            # base64 text: SQLite blob columns come back as text and cannot
            # carry arbitrary bytes safely.
            {"name": "embedding", "type": "TEXT"},
            {"name": "created_at", "type": "DATETIME"},
        ],
    },
    "notifications": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "user_id", "type": "TEXT"},
            {"name": "job_id", "type": "TEXT"},
            {"name": "match_score", "type": "INTEGER"},
            {"name": "status", "type": "TEXT"},
            {"name": "created_at", "type": "DATETIME"},
            {"name": "sent_at", "type": "DATETIME"},
        ],
    },
    # Every table needs an "id" column: the row endpoints (/tables/{table}/{id})
    # address rows by that column, so a differently named PK breaks row ops.
    "scraper_state": {
        "primary_key": "id",
        "columns": [
            {"name": "id", "type": "TEXT"},
            {"name": "state_key", "type": "TEXT"},
            {"name": "value", "type": "TEXT"},
            {"name": "updated_at", "type": "DATETIME"},
        ],
    },
}


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def write_env_value(path: Path, key: str, value: str) -> None:
    lines: List[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith(f"{key}="):
                lines.append(f"{key}={value}")
                replaced = True
            else:
                lines.append(raw)
    if not replaced:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


class Pyro:
    """Minimal project-scoped Pyronites REST client (httpx)."""

    def __init__(self, url: str, project_id: str, key: str, timeout: float = 90.0) -> None:
        self.url = url.rstrip("/")
        self.project_id = project_id
        self._client = httpx.Client(
            base_url=self.url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )

    def _project(self, suffix: str) -> str:
        return f"/api/projects/{self.project_id}{suffix}"

    def tables(self) -> List[Dict[str, Any]]:
        r = self._client.get(self._project("/tables"))
        r.raise_for_status()
        return r.json()

    def schema(self, table: str) -> List[Dict[str, Any]]:
        r = self._client.get(self._project(f"/tables/{table}/schema"))
        r.raise_for_status()
        return r.json()

    def create_table(self, table: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        r = self._client.post(
            self._project("/tables"),
            json={
                "table": table,
                "columns": spec["columns"],
                "primary_key": spec.get("primary_key"),
            },
        )
        if r.status_code >= 400:
            raise RuntimeError(f"create_table({table}) -> {r.status_code} {r.text[:300]}")
        return r.json() if r.content else {}

    def create_key(self, name: str, scopes: List[str]) -> Dict[str, Any]:
        r = self._client.post(self._project("/api/keys"), json={"name": name, "scopes": scopes})
        if r.status_code >= 400:
            raise RuntimeError(f"create_key({name}) -> {r.status_code} {r.text[:300]}")
        return r.json()

    def drop_table(self, table: str) -> Any:
        r = self._client.request(
            "DELETE", self._project(f"/tables/{table}"), json={"confirm_name": table}
        )
        if r.status_code >= 400:
            raise RuntimeError(f"drop_table({table}) -> {r.status_code} {r.text[:300]}")
        return r.json() if r.content else None

    def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        r = self._client.post(self._project(f"/tables/{table}"), json=row)
        if r.status_code >= 400:
            raise RuntimeError(f"insert({table}) -> {r.status_code} {r.text[:300]}")
        return r.json() if r.content else {}

    def select(self, table: str, **params: Any) -> List[Dict[str, Any]]:
        clean = {k: v for k, v in params.items() if v is not None}
        r = self._client.get(self._project(f"/tables/{table}"), params=clean)
        if r.status_code >= 400:
            raise RuntimeError(f"select({table}) -> {r.status_code} {r.text[:300]}")
        return r.json()

    def delete(self, table: str, row_id: str) -> Any:
        r = self._client.delete(self._project(f"/tables/{table}/{row_id}"))
        if r.status_code >= 400:
            raise RuntimeError(f"delete({table}/{row_id}) -> {r.status_code} {r.text[:300]}")
        return r.json() if r.content else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Pyronites for TazaKhabar")
    parser.add_argument("--skip-key", action="store_true", help="do not mint the app key")
    parser.add_argument("--skip-tables", action="store_true", help="do not create tables")
    parser.add_argument("--skip-smoke", action="store_true", help="do not run the smoke test")
    parser.add_argument(
        "--drop",
        action="append",
        default=[],
        metavar="TABLE",
        help="drop a table (admin key) before provisioning; it is recreated if in the schema map",
    )
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    url = env.get("PYRONITES_URL") or os.environ.get("PYRONITES_URL")
    project_id = env.get("PYRONITES_PROJECT_ID") or os.environ.get("PYRONITES_PROJECT_ID")
    admin_key = env.get("PYRONITES_ADMIN_KEY") or os.environ.get("PYRONITES_ADMIN_KEY")
    app_key = env.get("PYRONITES_KEY") or os.environ.get("PYRONITES_KEY")

    missing = [n for n, v in (("PYRONITES_URL", url), ("PYRONITES_PROJECT_ID", project_id), ("PYRONITES_ADMIN_KEY", admin_key)) if not v]
    if missing:
        print(f"ERROR: missing {', '.join(missing)} in {ENV_PATH}")
        return 2

    admin = Pyro(url, project_id, admin_key)  # type: ignore[arg-type]
    print(f"backend   : {url}")
    print(f"project   : {project_id}")
    print(f"env file  : {ENV_PATH}")

    if not args.skip_key and not app_key:
        name = "tazakhabar-app"
        created = admin.create_key(name, ["read", "write"])
        raw_key = created.get("key")
        if not raw_key:
            print(f"ERROR: key creation returned no raw key: {list(created.keys())}")
            return 3
        write_env_value(ENV_PATH, "PYRONITES_KEY", raw_key)
        app_key = raw_key
        print(f"app key   : minted '{name}' scopes={created.get('scopes')} -> saved to .env as PYRONITES_KEY")
    elif app_key:
        print("app key   : PYRONITES_KEY already present in .env (not rotated)")

    existing = {t["name"]: t for t in admin.tables()}
    for table in args.drop:
        if table in existing:
            admin.drop_table(table)
            existing.pop(table, None)
            print(f"table     : {table:18} dropped")
    if not args.skip_tables:
        for table, spec in TABLES.items():
            if table in existing:
                cols = admin.schema(table)
                print(f"table     : {table:18} exists ({len(cols)} cols) - skipped")
                continue
            admin.create_table(table, spec)
            print(f"table     : {table:18} created")
    else:
        print("tables    : skipped")

    if not args.skip_smoke:
        app = Pyro(url, project_id, app_key or admin_key)  # type: ignore[arg-type]
        marker = uuid.uuid4().hex
        row_id = uuid.uuid4().hex
        state_key = f"smoke-{marker}"
        app.insert("scraper_state", {
            "id": row_id,
            "state_key": state_key,
            "value": "ok",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        rows = app.select("scraper_state", filter_column="state_key", filter_value=state_key)
        assert rows and rows[0].get("value") == "ok", f"smoke select failed: {rows}"
        app.delete("scraper_state", row_id)
        print("smoke     : insert -> select -> delete OK (scraper_state)")

    print("\nphase A0 complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
