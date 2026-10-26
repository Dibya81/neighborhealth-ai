"""Tiny database layer: SQLite for zero-setup development, Postgres + PostGIS in docker/production.

SQL is written once with `?` placeholders; they're converted for psycopg. Rows come back as dicts.
Migrations are plain .sql files applied in order and recorded in `schema_migrations`.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.settings import get_settings

MIGRATIONS = Path(__file__).parent / "migrations"
_pool = None
_lock = threading.Lock()


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pg_pool():
    global _pool
    with _lock:
        if _pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
            _pool = ConnectionPool(get_settings().database_url, min_size=1, max_size=10,
                                   kwargs={"row_factory": dict_row, "autocommit": False})
    return _pool


@contextmanager
def connect() -> Iterator[Any]:
    s = get_settings()
    if s.is_postgres:
        with _pg_pool().connection() as conn:
            yield conn
    else:
        path = s.database_url.replace("sqlite:///", "")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _sql(q: str) -> str:
    return q.replace("?", "%s") if get_settings().is_postgres else q


def _row(r) -> dict | None:
    return None if r is None else dict(r)


def fetchall(q: str, params: tuple | list = ()) -> list[dict]:
    with connect() as c:
        cur = c.execute(_sql(q), tuple(params))
        return [dict(r) for r in cur.fetchall()]


def fetchone(q: str, params: tuple | list = ()) -> dict | None:
    with connect() as c:
        cur = c.execute(_sql(q), tuple(params))
        return _row(cur.fetchone())


def execute(q: str, params: tuple | list = ()) -> int:
    with connect() as c:
        cur = c.execute(_sql(q), tuple(params))
        if get_settings().is_postgres:
            c.commit()
        return cur.rowcount


def insert(table: str, values: dict) -> dict:
    values = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in values.items()}
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(values.values()))
    return values


def update(table: str, row_id: str, values: dict) -> None:
    values = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in values.items()}
    sets = ", ".join(f"{k} = ?" for k in values)
    execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*values.values(), row_id])


def migrate() -> list[str]:
    s = get_settings()
    applied: list[str] = []
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT)")
        done = {r["name"] if isinstance(r, dict) else r[0] for r in c.execute("SELECT name FROM schema_migrations").fetchall()}
        files = sorted(MIGRATIONS.glob("common/*.sql"))
        if s.is_postgres:
            files += sorted(MIGRATIONS.glob("postgres/*.sql"))
        for f in files:
            key = f"{f.parent.name}/{f.name}"
            if key in done:
                continue
            sql = f.read_text()
            if s.is_postgres:
                c.execute(sql)
            else:
                c.executescript(sql)
            c.execute(_sql("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)"), (key, now()))
            applied.append(key)
        if s.is_postgres:
            c.commit()
    return applied


def loads(v, default=None):
    if v is None:
        return default
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return default
