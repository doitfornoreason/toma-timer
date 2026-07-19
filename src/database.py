"""SQLite-backed session logging for Toma Timer.

Schema:
  sessions - one row per completed (or aborted) pomodoro session
  settings_audit - (future use) track config changes

All timestamps are ISO-8601 UTC strings for portability across exports.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import get_db_path, load

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_type    TEXT NOT NULL,           -- 'focus' | 'short_break' | 'long_break'
    started_at      TEXT NOT NULL,           -- ISO-8601 UTC
    ended_at        TEXT,                    -- ISO-8601 UTC, NULL if still running
    planned_minutes INTEGER NOT NULL,        -- configured duration
    actual_seconds  INTEGER,                 -- elapsed seconds (NULL until ended)
    completed       INTEGER NOT NULL DEFAULT 0,  -- 1 if ran to completion, 0 if stopped early
    label           TEXT DEFAULT ''          -- free-text tag (e.g. task name)
);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_type    ON sessions(session_type);
"""


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path(load())
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # safer for background writes
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_conn(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a connection. Commits on success, rolls back on error."""
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """Create tables if they don't exist."""
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_session(
    session_type: str,
    planned_minutes: int,
    label: str = "",
    db_path: Path | None = None,
) -> int:
    """Record the start of a session. Returns the new row id."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO sessions (session_type, started_at, planned_minutes, label)
               VALUES (?, ?, ?, ?)""",
            (session_type, now_iso(), planned_minutes, label),
        )
        return cur.lastrowid


def end_session(
    session_id: int,
    completed: bool,
    actual_seconds: int,
    db_path: Path | None = None,
) -> None:
    """Record the end of a session."""
    with get_conn(db_path) as conn:
        conn.execute(
            """UPDATE sessions
               SET ended_at = ?, actual_seconds = ?, completed = ?
               WHERE id = ?""",
            (now_iso(), actual_seconds, 1 if completed else 0, session_id),
        )


def get_all_sessions(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Return all sessions, oldest first."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_sessions_since(
    since: datetime,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return sessions started at or after `since`."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM sessions WHERE started_at >= ? ORDER BY started_at ASC",
            (since.isoformat(),),
        ).fetchall()
        return [dict(r) for r in rows]


def count_rows(db_path: Path | None = None) -> int:
    with get_conn(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
