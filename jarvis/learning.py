"""Auditable learning loop: record outcomes and promote reusable skills only after approval.

This module deliberately stores text proposals, not executable code. It does not
rewrite JARVIS, execute learned instructions, or treat observations as trusted policy.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re


def _clean(value: str, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError(f"{field} must contain 1–{limit} characters.")
    return value


def normalize_trigger(value: str) -> str:
    """Normalize a natural-language trigger for exact matching, not fuzzy execution."""
    value = _clean(value, "trigger", 200).casefold()
    return re.sub(r"\s+", " ", value)


@dataclass(frozen=True)
class Episode:
    episode_id: int
    task: str
    outcome: str
    evidence: str
    created_at: str


@dataclass(frozen=True)
class Skill:
    skill_id: int
    trigger: str
    instructions: str
    source_episode_id: int | None
    status: str
    created_at: str


class LearningStore:
    """Local episodic history and human-approved procedural skill proposals."""

    STATUSES = {"pending", "approved", "rejected"}

    def __init__(self, database_path: str | Path = "jarvis-data/learning.sqlite3") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                outcome TEXT NOT NULL,
                evidence TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT NOT NULL,
                normalized_trigger TEXT NOT NULL,
                instructions TEXT NOT NULL,
                source_episode_id INTEGER,
                status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS skills_trigger_status ON skills(normalized_trigger,status)")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path, timeout=5.0)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def record_episode(self, task: str, outcome: str, *, evidence: str = "") -> Episode:
        task = _clean(task, "task", 1000)
        outcome = _clean(outcome, "outcome", 1000)
        if not isinstance(evidence, str) or len(evidence) > 4000:
            raise ValueError("evidence must be text of at most 4000 characters.")
        now = self._now()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO episodes(task,outcome,evidence,created_at) VALUES(?,?,?,?)",
                (task, outcome, evidence.strip(), now),
            )
            row = db.execute("SELECT * FROM episodes WHERE id=?", (cursor.lastrowid,)).fetchone()
        return self._episode(row)

    def recent_episodes(self, limit: int = 20) -> list[Episode]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100.")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM episodes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._episode(row) for row in rows]

    def propose_skill(self, trigger: str, instructions: str, *, source_episode_id: int | None = None) -> Skill:
        trigger = _clean(trigger, "trigger", 200)
        instructions = _clean(instructions, "instructions", 4000)
        normalized = normalize_trigger(trigger)
        now = self._now()
        with self._connect() as db:
            if source_episode_id is not None and db.execute(
                "SELECT 1 FROM episodes WHERE id=?", (source_episode_id,)
            ).fetchone() is None:
                raise ValueError("source_episode_id does not exist.")
            cursor = db.execute(
                """INSERT INTO skills(trigger,normalized_trigger,instructions,source_episode_id,status,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (trigger, normalized, instructions, source_episode_id, "pending", now),
            )
            row = db.execute("SELECT * FROM skills WHERE id=?", (cursor.lastrowid,)).fetchone()
        return self._skill(row)

    def review_skill(self, skill_id: int, *, approve: bool) -> Skill:
        status = "approved" if approve else "rejected"
        with self._connect() as db:
            row = db.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
            if row is None:
                raise ValueError("Skill proposal not found.")
            if row["status"] != "pending":
                raise ValueError("Only pending skill proposals can be reviewed.")
            db.execute("UPDATE skills SET status=?, reviewed_at=? WHERE id=?", (status, self._now(), skill_id))
            updated = db.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
        return self._skill(updated)

    def list_skills(self, *, status: str | None = None, limit: int = 100) -> list[Skill]:
        if status is not None and status not in self.STATUSES:
            raise ValueError("Unknown skill status.")
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200.")
        with self._connect() as db:
            if status is None:
                rows = db.execute("SELECT * FROM skills ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM skills WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit)).fetchall()
        return [self._skill(row) for row in rows]

    def find_approved_skill(self, trigger: str) -> Skill | None:
        normalized = normalize_trigger(trigger)
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM skills WHERE normalized_trigger=? AND status='approved' ORDER BY id DESC LIMIT 1",
                (normalized,),
            ).fetchone()
        return self._skill(row) if row else None

    @staticmethod
    def _episode(row: sqlite3.Row) -> Episode:
        return Episode(int(row["id"]), row["task"], row["outcome"], row["evidence"], row["created_at"])

    @staticmethod
    def _skill(row: sqlite3.Row) -> Skill:
        return Skill(int(row["id"]), row["trigger"], row["instructions"],
                     int(row["source_episode_id"]) if row["source_episode_id"] is not None else None,
                     row["status"], row["created_at"])
