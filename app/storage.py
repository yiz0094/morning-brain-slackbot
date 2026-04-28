"""SQLite 영속 계층 — 세션, 풀 인덱스, 일일 API 카운트, Notion fallback 큐."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

from . import config
from .models import (
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    Session,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    exercise_type TEXT NOT NULL,
    slack_channel TEXT,
    slack_ts TEXT,
    notion_page_id TEXT,
    notion_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    exercise_content TEXT,
    answer TEXT,
    feedback TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    reminded_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_sessions_slack_ts ON sessions(slack_ts);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_notion_sync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    operation TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL,
    synced_at TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    parent = Path(config.SQLITE_PATH).parent
    if str(parent) and str(parent) != ".":
        parent.mkdir(parents=True, exist_ok=True)
    with _connect() as c:
        c.executescript(_SCHEMA)


@contextmanager
def _cursor() -> Iterator[sqlite3.Cursor]:
    conn = _connect()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()


# ---- meta (key-value) ----

def get_meta(key: str) -> Optional[str]:
    with _cursor() as c:
        row = c.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with _cursor() as c:
        c.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ---- 풀 인덱스 ----

def get_last_pool_index() -> int:
    val = get_meta("last_pool_index")
    return int(val) if val is not None else -1


def save_last_pool_index(idx: int) -> None:
    set_meta("last_pool_index", str(idx))


# ---- 일일 API 카운트 ----

def can_call_api() -> bool:
    today = str(date.today())
    last_date = get_meta("daily_api_count_date")
    if last_date != today:
        return True
    count = int(get_meta("daily_api_count") or 0)
    return count < config.DAILY_API_CAP


def record_api_call() -> None:
    today = str(date.today())
    last_date = get_meta("daily_api_count_date")
    if last_date != today:
        set_meta("daily_api_count_date", today)
        set_meta("daily_api_count", "1")
    else:
        count = int(get_meta("daily_api_count") or 0)
        set_meta("daily_api_count", str(count + 1))


# ---- 세션 ----

def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        exercise_type=row["exercise_type"],
        slack_channel=row["slack_channel"],
        slack_ts=row["slack_ts"],
        notion_page_id=row["notion_page_id"],
        notion_url=row["notion_url"],
        status=row["status"],
        exercise_content=row["exercise_content"],
        answer=row["answer"],
        feedback=row["feedback"],
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=(
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"] else None
        ),
        reminded_at=(
            datetime.fromisoformat(row["reminded_at"])
            if row["reminded_at"] else None
        ),
    )


def create_session(
    *, today: date, exercise_type: str, exercise_content: str
) -> int:
    """슬랙/노션 결과는 나중에 attach. 일단 row만 만든다."""
    now = datetime.utcnow().isoformat()
    with _cursor() as c:
        cur = c.execute(
            "INSERT INTO sessions"
            "(date, exercise_type, exercise_content, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(today), exercise_type, exercise_content, STATUS_PENDING, now),
        )
        return cur.lastrowid


def attach_slack(session_id: int, channel: str, ts: str) -> None:
    with _cursor() as c:
        c.execute(
            "UPDATE sessions SET slack_channel = ?, slack_ts = ? WHERE id = ?",
            (channel, ts, session_id),
        )


def attach_notion(session_id: int, page_id: str, page_url: str) -> None:
    with _cursor() as c:
        c.execute(
            "UPDATE sessions SET notion_page_id = ?, notion_url = ? WHERE id = ?",
            (page_id, page_url, session_id),
        )


def get_session_by_slack_ts(ts: str) -> Optional[Session]:
    with _cursor() as c:
        row = c.execute(
            "SELECT * FROM sessions WHERE slack_ts = ?", (ts,)
        ).fetchone()
        return _row_to_session(row) if row else None


def get_session_by_date(d: date) -> Optional[Session]:
    with _cursor() as c:
        row = c.execute(
            "SELECT * FROM sessions WHERE date = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (str(d),),
        ).fetchone()
        return _row_to_session(row) if row else None


def get_today_pending_sessions() -> list[Session]:
    today = str(date.today())
    with _cursor() as c:
        rows = c.execute(
            "SELECT * FROM sessions WHERE date = ? AND status = ?",
            (today, STATUS_PENDING),
        ).fetchall()
        return [_row_to_session(r) for r in rows]


def save_answer_and_feedback(
    *, slack_ts: str, answer: str, feedback: str
) -> None:
    now = datetime.utcnow().isoformat()
    with _cursor() as c:
        c.execute(
            "UPDATE sessions SET answer = ?, feedback = ?, status = ?, "
            "completed_at = ? WHERE slack_ts = ?",
            (answer, feedback, STATUS_COMPLETED, now, slack_ts),
        )


def mark_skipped(slack_ts: str) -> None:
    now = datetime.utcnow().isoformat()
    with _cursor() as c:
        c.execute(
            "UPDATE sessions SET status = ?, completed_at = ? "
            "WHERE slack_ts = ?",
            (STATUS_SKIPPED, now, slack_ts),
        )


def mark_reminded(session_id: int) -> None:
    now = datetime.utcnow().isoformat()
    with _cursor() as c:
        c.execute(
            "UPDATE sessions SET reminded_at = ? WHERE id = ?",
            (now, session_id),
        )


def recent_summaries_for_type(
    exercise_type: str, days: int = 7
) -> list[str]:
    """최근 N일간 같은 타입 운동 콘텐츠의 앞 200자."""
    since = (date.today() - timedelta(days=days)).isoformat()
    with _cursor() as c:
        rows = c.execute(
            "SELECT exercise_content FROM sessions "
            "WHERE exercise_type = ? AND date >= ? "
            "AND exercise_content IS NOT NULL "
            "ORDER BY date DESC",
            (exercise_type, since),
        ).fetchall()
    return [r["exercise_content"][:200] for r in rows]


def get_streak() -> int:
    """오늘부터 거꾸로 연속 평일 completed 일수."""
    streak = 0
    d = date.today()
    while True:
        if d.weekday() >= 5:
            d -= timedelta(days=1)
            continue
        s = get_session_by_date(d)
        if not s or s.status != STATUS_COMPLETED:
            break
        streak += 1
        d -= timedelta(days=1)
    return streak


def get_recent_weekday_history(weekdays: int = 14) -> str:
    """가장 오래된 → 최신 순으로 N평일의 이모지 문자열."""
    days: list[str] = []
    d = date.today()
    while len(days) < weekdays:
        if d.weekday() < 5:
            s = get_session_by_date(d)
            if not s:
                days.append("⬛")
            elif s.status == STATUS_COMPLETED:
                days.append("✅")
            elif s.status == STATUS_SKIPPED:
                days.append("⏭")
            else:
                days.append("⬛")
        d -= timedelta(days=1)
    return "".join(reversed(days))


def get_history_for_type(exercise_type: str, limit: int = 5) -> list[Session]:
    with _cursor() as c:
        rows = c.execute(
            "SELECT * FROM sessions WHERE exercise_type = ? "
            "ORDER BY date DESC LIMIT ?",
            (exercise_type, limit),
        ).fetchall()
        return [_row_to_session(r) for r in rows]


def get_recent_history(limit: int = 5) -> list[Session]:
    with _cursor() as c:
        rows = c.execute(
            "SELECT * FROM sessions ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_session(r) for r in rows]


# ---- Notion fallback 큐 ----

def queue_notion_sync(
    session_id: int, operation: str, payload: Optional[dict] = None
) -> None:
    now = datetime.utcnow().isoformat()
    with _cursor() as c:
        c.execute(
            "INSERT INTO pending_notion_sync"
            "(session_id, operation, payload, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, operation, json.dumps(payload or {}), now),
        )


def get_pending_notion_syncs() -> list[dict]:
    with _cursor() as c:
        rows = c.execute(
            "SELECT * FROM pending_notion_sync WHERE synced_at IS NULL "
            "ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def mark_synced(sync_id: int) -> None:
    now = datetime.utcnow().isoformat()
    with _cursor() as c:
        c.execute(
            "UPDATE pending_notion_sync SET synced_at = ? WHERE id = ?",
            (now, sync_id),
        )
