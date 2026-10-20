import tempfile
import unittest
from pathlib import Path

from jarvis.self_healing import RepairLedger


class RepairLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = RepairLedger(Path(self.temp.name) / "repairs.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_proposal_is_only_a_proposal_and_persists(self):
        proposal = self.ledger.propose("Provider timeout", "Add bounded retry with cancellation.", "issue-42")
        self.assertEqual(proposal.status, "proposed")
        self.assertEqual(self.ledger.list_proposals()[0], proposal)

    def test_rejects_path_traversal_and_unbounded_fields(self):
        with self.assertRaises(ValueError):
            self.ledger.propose("failure", "change", "../main")
        with self.assertRaises(ValueError):
            self.ledger.propose("failure", "x" * 8001, "issue-1")

    def test_failed_verification_cannot_be_approved(self):
        proposal = self.ledger.propose("Regression", "Fix edge case.", "commit-123")
        receipt = self.ledger.record_verification(
            proposal.repair_id, result="failed", test_summary="2 tests failed",
            baseline_ref="main", candidate_ref="repair-1",
        )
        self.assertEqual(receipt.result, "failed")
        with self.assertRaises(PermissionError):
            self.ledger.review(proposal.repair_id, approve_for_manual_review=True)

    def test_passed_verification_still_needs_review_and_never_auto_applies(self):
        proposal = self.ledger.propose("Parser error", "Handle blank input.", "issue-7")
        with self.assertRaises(PermissionError):
            self.ledger.review(proposal.repair_id, approve_for_manual_review=True)
        self.ledger.record_verification(
            proposal.repair_id, result="passed", test_summary="unit suite passed",
            baseline_ref="main", candidate_ref="repair-7",
        )
        reviewed = self.ledger.review(proposal.repair_id, approve_for_manual_review=True)
        self.assertEqual(reviewed.status, "approved_for_manual_review")
        with self.assertRaises(ValueError):
            self.ledger.review(proposal.repair_id, approve_for_manual_review=False)

    def test_unknown_proposal_and_bad_result_are_rejected(self):
        with self.assertRaises(ValueError):
            self.ledger.record_verification(999, result="passed", test_summary="ok",
                                            baseline_ref="main", candidate_ref="repair")
        proposal = self.ledger.propose("failure", "fix", "issue-8")
        with self.assertRaises(ValueError):
            self.ledger.record_verification(proposal.repair_id, result="magic",
                                            test_summary="ok", baseline_ref="main",
                                            candidate_ref="repair")


if __name__ == "__main__":
    unittest.main()
