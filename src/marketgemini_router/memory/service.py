# src/marketgemini_router/memory/service.py

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional


# DB lives at: src/marketgemini_router/memory.db
DB_PATH = Path(__file__).resolve().parents[1] / "memory.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_memory_user_id_created_at
    ON user_memory (user_id, created_at DESC);
"""


class MemoryService:
    """
    Very simple SQLite-backed user memory service.

    - add_event(user_id, session_id, kind, text)
    - get_recent_memory(user_id, limit)
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        conn = self._conn()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    # --- Public API ---------------------------------------------------------

    def add_event(
        self,
        user_id: str,
        session_id: Optional[str],
        kind: str,
        text: str,
    ) -> None:
        """
        Store a simple memory row for this user.
        """
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO user_memory (user_id, session_id, kind, text)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, session_id, kind, text),
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent_memory(self, user_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Fetch the most recent memory rows for this user_id.
        """
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                SELECT id, user_id, session_id, kind, text, created_at
                FROM user_memory
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        items: List[Dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "id": r[0],
                    "user_id": r[1],
                    "session_id": r[2],
                    "kind": r[3],
                    "text": r[4],
                    "created_at": r[5],
                }
            )
        return items


# --- Safety helpers used by app.py ------------------------------------------


def assert_single_user_context(items: List[Dict[str, Any]], expected_user_id: str) -> None:
    """
    Ensure that all memory rows belong to the same user_id.
    If not, raise RuntimeError to prevent cross-user leakage.
    """
    user_ids = {it.get("user_id") for it in items if it.get("user_id")}
    if not user_ids:
        # no memory or no user_id → nothing to check
        return

    if len(user_ids) > 1:
        raise RuntimeError(
            f"user_memory leak detected: multiple user_ids in memory: {user_ids}"
        )

    only_id = next(iter(user_ids))
    if only_id != expected_user_id:
        raise RuntimeError(
            f"user_memory mismatch: expected {expected_user_id}, got {only_id}"
        )


def build_memory_context(items: List[Dict[str, Any]]) -> str:
    """
    Build a compact system message from memory items.

    You can later make this richer (include timestamps, kinds, etc.).
    For now we just join texts as bullets.
    """
    if not items:
        return ""

    lines: List[str] = ["Recent context from your past requests:"]

    # reverse so oldest is first
    for it in reversed(items):
        txt = it.get("text", "").strip()
        if not txt:
            continue
        lines.append(f"- {txt}")

    return "\n".join(lines)
