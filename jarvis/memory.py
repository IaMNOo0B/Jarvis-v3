"""Local provenance-aware memory store with explicit, auditable forgetting."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: int
    content: str
    source: str
    created_at: str


class MemoryStore:
    """Small local SQLite store. It does not infer, inject, or auto-save memories."""

    def __init__(self, database_path: str | Path = "jarvis-data/memory.sqlite3") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS memory_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                operation TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=5.0)
        db.row_factory = sqlite3.Row
        return db

    def remember(self, content: str, *, source: str) -> MemoryRecord:
        value, provenance = content.strip(), source.strip()
        if not value or len(value) > 4000:
            raise ValueError("Memory must contain 1–4000 characters.")
        if not provenance or len(provenance) > 200:
            raise ValueError("A source/provenance label is required.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute("INSERT INTO memories(content,source,created_at) VALUES(?,?,?)", (value, provenance, now))
            row = db.execute("SELECT * FROM memories WHERE id=?", (cursor.lastrowid,)).fetchone()
        return self._from_row(row)

    def list(self, limit: int = 100) -> list[MemoryRecord]:
        if not 1 <= limit <= 500:
            raise ValueError("Memory list limit must be between 1 and 500.")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._from_row(row) for row in rows]

    def forget(self, memory_id: int) -> bool:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            row = db.execute("SELECT id FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                return False
            db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            db.execute("INSERT INTO memory_audit(memory_id,operation,occurred_at) VALUES(?,?,?)",
                       (memory_id, "forgotten", now))
        return True

    def forget_all(self, *, confirmed: bool = False) -> int:
        if not confirmed:
            raise PermissionError("Forgetting all memories requires explicit confirmation.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            ids = [int(row["id"]) for row in db.execute("SELECT id FROM memories").fetchall()]
            db.executemany("INSERT INTO memory_audit(memory_id,operation,occurred_at) VALUES(?,?,?)",
                           [(memory_id, "forgotten_all", now) for memory_id in ids])
            db.execute("DELETE FROM memories")
        return len(ids)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(int(row["id"]), row["content"], row["source"], row["created_at"])


def parse_natural_remember_request(request: str) -> str | None:
    """Extract explicit natural-language remember requests; never infer memories."""
    text = request.strip()
    lowered = text.casefold()
    prefixes = (
        "i want you to remember that ",
        "jarvis, please remember that ", "jarvis please remember that ",
        "please remember that ", "remember that ",
        "jarvis, remember that ", "jarvis remember that ",
        "please remember ", "remember ",
    )
    for prefix in prefixes:
        if lowered.startswith(prefix):
            content = text[len(prefix):].strip()
            # Do not mistake a reminder command for a memory request.
            if content.casefold().startswith(("to ", "me to ", "me in ", "me at ", "me tomorrow ")):
                return None
            return content or None
    return None


def is_sensitive_memory_request(content: str) -> bool:
    """Conservatively reject explicit attempts to store credentials or access secrets."""
    import re

    patterns = (
        r"\bpassword\b", r"\bpasscode\b", r"\bapi[ _-]?key\b",
        r"\baccess token\b", r"\bprivate key\b", r"\brecovery code\b",
        r"\bone[- ]time code\b", r"\botp\b", r"\bsecret token\b",
    )
    return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)
