"""Persistent task receipts that distinguish observed outcomes from user-goal success.

Receipts are local audit records. They never authorize actions or claim more than
the supplied evidence proves.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3


OUTCOMES = {
    "response_generated",
    "action_accepted",
    "action_failed",
    "provider_failed",
    "research_succeeded",
    "research_failed",
}


def _redact(value: str, limit: int) -> str:
    value = re.sub(
        r"(?i)\b(api[_ -]?key|token|password|passwd|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]", value,
    )
    value = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED_API_KEY]", value)
    value = re.sub(r"\bAQ\.[0-9A-Za-z._-]{30,}", "[REDACTED_API_KEY]", value)
    value = re.sub(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED_TOKEN]", value)
    return value[:limit]


class TaskReceiptStore:
    """SQLite task history with bounded fields and explicit evidence labels."""

    def __init__(self, database_path: str | Path = "jarvis-data/task-receipts.sqlite3") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS task_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                outcome TEXT NOT NULL,
                evidence TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path)
        db.row_factory = sqlite3.Row
        return db

    def record(self, task: str, outcome: str, *, evidence: str = "") -> dict:
        if not isinstance(task, str) or not task.strip() or len(task) > 4000:
            raise ValueError("Task must contain 1–4000 characters.")
        if outcome not in OUTCOMES:
            raise ValueError("Unsupported evidence-labelled outcome.")
        if not isinstance(evidence, str) or len(evidence) > 4000:
            raise ValueError("Evidence must be text up to 4000 characters.")
        if not isinstance(task, str) or not isinstance(evidence, str):
            raise ValueError("Task and evidence must be text.")
        task = _redact(task.strip(), 1000)
        evidence = _redact(evidence.strip(), 2000)
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO task_receipts(task, outcome, evidence, created_at) VALUES (?, ?, ?, ?)",
                (task, outcome, evidence, created_at),
            )
            row = db.execute("SELECT * FROM task_receipts WHERE id=?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def recent(self, limit: int = 10) -> list[dict]:
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM task_receipts ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]
