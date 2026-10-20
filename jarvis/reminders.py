"""Persistent local reminders with explicit lifecycle and no background scheduler side effects."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Reminder:
    reminder_id: int
    due_at: str
    message: str
    status: str


class ReminderStore:
    """SQLite-backed reminders; caller owns scheduling and notification delivery."""

    def __init__(self, database_path: str | Path = "jarvis-data/reminders.sqlite3") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                due_at TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','fired','cancelled')),
                created_at TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=5.0)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _normalise_due(value: str) -> str:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Reminder time must include a timezone offset.")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")

    def create(self, due_at: str, message: str) -> Reminder:
        due = self._normalise_due(due_at)
        content = message.strip()
        if not content or len(content) > 2000:
            raise ValueError("Reminder message must contain 1–2000 characters.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute("INSERT INTO reminders(due_at,message,status,created_at) VALUES(?,?,?,?)",
                                (due, content, "pending", now))
            row = db.execute("SELECT * FROM reminders WHERE id=?", (cursor.lastrowid,)).fetchone()
        return self._from_row(row)

    def list(self, *, include_finished: bool = False) -> list[Reminder]:
        query = "SELECT * FROM reminders"
        if not include_finished:
            query += " WHERE status='pending'"
        query += " ORDER BY due_at, id"
        with self._connect() as db:
            rows = db.execute(query).fetchall()
        return [self._from_row(row) for row in rows]

    def due(self, now: datetime | None = None) -> list[Reminder]:
        current = (now or datetime.now(timezone.utc))
        if current.tzinfo is None:
            raise ValueError("Current time must include a timezone offset.")
        current_iso = current.astimezone(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM reminders WHERE status='pending' AND due_at<=? ORDER BY due_at,id",
                              (current_iso,)).fetchall()
        return [self._from_row(row) for row in rows]

    def mark_fired(self, reminder_id: int) -> bool:
        with self._connect() as db:
            cursor = db.execute("UPDATE reminders SET status='fired' WHERE id=? AND status='pending'", (reminder_id,))
        return cursor.rowcount == 1

    def cancel(self, reminder_id: int) -> bool:
        with self._connect() as db:
            cursor = db.execute("UPDATE reminders SET status='cancelled' WHERE id=? AND status='pending'", (reminder_id,))
        return cursor.rowcount == 1

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Reminder:
        return Reminder(int(row["id"]), row["due_at"], row["message"], row["status"])
