"""SQLite persistence: one row per check holding the Check JSON."""

import sqlite3
from contextlib import closing
from pathlib import Path

from .models import Check


def init(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS checks (id TEXT PRIMARY KEY, created_at TEXT, data TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS claim_cache "
            "(key TEXT PRIMARY KEY, created_at TEXT, data TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS live_checks (day TEXT PRIMARY KEY, count INTEGER)"
        )


def save(path: Path, check: Check) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "INSERT INTO checks (id, created_at, data) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (check.id, check.created_at, check.model_dump_json()),
        )


def get(path: Path, check_id: str) -> Check | None:
    with closing(sqlite3.connect(path)) as conn:
        row = conn.execute("SELECT data FROM checks WHERE id = ?", (check_id,)).fetchone()
    return Check.model_validate_json(row[0]) if row else None


def list_recent(path: Path, limit: int) -> list[Check]:
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute(
            "SELECT data FROM checks ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
    return [Check.model_validate_json(r[0]) for r in rows]


def cache_get(path: Path, key: str) -> tuple[str, str] | None:
    with closing(sqlite3.connect(path)) as conn:
        row = conn.execute(
            "SELECT created_at, data FROM claim_cache WHERE key = ?", (key,)
        ).fetchone()
    return (row[0], row[1]) if row else None


def cache_put(path: Path, key: str, created_at: str, data: str) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "INSERT INTO claim_cache (key, created_at, data) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET created_at = excluded.created_at, "
            "data = excluded.data",
            (key, created_at, data),
        )


def take_daily_slot(path: Path, day: str, cap: int) -> bool:
    """Count one live check against `day`; False when the day already has `cap` checks."""
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "INSERT INTO live_checks (day, count) VALUES (?, 0) ON CONFLICT(day) DO NOTHING",
            (day,),
        )
        taken = conn.execute(
            "UPDATE live_checks SET count = count + 1 WHERE day = ? AND count < ?", (day, cap)
        )
        return taken.rowcount == 1
