"""Safe self-healing primitives: propose, stage, verify, and review repairs.

This module never edits the live application, runs arbitrary generated code, or
auto-approves a patch. It stores bounded text proposals and test receipts only.
A separate, explicitly authorized executor can be designed later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import re


def _bounded_text(value: str, name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text.")
    value = value.strip()
    if not value or len(value) > maximum:
        raise ValueError(f"{name} must contain 1–{maximum} characters.")
    return value


def _safe_ref(value: str) -> str:
    value = _bounded_text(value, "reference", 200)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", value) or ".." in value.split("/"):
        raise ValueError("Reference must be a safe branch, commit, or issue identifier.")
    return value


def should_propose_desktop_repair(outcome: str, detail: str) -> bool:
    """Return true only for unexpected worker exceptions, not normal preconditions."""
    if outcome != "action_failed" or not isinstance(detail, str):
        return False
    normalized = detail.casefold()
    unexpected_markers = (
        "unexpected notepad automation error",
        "unexpected browser navigation error",
        "unexpected launch error",
    )
    return any(marker in normalized for marker in unexpected_markers)


@dataclass(frozen=True)
class RepairProposal:
    repair_id: int
    failure_summary: str
    proposed_change: str
    source_ref: str
    status: str
    created_at: str


@dataclass(frozen=True)
class VerificationReceipt:
    repair_id: int
    result: str
    test_summary: str
    baseline_ref: str
    candidate_ref: str
    created_at: str


class RepairLedger:
    """Persistent repair proposals and test receipts; no live-code mutation."""

    PROPOSAL_STATUSES = {"proposed", "rejected", "verified_pending_approval", "approved_for_manual_review"}

    def __init__(self, database_path: str | Path = "jarvis-data/repairs.sqlite3") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS repair_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_summary TEXT NOT NULL,
                proposed_change TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN
                    ('proposed','rejected','verified_pending_approval','approved_for_manual_review')),
                created_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS verification_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repair_id INTEGER NOT NULL REFERENCES repair_proposals(id),
                result TEXT NOT NULL CHECK(result IN ('passed','failed','not_run')),
                test_summary TEXT NOT NULL,
                baseline_ref TEXT NOT NULL,
                candidate_ref TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def _proposal(row: sqlite3.Row) -> RepairProposal:
        return RepairProposal(row["id"], row["failure_summary"], row["proposed_change"],
                              row["source_ref"], row["status"], row["created_at"])

    def propose(self, failure_summary: str, proposed_change: str, source_ref: str) -> RepairProposal:
        failure_summary = _bounded_text(failure_summary, "failure summary", 2000)
        proposed_change = _bounded_text(proposed_change, "proposed change", 8000)
        source_ref = _safe_ref(source_ref)
        created = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO repair_proposals(failure_summary, proposed_change, source_ref, status, created_at) "
                "VALUES (?, ?, ?, 'proposed', ?)",
                (failure_summary, proposed_change, source_ref, created),
            )
            row = db.execute("SELECT * FROM repair_proposals WHERE id=?", (cur.lastrowid,)).fetchone()
        return self._proposal(row)

    def record_verification(
        self, repair_id: int, *, result: str, test_summary: str,
        baseline_ref: str, candidate_ref: str,
    ) -> VerificationReceipt:
        if result not in {"passed", "failed", "not_run"}:
            raise ValueError("Verification result must be passed, failed, or not_run.")
        test_summary = _bounded_text(test_summary, "test summary", 3000)
        baseline_ref, candidate_ref = _safe_ref(baseline_ref), _safe_ref(candidate_ref)
        created = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            proposal = db.execute("SELECT * FROM repair_proposals WHERE id=?", (repair_id,)).fetchone()
            if proposal is None:
                raise ValueError("Unknown repair proposal.")
            if proposal["status"] != "proposed":
                raise ValueError("Only an unreviewed proposal can receive its first verification receipt.")
            db.execute(
                "INSERT INTO verification_receipts(repair_id, result, test_summary, baseline_ref, candidate_ref, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (repair_id, result, test_summary, baseline_ref, candidate_ref, created),
            )
            status = "verified_pending_approval" if result == "passed" else "proposed"
            db.execute("UPDATE repair_proposals SET status=? WHERE id=?", (status, repair_id))
        return VerificationReceipt(repair_id, result, test_summary, baseline_ref, candidate_ref, created)

    def review(self, repair_id: int, *, approve_for_manual_review: bool) -> RepairProposal:
        with self._connect() as db:
            row = db.execute("SELECT * FROM repair_proposals WHERE id=?", (repair_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown repair proposal.")
            if row["status"] not in {"proposed", "verified_pending_approval"}:
                raise ValueError("Repair proposal has already been reviewed.")
            if approve_for_manual_review:
                receipt = db.execute(
                    "SELECT result FROM verification_receipts WHERE repair_id=? ORDER BY id DESC LIMIT 1",
                    (repair_id,),
                ).fetchone()
                if receipt is None or receipt["result"] != "passed":
                    raise PermissionError("A passing test receipt is required before approval for manual review.")
                status = "approved_for_manual_review"
            else:
                status = "rejected"
            db.execute("UPDATE repair_proposals SET status=? WHERE id=?", (status, repair_id))
            updated = db.execute("SELECT * FROM repair_proposals WHERE id=?", (repair_id,)).fetchone()
        return self._proposal(updated)

    def list_proposals(self, limit: int = 20) -> list[RepairProposal]:
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100.")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM repair_proposals ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._proposal(row) for row in rows]
