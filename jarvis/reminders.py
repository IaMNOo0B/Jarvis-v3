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


def parse_natural_reminder(request: str, now: datetime | None = None) -> tuple[str, str] | None:
    """Parse a small, explicit set of natural reminder phrasings without guessing.

    Returns (timezone-aware ISO timestamp, message). Ambiguous clock-only times,
    relative dates, and unsupported wording return None rather than inventing a
    schedule. The GUI can then ask for a clearer time without saving anything.
    """
    import re
    from datetime import timedelta

    current = now or datetime.now().astimezone()
    if current.tzinfo is None:
        raise ValueError("Current time must include a timezone.")
    text = request.strip()
    if len(text) > 2200:
        return None

    prefix = r"(?:jarvis[, ]+)?(?:please )?remind me "
    relative_patterns = (
        re.compile(prefix + r"in (\d{1,5}) (minutes?|mins?|hours?|hrs?|days?) to (.+)", re.IGNORECASE),
        re.compile(prefix + r"to (.+) in (\d{1,5}) (minutes?|mins?|hours?|hrs?|days?)", re.IGNORECASE),
    )
    units = {"minute": 1, "min": 1, "hour": 60, "hr": 60, "day": 1440}
    for index, pattern in enumerate(relative_patterns):
        match = pattern.fullmatch(text)
        if not match:
            continue
        if index == 0:
            amount, unit_text, message = int(match.group(1)), match.group(2).casefold(), match.group(3).strip()
        else:
            message, amount, unit_text = match.group(1).strip(), int(match.group(2)), match.group(3).casefold()
        unit = unit_text.rstrip("s")
        if unit.endswith("s"):
            unit = unit[:-1]
        if unit == "mins":
            unit = "min"
        if unit == "hrs":
            unit = "hr"
        multiplier = units.get(unit)
        minutes = amount * multiplier if multiplier else 0
        if amount < 1 or minutes > 30 * 24 * 60 or not message:
            return None
        due = current + timedelta(minutes=minutes)
        return due.isoformat(timespec="seconds"), message

    absolute = re.compile(
        prefix + r"(?:(today|tomorrow) )?at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?) to (.+)",
        re.IGNORECASE,
    ).fullmatch(text)
    if not absolute:
        return None
    day_name, clock, message = absolute.group(1), absolute.group(2).strip(), absolute.group(3).strip()
    if not message:
        return None
    time_match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", clock, re.IGNORECASE)
    if not time_match:
        return None
    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or "0")
    meridiem = (time_match.group(3) or "").casefold()
    if minute > 59:
        return None
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    elif time_match.group(2) is None or not 0 <= hour <= 23:
        # A bare "at 8" is ambiguous; require 8 AM/PM or 08:00/20:00.
        return None

    due = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if day_name and day_name.casefold() == "tomorrow":
        due += timedelta(days=1)
    elif day_name and due <= current:
        return None
    elif not day_name and due <= current:
        due += timedelta(days=1)
    return due.isoformat(timespec="seconds"), message
