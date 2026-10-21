"""
Pyronites (PyroCore) data client for TazaKhabar.

The backend talks to Pyronites over its project-scoped REST API:

    {PYRONITES_URL}/api/projects/{PYRONITES_PROJECT_ID}/...

Auth is ``Authorization: Bearer <PYRONITES_KEY>``. Row endpoints address rows by
their ``id`` column, so every table needs one.

Two access paths are used:

* row API  - insert / patch / delete / simple equality reads
* SQL API  - ``POST .../sql/execute`` (one statement per request, SQLite dialect)
             for anything the row API cannot express: ORDER BY, ranges, counts,
             upserts.

The SQL endpoint takes a raw statement with no bind parameters, so every value
goes through :func:`sql_literal`, which quotes and escapes it. Identifiers go
through :func:`sql_ident`, which only allows ``[A-Za-z_][A-Za-z0-9_]*``.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

import httpx

from src.config import settings

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Reserved table names on the Pyronites backend.
RESERVED_TABLES = frozenset(
    {
        "users",
        "sessions",
        "api_keys",
        "migrations",
        "projects",
        "storage_files",
        "password_reset_tokens",
        "oauth_identities",
    }
)


class PyronitesError(RuntimeError):
    """Raised when the Pyronites backend returns an error."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PyronitesAuthError(PyronitesError):
    """Raised on 401/403 responses."""


def sql_ident(name: str) -> str:
    """Quote a SQL identifier. Only simple names are allowed."""
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"invalid SQL identifier: {name!r}")
    return f'"{name}"'


def sql_literal(value: Any) -> str:
    """Render a Python value as a safe SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (datetime, date)):
        return "'" + value.isoformat().replace("'", "''") + "'"
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    if "\x00" in text:
        raise ValueError("NUL byte is not allowed in SQL literals")
    return "'" + text.replace("'", "''") + "'"


class PyroClient:
    """Thin async client over the Pyronites project-scoped API."""

    def __init__(
        self,
        url: str,
        key: str,
        project_id: str,
        timeout: float = 30.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self.project_id = project_id
        self._client = httpx.AsyncClient(
            base_url=self.url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ----------------------------------------------------------------- plumbing

    def _project_path(self, suffix: str) -> str:
        return f"/api/projects/{self.project_id}{suffix}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        files: Any = None,
    ) -> Any:
        try:
            response = await self._client.request(
                method, path, json=json_body, params=params, files=files
            )
        except httpx.HTTPError as exc:  # network / timeout
            raise PyronitesError(f"Pyronites request failed: {exc}") from exc

        if response.status_code >= 400:
            message = response.text[:300]
            try:
                body = response.json()
                detail = body.get("detail") if isinstance(body, dict) else None
                if isinstance(detail, dict):
                    message = detail.get("message", message)
                elif isinstance(body, dict):
                    message = body.get("message", message)
            except ValueError:
                body = None
            error_cls = PyronitesAuthError if response.status_code in (401, 403) else PyronitesError
            raise error_cls(
                f"Pyronites {method} {path} -> {response.status_code}: {message}",
                status_code=response.status_code,
                body=body,
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.content

    # --------------------------------------------------------------------- SQL

    async def sql(self, statement: str) -> List[Dict[str, Any]]:
        """Run one SQL statement and return rows as dicts."""
        payload = await self._request(
            "POST", self._project_path("/sql/execute"), json_body={"sql": statement}
        )
        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            return []
        first = results[0]
        columns = first.get("columns") or []
        rows = first.get("rows") or []
        return [dict(zip(columns, row)) for row in rows]

    async def exec(self, statement: str) -> int:
        """Run one write statement and return the number of affected rows."""
        payload = await self._request(
            "POST", self._project_path("/sql/execute"), json_body={"sql": statement}
        )
        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            return 0
        return int(results[0].get("changes") or 0)

    # -------------------------------------------------------------------- rows

    async def rows(
        self,
        table: str,
        *,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List rows with a single equality filter (row API)."""
        params: Dict[str, Any] = {}
        if where:
            if len(where) != 1:
                raise ValueError("the row API supports exactly one equality filter")
            column, value = next(iter(where.items()))
            params["filter_column"] = column
            params["filter_value"] = value
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        result = await self._request(
            "GET", self._project_path(f"/tables/{table}"), params=params or None
        )
        return result if isinstance(result, list) else []

    async def insert(self, table: str, row: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one row; ``id`` is generated when absent."""
        result = await self._request(
            "POST", self._project_path(f"/tables/{table}"), json_body=row
        )
        return result if isinstance(result, dict) else {}

    async def patch(self, table: str, row_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update one row by id."""
        result = await self._request(
            "PATCH", self._project_path(f"/tables/{table}/{row_id}"), json_body=data
        )
        return result if isinstance(result, dict) else {}

    async def delete(self, table: str, row_id: str) -> None:
        await self._request("DELETE", self._project_path(f"/tables/{table}/{row_id}"))

    async def schema(self, table: str) -> List[Dict[str, Any]]:
        result = await self._request("GET", self._project_path(f"/tables/{table}/schema"))
        return result if isinstance(result, list) else []

    async def table_names(self) -> List[str]:
        result = await self._request("GET", self._project_path("/tables"))
        return [t["name"] for t in result if isinstance(t, dict) and "name" in t]

    # ----------------------------------------------------------------- storage

    async def upload(self, filename: str, content: bytes, content_type: str) -> Dict[str, Any]:
        result = await self._request(
            "POST",
            self._project_path("/storage/upload"),
            files={"file": (filename, content, content_type)},
        )
        return result if isinstance(result, dict) else {}

    async def download(self, file_id: str) -> bytes:
        return await self._request("GET", self._project_path(f"/storage/{file_id}/download"))

    async def healthy(self) -> bool:
        try:
            result = await self._request("GET", "/health")
        except PyronitesError:
            return False
        return bool(result and result.get("status") == "ok")


_client: PyroClient | None = None


def get_pyro() -> PyroClient:
    """Return the shared Pyronites client."""
    global _client
    if _client is None:
        if not settings.PYRONITES_URL:
            raise PyronitesError("PYRONITES_URL is not configured")
        if not settings.PYRONITES_KEY:
            raise PyronitesError("PYRONITES_KEY is not configured")
        if not settings.PYRONITES_PROJECT_ID:
            raise PyronitesError("PYRONITES_PROJECT_ID is not configured")
        _client = PyroClient(
            settings.PYRONITES_URL,
            settings.PYRONITES_KEY,
            settings.PYRONITES_PROJECT_ID,
        )
    return _client


def build_where(clauses: Iterable[str]) -> str:
    """Join SQL conditions into a WHERE body."""
    parts = [c for c in clauses if c]
    return " AND ".join(parts) if parts else "1=1"


async def fetch_all(
    table: str,
    *,
    where: Optional[List[str]] = None,
    order_by: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Read rows through the SQL API (supports ORDER BY, ranges and limits)."""
    statement = f"SELECT * FROM {sql_ident(table)}"
    if where:
        statement += f" WHERE {build_where(where)}"
    if order_by:
        statement += f" ORDER BY {order_by}"
    if limit is not None:
        statement += f" LIMIT {int(limit)}"
    if offset is not None:
        statement += f" OFFSET {int(offset)}"
    return await get_pyro().sql(statement)


async def upsert_row(
    table: str,
    row_id: str,
    row: Dict[str, Any],
    *,
    update_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Insert a row, or update it by id when it already exists."""
    payload = {"id": row_id, **row}
    columns = ", ".join(sql_ident(c) for c in payload)
    values = ", ".join(sql_literal(payload[c]) for c in payload)
    if update_columns is None:
        update_columns = [c for c in payload if c != "id"]
    assignments = ", ".join(
        f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in update_columns
    )
    statement = (
        f"INSERT INTO {sql_ident(table)} ({columns}) VALUES ({values}) "
        f"ON CONFLICT(id) DO UPDATE SET {assignments} RETURNING *"
    )
    rows = await get_pyro().sql(statement)
    return rows[0] if rows else {}
