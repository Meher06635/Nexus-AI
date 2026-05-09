"""
SQLite database layer for Nexus AI.
Stores conversation turns, automation task history, and user-requested memories ("remember this").
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Thin wrapper around sqlite3 with Nexus-specific schema."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Create tables if they do not exist."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_session
                    ON conversations(session_id, created_at);

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    result TEXT,
                    status TEXT NOT NULL,
                    tool_trace TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    # --- Conversations ---
    def add_message(self, session_id: str, role: str, content: str) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO conversations (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, _utc_now()),
            )
            return int(cur.lastrowid)

    def recent_messages(self, session_id: str, limit: int = 24) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT role, content, created_at FROM conversations
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()
        rows.reverse()
        return [dict(r) for r in rows]

    # --- Task history ---
    def log_task(
        self,
        command: str,
        result: str | None,
        status: str,
        tool_trace: list[dict[str, Any]] | None = None,
    ) -> int:
        trace_json = json.dumps(tool_trace or [])
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO tasks (command, result, status, tool_trace, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (command, result, status, trace_json, _utc_now()),
            )
            return int(cur.lastrowid)

    def recent_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT id, command, result, status, tool_trace, created_at
                FROM tasks ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
            rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["tool_trace"] = json.loads(d["tool_trace"] or "[]")
            except json.JSONDecodeError:
                d["tool_trace"] = []
            out.append(d)
        return out

    # --- Explicit memories ---
    def remember(self, content: str) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO memories (content, created_at) VALUES (?, ?)",
                (content.strip(), _utc_now()),
            )
            return int(cur.lastrowid)

    def list_memories(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, content, created_at FROM memories ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
