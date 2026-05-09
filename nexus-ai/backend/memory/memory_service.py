"""
MemoryService bridges SQLite storage and the LangChain agent prompt.
Builds a compact context block from recent chat + saved memories.
"""

from __future__ import annotations

from typing import Any

from backend.database.db import Database


def _fmt_safe(text: str) -> str:
    """Escape braces so stored memories never break ChatPromptTemplate formatting."""
    return text.replace("{", "{{").replace("}", "}}")


class MemoryService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def persist_exchange(self, session_id: str, user_text: str, assistant_text: str) -> None:
        """Store both sides of a completed assistant turn."""
        self.db.add_message(session_id, "user", user_text)
        self.db.add_message(session_id, "assistant", assistant_text)

    def chat_history_for_prompt(self, session_id: str, limit: int = 16) -> list[tuple[str, str]]:
        """Return (role, content) tuples suitable for MessagesPlaceholder."""
        rows = self.db.recent_messages(session_id, limit=limit)
        return [(r["role"], r["content"]) for r in rows]

    def memories_block(self, limit: int = 12) -> str:
        """Formatted bullet list of user-saved memories for system prompt injection."""
        memories = self.db.list_memories(limit=limit)
        if not memories:
            return "(no saved memories)"
        lines = [f"- [{m['created_at']}] {_fmt_safe(m['content'])}" for m in reversed(memories)]
        return "\n".join(lines)

    def remember_phrase(self, content: str) -> dict[str, Any]:
        """Persist explicit memory; returns ack payload."""
        cid = self.db.remember(content)
        return {"ok": True, "id": cid, "content": content.strip()}
