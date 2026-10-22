"""Safe self-healing primitives: propose, stage, verify, and review repairs.

This module never edits the live application, runs arbitrary generated code, or
auto-approves a patch. It stores bounded text proposals and test receipts only.
A separate, explicitly authorized executor can be designed later.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import ContextManager

from jarvis.sqlite_utils import sqlite_connection
from jarvis.repair_policy import MAX_DIFF_CHARS, CandidateReview, review_candidate
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

@dataclass(frozen=True)
class CandidatePolicyReceipt:
    review_id: int
    repair_id: int
    decision: str
    reasons: tuple[str, ...]
    changed_paths: tuple[str, ...]
    diff_sha256: str
    diff_chars: int
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
            db.execute("""CREATE TABLE IF NOT EXISTS candidate_policy_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repair_id INTEGER NOT NULL REFERENCES repair_proposals(id),
                decision TEXT NOT NULL CHECK(decision IN ('rejected','manual_review_required','eligible_for_tests')),
                reasons_json TEXT NOT NULL,
                changed_paths_json TEXT NOT NULL,
                diff_sha256 TEXT NOT NULL,
                diff_chars INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def _connect(self) -> ContextManager[sqlite3.Connection]:
        return sqlite_connection(self.database_path, timeout=5.0, foreign_keys=True)

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

    def review_candidate_policy(
        self, repair_id: int, *, changed_paths: list[str] | tuple[str, ...],
        diff_text: str,
    ) -> CandidatePolicyReceipt:
        """Persist a bounded policy review without changing proposal status or applying code."""
        with self._connect() as db:
            proposal = db.execute("SELECT id FROM repair_proposals WHERE id=?", (repair_id,)).fetchone()
        if proposal is None:
            raise ValueError("Unknown repair proposal.")
        if not isinstance(diff_text, str):
            raise ValueError("Diff must be text.")
        # Persist only a hash and metadata, never candidate source or secret-bearing diffs.
        diff_hash = (
            hashlib.sha256(diff_text.encode("utf-8", errors="replace")).hexdigest()
            if len(diff_text) <= MAX_DIFF_CHARS else ""
        )
        try:
            review: CandidateReview = review_candidate(changed_paths, diff_text)
            decision, reasons, paths, diff_chars = (
                review.decision, review.reasons, review.changed_files, review.diff_chars
            )
        except (ValueError, TypeError) as exc:
            decision = "rejected"
            reasons = (f"candidate policy input rejected: {type(exc).__name__}",)
            paths = ()
            diff_chars = min(len(diff_text), 2**31 - 1)
        created = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO candidate_policy_reviews(
                    repair_id, decision, reasons_json, changed_paths_json,
                    diff_sha256, diff_chars, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (repair_id, decision, json.dumps(reasons), json.dumps(paths),
                 diff_hash, diff_chars, created),
            )
            review_id = cursor.lastrowid
        return CandidatePolicyReceipt(
            int(review_id), repair_id, decision, tuple(reasons), tuple(paths),
            diff_hash, diff_chars, created,
        )

    def recent_candidate_policy_reviews(self, repair_id: int, limit: int = 20) -> list[CandidatePolicyReceipt]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM candidate_policy_reviews WHERE repair_id=? ORDER BY id DESC LIMIT ?",
                (repair_id, limit),
            ).fetchall()
        return [
            CandidatePolicyReceipt(
                row["id"], row["repair_id"], row["decision"],
                tuple(json.loads(row["reasons_json"])),
                tuple(json.loads(row["changed_paths_json"])),
                row["diff_sha256"], row["diff_chars"], row["created_at"],
            )
            for row in rows
        ]

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
