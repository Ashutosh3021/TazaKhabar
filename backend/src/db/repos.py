"""
Table access for the Pyronites store.

Everything the API and services need from the database goes through this
module. Reads use the SQL endpoint (ORDER BY, ranges, counts); writes use the
row API (JSON body, no string interpolation) or an upsert through the SQL
endpoint.

JSON columns come back as JSON text and must be decoded, and datetimes come
back as ISO strings.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.db.pyro import get_pyro, sql_ident, sql_literal

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    """Current UTC timestamp in the format Pyronites stores."""
    return datetime.now(timezone.utc).isoformat()


def _json_field(row: Dict[str, Any], key: str, default: Any) -> Any:
    value = row.get(key)
    if value is None:
        return default
    if isinstance(value, (list, dict, int, float, bool)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "t"}
    return False


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _decode_dt(value: Any) -> Optional[datetime]:
    """Parse a stored timestamp into a datetime (naive UTC)."""
    text = _iso(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------


def _profile_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "email": row.get("email"),
        "roles": _json_field(row, "roles", []),
        "experience_level": row.get("experience_level") or "I",
        "resume_path": row.get("resume_path"),
        "resume_text": row.get("resume_text"),
        "ats_score": row.get("ats_score"),
        "ats_critical_issues": _json_field(row, "ats_critical_issues", []),
        "ats_missing_keywords": _json_field(row, "ats_missing_keywords", []),
        "ats_suggested_additions": _json_field(row, "ats_suggested_additions", []),
        "last_analysis_at": _iso(row.get("last_analysis_at")),
        "preferences": _json_field(row, "preferences", {}),
        "feed_last_seen_at": _iso(row.get("feed_last_seen_at")),
        "created_at": _iso(row.get("created_at")),
    }


async def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().rows("profiles", where={"id": user_id})
    return _profile_row(rows[0]) if rows else None


async def all_profiles() -> List[Dict[str, Any]]:
    rows = await get_pyro().sql('SELECT * FROM "profiles"')
    return [_profile_row(row) for row in rows]


# ---------------------------------------------------------------------------
# accounts (OAuth identities: Google, GitHub)
# ---------------------------------------------------------------------------


def _account_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "provider": row.get("provider"),
        "provider_id": row.get("provider_id"),
        "email": row.get("email"),
        "name": row.get("name"),
        "avatar_url": row.get("avatar_url"),
        "email_verified": _bool(row.get("email_verified")),
        "created_at": _iso(row.get("created_at")),
        "last_login_at": _iso(row.get("last_login_at")),
    }


async def get_account(account_id: str) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f"SELECT * FROM \"accounts\" WHERE id = {sql_literal(account_id)} LIMIT 1"
    )
    return _account_row(rows[0]) if rows else None


async def upsert_account(
    provider: str,
    provider_id: str,
    email: str,
    name: str = "",
    avatar_url: str = "",
    email_verified: bool = False,
) -> Dict[str, Any]:
    """
    Find or create the account for an OAuth identity.

    The same provider identity always maps to the same account. An account is
    also linked by email when the provider verified that email, which is what
    keeps one person to one account across providers.
    """
    now = now_iso()

    existing = await get_pyro().sql(
        "SELECT * FROM \"accounts\" WHERE provider = "
        f"{sql_literal(provider)} AND provider_id = {sql_literal(provider_id)} LIMIT 1"
    )

    if existing:
        row = existing[0]
        await get_pyro().sql(
            "UPDATE \"accounts\" SET email = "
            f"{sql_literal(email)}, name = {sql_literal(name or row.get('name') or '')}, "
            f"avatar_url = {sql_literal(avatar_url or row.get('avatar_url') or '')}, "
            f"last_login_at = {sql_literal(now)} WHERE id = {sql_literal(row['id'])}"
        )
        return await get_account(row["id"]) or {}

    if email and email_verified:
        by_email = await get_pyro().sql(
            f"SELECT id FROM \"accounts\" WHERE email = {sql_literal(email)} LIMIT 1"
        )
        if by_email:
            account_id = by_email[0]["id"]
            await get_pyro().sql(
                "UPDATE \"accounts\" SET provider = "
                f"{sql_literal(provider)}, provider_id = {sql_literal(provider_id)}, "
                f"name = {sql_literal(name)}, avatar_url = {sql_literal(avatar_url)}, "
                f"last_login_at = {sql_literal(now)} WHERE id = {sql_literal(account_id)}"
            )
            return await get_account(account_id) or {}

    account_id = uuid.uuid4().hex
    row = {
        "id": account_id,
        "provider": provider,
        "provider_id": provider_id,
        "email": email,
        "name": name,
        "avatar_url": avatar_url,
        "email_verified": bool(email_verified),
        "created_at": now,
        "last_login_at": now,
    }
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    await get_pyro().exec(
        f"INSERT INTO \"accounts\" ({columns}) VALUES ({values})"
    )
    return await get_account(account_id) or {}


async def job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f"SELECT * FROM \"jobs\" WHERE id = {sql_literal(job_id)} LIMIT 1"
    )
    return _job_row(rows[0]) if rows else None


async def save_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or update a profile row and return the stored version."""
    payload: Dict[str, Any] = {"id": user_id}
    payload.update({k: v for k, v in updates.items() if v is not None})
    payload.setdefault("created_at", now_iso())
    columns = ", ".join(sql_ident(c) for c in payload)
    values = ", ".join(sql_literal(payload[c]) for c in payload)
    assignments = ", ".join(
        f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in payload if c != "id"
    )
    statement = (
        f"INSERT INTO \"profiles\" ({columns}) VALUES ({values}) "
        f"ON CONFLICT(id) DO UPDATE SET {assignments} RETURNING *"
    )
    rows = await get_pyro().sql(statement)
    return _profile_row(rows[0]) if rows else {}


async def set_feed_last_seen(user_id: str, timestamp: Optional[str] = None) -> str:
    """Mark everything up to now as seen for this user."""
    stamp = timestamp or now_iso()
    await save_profile(user_id, {"feed_last_seen_at": stamp})
    return stamp


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------


def _job_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "hn_item_id": row.get("hn_item_id"),
        "title": row.get("title"),
        "company": row.get("company"),
        "location": row.get("location"),
        "tags": _json_field(row, "tags", []),
        "email_contact": row.get("email_contact"),
        "apply_link": row.get("apply_link"),
        "is_ghost_job": _bool(row.get("is_ghost_job")),
        "deadline": row.get("deadline"),
        "posted_at": _iso(row.get("posted_at")),
        "scraped_at": _iso(row.get("scraped_at")),
        "cleaned_title": row.get("cleaned_title"),
        "cleaned_company": row.get("cleaned_company"),
        "role": row.get("role"),
        "description": row.get("description"),
        "processed": _bool(row.get("processed")),
    }


def _job_conditions(
    roles: Optional[Sequence[str]] = None,
    remote: bool = False,
    since: Optional[str] = None,
) -> List[str]:
    conditions: List[str] = []
    if remote:
        conditions.append(
            "(LOWER(location) LIKE '%remote%' OR LOWER(location) LIKE '%work from home%'"
            " OR LOWER(location) LIKE '%wfh%' OR LOWER(location) LIKE '%anywhere%'"
            " OR LOWER(location) LIKE '%distributed%')"
        )
    if roles:
        role_parts = [
            f"(LOWER(COALESCE(role, '')) LIKE {sql_literal('%' + r.lower() + '%')})"
            for r in roles
            if r
        ]
        if role_parts:
            conditions.append("(" + " OR ".join(role_parts) + ")")
    if since:
        conditions.append(f"scraped_at > {sql_literal(since)}")
    return conditions


async def count_jobs(
    roles: Optional[Sequence[str]] = None,
    remote: bool = False,
    since: Optional[str] = None,
) -> int:
    conditions = _job_conditions(roles, remote, since)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await get_pyro().sql(f'SELECT COUNT(*) AS n FROM "jobs" WHERE {where}')
    return _int(rows[0].get("n")) if rows else 0


async def list_jobs(
    roles: Optional[Sequence[str]] = None,
    remote: bool = False,
    skip: int = 0,
    limit: int = 20,
    since: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conditions = _job_conditions(roles, remote, since)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await get_pyro().sql(
        f'SELECT * FROM "jobs" WHERE {where} ORDER BY scraped_at DESC LIMIT {int(limit)} OFFSET {int(skip)}'
    )
    return [_job_row(row) for row in rows]


async def list_jobs_page(
    roles: Optional[Sequence[str]] = None,
    remote: bool = False,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """One round trip: the page plus the total count of the filtered set."""
    conditions = _job_conditions(roles, remote)
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await get_pyro().sql(
        f'SELECT *, COUNT(*) OVER () AS _total FROM "jobs" WHERE {where} '
        f"ORDER BY scraped_at DESC LIMIT {int(limit)} OFFSET {int(skip)}"
    )
    total = 0
    page: List[Dict[str, Any]] = []
    for row in rows:
        total = _int(row.pop("_total", 0))
        page.append(_job_row(row))
    return page, total


async def job_by_hn_item_id(hn_item_id: int) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().rows("jobs", where={"hn_item_id": hn_item_id})
    return _job_row(rows[0]) if rows else None


async def jobs_by_ids(job_ids: Sequence[str]) -> List[Dict[str, Any]]:
    if not job_ids:
        return []
    quoted = ", ".join(sql_literal(i) for i in job_ids)
    rows = await get_pyro().sql(f'SELECT * FROM "jobs" WHERE id IN ({quoted})')
    return [_job_row(row) for row in rows]


async def unprocessed_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        "SELECT * FROM \"jobs\" WHERE COALESCE(processed, 0) = 0 "
        f"ORDER BY scraped_at DESC LIMIT {int(limit)}"
    )
    return [_job_row(row) for row in rows]


async def jobs_for_embedding(limit: int = 200) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f'SELECT id, title, company, location FROM "jobs" ORDER BY scraped_at DESC LIMIT {int(limit)}'
    )
    return rows


async def role_counts() -> List[Tuple[str, int]]:
    rows = await get_pyro().sql(
        'SELECT role, COUNT(*) AS n FROM "jobs" WHERE role IS NOT NULL AND role != "" GROUP BY role ORDER BY n DESC'
    )
    return [(row.get("role"), _int(row.get("n"))) for row in rows]


async def sample_job_for_role(role: str) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f"SELECT * FROM \"jobs\" WHERE role = {sql_literal(role)} ORDER BY scraped_at DESC LIMIT 1"
    )
    return _job_row(rows[0]) if rows else None


async def count_jobs_matching(text: str) -> int:
    pattern = f"%{text.lower()}%"
    rows = await get_pyro().sql(
        "SELECT COUNT(*) AS n FROM \"jobs\" "
        f"WHERE LOWER(title) LIKE {sql_literal(pattern)} "
        f"OR LOWER(COALESCE(tags, '')) LIKE {sql_literal(pattern)}"
    )
    return _int(rows[0].get("n")) if rows else 0


async def jobs_text_since(since: str) -> List[Dict[str, Any]]:
    """Titles and tags of jobs scraped at or after ``since``."""
    rows = await get_pyro().sql(
        f"SELECT title, tags FROM \"jobs\" WHERE scraped_at >= {sql_literal(since)}"
    )
    return [
        {"title": row.get("title"), "tags": _json_field(row, "tags", [])} for row in rows
    ]


async def news_text_since(since: str) -> List[Dict[str, Any]]:
    """Titles and summaries of news scraped at or after ``since``."""
    rows = await get_pyro().sql(
        f"SELECT title, summary FROM \"news\" WHERE scraped_at >= {sql_literal(since)}"
    )
    return rows


async def news_without_embeddings(limit: int = 200) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        "SELECT id, title, summary, type FROM \"news\" WHERE id NOT IN "
        "(SELECT item_id FROM \"embeddings\" WHERE item_type = 'news') "
        f"LIMIT {int(limit)}"
    )
    return [
        {
            "id": row.get("id"),
            "title": row.get("title") or "",
            "summary": row.get("summary"),
            "type": row.get("type") or "news",
        }
        for row in rows
    ]


async def jobs_without_embeddings(limit: int = 200) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        "SELECT id, title, company, location FROM \"jobs\" WHERE id NOT IN "
        "(SELECT item_id FROM \"embeddings\" WHERE item_type = 'job') "
        f"LIMIT {int(limit)}"
    )
    return rows


async def upsert_job(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    row = {"id": job_id, **payload}
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    assignments = ", ".join(
        f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in row if c != "id"
    )
    statement = (
        f"INSERT INTO \"jobs\" ({columns}) VALUES ({values}) "
        f"ON CONFLICT(id) DO UPDATE SET {assignments} RETURNING *"
    )
    rows = await get_pyro().sql(statement)
    return _job_row(rows[0]) if rows else {}


async def insert_rows(
    table: str, rows: List[Dict[str, Any]], chunk: int = 100
) -> int:
    """Insert many rows with a handful of statements instead of one call per row."""
    if not rows:
        return 0

    columns = list(rows[0].keys())
    inserted = 0
    for start in range(0, len(rows), chunk):
        batch = rows[start : start + chunk]
        col_sql = ", ".join(sql_ident(c) for c in columns)
        values = ", ".join(
            "(" + ", ".join(sql_literal(row.get(c)) for c in columns) + ")"
            for row in batch
        )
        await get_pyro().exec(
            f"INSERT INTO {sql_ident(table)} ({col_sql}) VALUES {values}"
        )
        inserted += len(batch)
    return inserted


async def existing_jobs_by_hn_item_id() -> Dict[int, Dict[str, Any]]:
    """Map hn_item_id -> {id, deadline, scraped_at} for every stored job."""
    rows = await get_pyro().sql(
        "SELECT id, hn_item_id, deadline, scraped_at FROM \"jobs\" WHERE hn_item_id IS NOT NULL"
    )
    return {int(r["hn_item_id"]): r for r in rows if r.get("hn_item_id") is not None}


async def existing_news_hn_item_ids() -> set:
    rows = await get_pyro().sql(
        "SELECT hn_item_id FROM \"news\" WHERE hn_item_id IS NOT NULL"
    )
    return {int(r["hn_item_id"]) for r in rows if r.get("hn_item_id") is not None}


# ---------------------------------------------------------------------------
# news
# ---------------------------------------------------------------------------


def _news_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row.get("id"),
        "hn_item_id": row.get("hn_item_id"),
        "type": row.get("type"),
        "title": row.get("title"),
        "url": row.get("url"),
        "score": _int(row.get("score")),
        "comment_count": _int(row.get("comment_count")),
        "summary": row.get("summary"),
        "summarized": _bool(row.get("summarized")),
        "summarized_at": _iso(row.get("summarized_at")),
        "scraped_at": _iso(row.get("scraped_at")),
    }


async def count_news(news_type: Optional[str] = None) -> int:
    if news_type:
        rows = await get_pyro().sql(
            f"SELECT COUNT(*) AS n FROM \"news\" WHERE type = {sql_literal(news_type)}"
        )
    else:
        rows = await get_pyro().sql('SELECT COUNT(*) AS n FROM "news"')
    return _int(rows[0].get("n")) if rows else 0


async def count_news_since(since: str) -> int:
    rows = await get_pyro().sql(
        f"SELECT COUNT(*) AS n FROM \"news\" WHERE scraped_at > {sql_literal(since)}"
    )
    return _int(rows[0].get("n")) if rows else 0


async def badge_counts(user_id: Optional[str], fallback_since: str) -> Dict[str, Any]:
    """One round trip: the user's last-seen marker plus both counters."""
    rows = await get_pyro().sql(
        "SELECT 'last_seen' AS k, feed_last_seen_at AS v FROM \"profiles\" "
        f"WHERE id = {sql_literal(user_id or '')} "
        "UNION ALL SELECT 'jobs', COUNT(*) FROM \"jobs\" WHERE scraped_at > "
        f"COALESCE((SELECT feed_last_seen_at FROM \"profiles\" WHERE id = {sql_literal(user_id or '')}), {sql_literal(fallback_since)}) "
        "UNION ALL SELECT 'news', COUNT(*) FROM \"news\" WHERE scraped_at > "
        f"COALESCE((SELECT feed_last_seen_at FROM \"profiles\" WHERE id = {sql_literal(user_id or '')}), {sql_literal(fallback_since)})"
    )
    result: Dict[str, Any] = {"last_seen": None, "new_jobs": 0, "new_news": 0}
    for row in rows:
        key = row.get("k")
        if key == "last_seen":
            result["last_seen"] = _iso(row.get("v"))
        elif key == "jobs":
            result["new_jobs"] = _int(row.get("v"))
        elif key == "news":
            result["new_news"] = _int(row.get("v"))
    return result


async def news_counts_by_type() -> Dict[str, Dict[str, Any]]:
    """Row count and last scrape time per news type."""
    rows = await get_pyro().sql(
        'SELECT type, COUNT(*) AS n, MAX(scraped_at) AS last_scraped FROM "news" GROUP BY type'
    )
    return {
        row.get("type") or "": {
            "count": _int(row.get("n")),
            "last_scraped": _iso(row.get("last_scraped")),
        }
        for row in rows
    }


async def hn_job_stats() -> Dict[str, Any]:
    """Count and last scrape time for jobs that came from HN."""
    rows = await get_pyro().sql(
        'SELECT COUNT(*) AS n, MAX(scraped_at) AS last_scraped FROM "jobs" '
        "WHERE hn_item_id IS NOT NULL"
    )
    if not rows:
        return {"count": 0, "last_scraped": None}
    return {
        "count": _int(rows[0].get("n")),
        "last_scraped": _iso(rows[0].get("last_scraped")),
    }


async def list_news(
    news_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    summarized_only: bool = False,
) -> List[Dict[str, Any]]:
    conditions: List[str] = []
    if news_type:
        conditions.append(f"type = {sql_literal(news_type)}")
    if summarized_only:
        conditions.append("summary IS NOT NULL AND summary != ''")
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await get_pyro().sql(
        f'SELECT * FROM "news" WHERE {where} ORDER BY score DESC, scraped_at DESC '
        f"LIMIT {int(limit)} OFFSET {int(skip)}"
    )
    return [_news_row(row) for row in rows]


async def list_news_page(
    news_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[Dict[str, Any]], int, set]:
    """One round trip: the page, the total count and the featured ids."""
    conditions: List[str] = []
    if news_type:
        conditions.append(f"type = {sql_literal(news_type)}")
    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await get_pyro().sql(
        f'SELECT *, COUNT(*) OVER () AS _total, '
        f"RANK() OVER (ORDER BY score DESC, scraped_at DESC) AS _rank "
        f'FROM "news" WHERE {where} ORDER BY score DESC, scraped_at DESC '
        f"LIMIT {int(limit)} OFFSET {int(skip)}"
    )
    total = 0
    page: List[Dict[str, Any]] = []
    featured: set = set()
    for row in rows:
        total = _int(row.pop("_total", 0))
        rank = _int(row.pop("_rank", 0))
        item = _news_row(row)
        if rank <= 3:
            featured.add(item["id"])
        page.append(item)
    return page, total, featured


async def top_news_ids(limit: int = 3) -> List[str]:
    rows = await get_pyro().sql(
        f'SELECT id FROM "news" ORDER BY score DESC, scraped_at DESC LIMIT {int(limit)}'
    )
    return [row.get("id") for row in rows if row.get("id")]


async def news_by_hn_item_id(hn_item_id: int) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().rows("news", where={"hn_item_id": hn_item_id})
    return _news_row(rows[0]) if rows else None


async def news_by_id(news_id: str) -> Optional[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f"SELECT * FROM \"news\" WHERE id = {sql_literal(news_id)} LIMIT 1"
    )
    return _news_row(rows[0]) if rows else None


async def unsummarized_news(limit: int = 20) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        'SELECT * FROM "news" WHERE COALESCE(summarized, 0) = 0 '
        f"ORDER BY score DESC LIMIT {int(limit)}"
    )
    return [_news_row(row) for row in rows]


async def mark_news_summarized(news_id: str, summary: str) -> None:
    await get_pyro().sql(
        "UPDATE \"news\" SET summary = "
        f"{sql_literal(summary)}, summarized = 1, summarized_at = {sql_literal(now_iso())} "
        f"WHERE id = {sql_literal(news_id)}"
    )


async def upsert_news(news_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    row = {"id": news_id, **payload}
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    assignments = ", ".join(
        f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in row if c != "id"
    )
    statement = (
        f"INSERT INTO \"news\" ({columns}) VALUES ({values}) "
        f"ON CONFLICT(id) DO UPDATE SET {assignments} RETURNING *"
    )
    rows = await get_pyro().sql(statement)
    return _news_row(rows[0]) if rows else {}


# ---------------------------------------------------------------------------
# trends
# ---------------------------------------------------------------------------


async def list_trends(week_start: str) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f"SELECT * FROM \"trends\" WHERE week_start = {sql_literal(week_start)}"
    )
    return [
        {
            "id": row.get("id"),
            "keyword": row.get("keyword"),
            "count": _int(row.get("count")),
            "week_start": _iso(row.get("week_start")),
            "week_end": _iso(row.get("week_end")),
            "percentage_change": float(row.get("percentage_change") or 0.0),
            "direction": row.get("direction"),
        }
        for row in rows
    ]


async def upsert_trend(
    keyword: str,
    count: int,
    week_start: str,
    week_end: str,
    percentage_change: float,
    direction: str,
) -> None:
    await upsert_trends(
        [
            {
                "id": f"{keyword}|{week_start}",
                "keyword": keyword,
                "count": int(count),
                "week_start": week_start,
                "week_end": week_end,
                "percentage_change": float(percentage_change),
                "direction": direction,
            }
        ]
    )


async def upsert_trends(rows: List[Dict[str, Any]], chunk: int = 100) -> int:
    """Upsert many trend rows with a handful of statements, not one per row."""
    if not rows:
        return 0

    columns = list(rows[0].keys())
    written = 0
    for start in range(0, len(rows), chunk):
        batch = rows[start : start + chunk]
        col_sql = ", ".join(sql_ident(c) for c in columns)
        values = ", ".join(
            "(" + ", ".join(sql_literal(row.get(c)) for c in columns) + ")" for row in batch
        )
        assignments = ", ".join(
            f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in columns if c != "id"
        )
        await get_pyro().exec(
            f"INSERT INTO \"trends\" ({col_sql}) VALUES {values} "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}"
        )
        written += len(batch)
    return written


async def distinct_trend_keywords() -> List[str]:
    rows = await get_pyro().sql('SELECT DISTINCT keyword FROM "trends"')
    return [row.get("keyword") for row in rows if row.get("keyword")]


async def trend_history(keyword: str) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        f"SELECT * FROM \"trends\" WHERE keyword = {sql_literal(keyword)} ORDER BY week_start ASC"
    )
    return [
        {
            "count": _int(row.get("count")),
            "week_start": _iso(row.get("week_start")),
            "percentage_change": float(row.get("percentage_change") or 0.0),
        }
        for row in rows
    ]


async def insert_prediction(
    keyword: str, horizon_weeks: int, predicted_count: int, confidence: float
) -> None:
    row = {
        "id": uuid.uuid4().hex,
        "keyword": keyword,
        "horizon_weeks": int(horizon_weeks),
        "predicted_count": int(predicted_count),
        "confidence": float(confidence),
        "predicted_at": now_iso(),
    }
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    await get_pyro().exec(
        f"INSERT INTO \"trend_predictions\" ({columns}) VALUES ({values})"
    )


async def recent_prediction_exists(keyword: str, since: str) -> bool:
    rows = await get_pyro().sql(
        "SELECT id FROM \"trend_predictions\" "
        f"WHERE keyword = {sql_literal(keyword)} AND predicted_at >= {sql_literal(since)} LIMIT 1"
    )
    return bool(rows)


# ---------------------------------------------------------------------------
# rate limits
# ---------------------------------------------------------------------------


def _rate_limit_id(user_id: Optional[str], date: str) -> str:
    return f"{user_id or 'anonymous'}:{date}"


async def get_rate_limit(user_id: Optional[str], date: str) -> int:
    rows = await get_pyro().sql(
        "SELECT request_count FROM \"rate_limits\" "
        f"WHERE id = {sql_literal(_rate_limit_id(user_id, date))}"
    )
    return _int(rows[0].get("request_count")) if rows else 0


async def bump_rate_limit(user_id: Optional[str], date: str) -> int:
    """Increment the counter for this user/date and return the new value."""
    row_id = _rate_limit_id(user_id, date)
    statement = (
        "INSERT INTO \"rate_limits\" (id, user_id, date, request_count, last_request_at) "
        f"VALUES ({sql_literal(row_id)}, {sql_literal(user_id)}, {sql_literal(date)}, 1, {sql_literal(now_iso())}) "
        "ON CONFLICT(id) DO UPDATE SET request_count = request_count + 1, "
        f"last_request_at = {sql_literal(now_iso())} RETURNING request_count"
    )
    rows = await get_pyro().sql(statement)
    return _int(rows[0].get("request_count")) if rows else 0


# ---------------------------------------------------------------------------
# embeddings (base64 text, keeps binary data intact)
# ---------------------------------------------------------------------------


async def get_embedding(item_id: str, item_type: str) -> Optional[bytes]:
    rows = await get_pyro().sql(
        "SELECT embedding FROM \"embeddings\" "
        f"WHERE item_id = {sql_literal(item_id)} AND item_type = {sql_literal(item_type)} LIMIT 1"
    )
    if not rows:
        return None
    value = rows[0].get("embedding")
    if value is None:
        return None
    try:
        return base64.b64decode(value)
    except (TypeError, ValueError):
        return None


async def get_embeddings(
    item_ids: Sequence[str], item_type: str
) -> Dict[str, bytes]:
    if not item_ids:
        return {}
    quoted = ", ".join(sql_literal(i) for i in item_ids)
    rows = await get_pyro().sql(
        "SELECT item_id, embedding FROM \"embeddings\" "
        f"WHERE item_type = {sql_literal(item_type)} AND item_id IN ({quoted})"
    )
    result: Dict[str, bytes] = {}
    for row in rows:
        value = row.get("embedding")
        if value is None:
            continue
        try:
            result[row.get("item_id")] = base64.b64decode(value)
        except (TypeError, ValueError):
            continue
    return result


async def upsert_embedding(item_id: str, item_type: str, blob: bytes) -> None:
    payload = base64.b64encode(blob).decode("ascii")
    await upsert_embeddings(
        [
            {
                "id": f"{item_type}:{item_id}",
                "item_id": item_id,
                "item_type": item_type,
                "embedding": payload,
                "created_at": now_iso(),
            }
        ]
    )


async def upsert_embeddings(rows: List[Dict[str, Any]], chunk: int = 50) -> int:
    """Upsert many embedding rows with a handful of statements."""
    if not rows:
        return 0

    columns = list(rows[0].keys())
    written = 0
    for start in range(0, len(rows), chunk):
        batch = rows[start : start + chunk]
        col_sql = ", ".join(sql_ident(c) for c in columns)
        values = ", ".join(
            "(" + ", ".join(sql_literal(row.get(c)) for c in columns) + ")" for row in batch
        )
        assignments = ", ".join(
            f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in columns if c != "id"
        )
        await get_pyro().exec(
            f"INSERT INTO \"embeddings\" ({col_sql}) VALUES {values} "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}"
        )
        written += len(batch)
    return written


# ---------------------------------------------------------------------------
# observations
# ---------------------------------------------------------------------------


async def latest_observation() -> Optional[Dict[str, Any]]:
    rows = await get_pyro().sql(
        'SELECT * FROM "observations" ORDER BY generated_at DESC LIMIT 1'
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row.get("id"),
        "week_start": _iso(row.get("week_start")),
        "text": row.get("text"),
        "generated_at": _iso(row.get("generated_at")),
    }


async def insert_observation(text: str, week_start: str) -> None:
    row = {
        "id": uuid.uuid4().hex,
        "week_start": week_start,
        "text": text,
        "generated_at": now_iso(),
    }
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    await get_pyro().exec(
        f"INSERT INTO \"observations\" ({columns}) VALUES ({values})"
    )


# ---------------------------------------------------------------------------
# scraper state (keeps the CI runner stateless)
# ---------------------------------------------------------------------------


async def get_state(key: str) -> Optional[str]:
    rows = await get_pyro().sql(
        f"SELECT value FROM \"scraper_state\" WHERE state_key = {sql_literal(key)} LIMIT 1"
    )
    return rows[0].get("value") if rows else None


async def set_state(key: str, value: str) -> None:
    existing = await get_pyro().sql(
        f"SELECT id FROM \"scraper_state\" WHERE state_key = {sql_literal(key)} LIMIT 1"
    )
    row = {
        "id": existing[0].get("id") if existing else uuid.uuid4().hex,
        "state_key": key,
        "value": value,
        "updated_at": now_iso(),
    }
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    assignments = ", ".join(
        f"{sql_ident(c)} = excluded.{sql_ident(c)}" for c in row if c != "id"
    )
    await get_pyro().exec(
        f"INSERT INTO \"scraper_state\" ({columns}) VALUES ({values}) "
        f"ON CONFLICT(id) DO UPDATE SET {assignments}"
    )


# ---------------------------------------------------------------------------
# notifications
# ---------------------------------------------------------------------------


async def queue_notification(user_id: str, job_id: str, match_score: int) -> None:
    row = {
        "id": uuid.uuid4().hex,
        "user_id": user_id,
        "job_id": job_id,
        "match_score": int(match_score),
        "status": "queued",
        "created_at": now_iso(),
    }
    columns = ", ".join(sql_ident(c) for c in row)
    values = ", ".join(sql_literal(row[c]) for c in row)
    await get_pyro().exec(
        f"INSERT INTO \"notifications\" ({columns}) VALUES ({values})"
    )


async def pending_notifications(limit: int = 50) -> List[Dict[str, Any]]:
    rows = await get_pyro().sql(
        "SELECT * FROM \"notifications\" WHERE status = 'queued' "
        f"ORDER BY created_at ASC LIMIT {int(limit)}"
    )
    return rows


async def update_notification_status(notification_id: str, status: str) -> None:
    await get_pyro().sql(
        "UPDATE \"notifications\" SET status = "
        f"{sql_literal(status)}, sent_at = {sql_literal(now_iso())} "
        f"WHERE id = {sql_literal(notification_id)}"
    )


async def existing_job_triples() -> set:
    """(title, company, apply_link) for every stored job, used for CSV dedup."""
    rows = await get_pyro().sql(
        'SELECT title, company, apply_link FROM "jobs"'
    )
    return {
        (row.get("title") or "", row.get("company") or "", row.get("apply_link") or "")
        for row in rows
    }


async def delete_all_jobs() -> int:
    """Remove every stored job (used by the CSV loader's clear_existing mode)."""
    return await get_pyro().exec('DELETE FROM "jobs"')
