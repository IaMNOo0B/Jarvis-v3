import tempfile
import unittest
from pathlib import Path

from jarvis.self_healing import RepairLedger, should_propose_desktop_repair


class RepairLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = RepairLedger(Path(self.temp.name) / "repairs.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_only_unexpected_desktop_worker_errors_trigger_repair_proposals(self):
        for detail in (
            "Unexpected Notepad automation error. Inspect the desktop before retrying.",
            "Unexpected browser navigation error. No further action was taken.",
            "Unexpected launch error. No further action was taken.",
        ):
            with self.subTest(detail=detail):
                self.assertTrue(should_propose_desktop_repair("action_failed", detail))

    def test_normal_preconditions_and_ambiguous_outcomes_do_not_trigger_repair_proposals(self):
        for outcome, detail in (
            ("action_failed", "Notepad was not found on this PC."),
            ("action_failed", "No blank Notepad document was found; existing text was left untouched."),
            ("action_failed", "URL rejected; only valid HTTP(S) URLs are allowed."),
            ("action_partial", "Partial execution: one app accepted; next launch failed."),
            ("action_unknown", "Text may have been partially entered; inspect Notepad before retrying."),
            ("action_accepted", "Windows accepted the launch request."),
            ("response_generated", "Unexpected Notepad automation error."),
            ("action_failed", ""),
        ):
            with self.subTest(outcome=outcome, detail=detail):
                self.assertFalse(should_propose_desktop_repair(outcome, detail))

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

    def test_candidate_policy_review_is_audited_without_approving_or_applying(self):
        proposal = self.ledger.propose("Routing regression", "Adjust planner matching.", "issue-9")
        receipt = self.ledger.review_candidate_policy(
            proposal.repair_id,
            changed_paths=["jarvis/learning.py", "tests/test_learning.py"],
            diff_text="diff --git a/jarvis/learning.py b/jarvis/learning.py",
        )
        self.assertEqual(receipt.decision, "eligible_for_tests")
        self.assertEqual(len(receipt.diff_sha256), 64)
        self.assertFalse(hasattr(receipt, "diff_text"))
        self.assertEqual(self.ledger.list_proposals()[0].status, "proposed")
        stored = self.ledger.recent_candidate_policy_reviews(proposal.repair_id)
        self.assertEqual(stored[0], receipt)

    def test_protected_candidate_is_flagged_and_traversal_is_rejected(self):
        proposal = self.ledger.propose("Safety regression", "Review the patch.", "issue-10")
        protected = self.ledger.review_candidate_policy(
            proposal.repair_id, changed_paths=["jarvis/safety.py"], diff_text="diff"
        )
        self.assertEqual(protected.decision, "manual_review_required")
        traversal = self.ledger.review_candidate_policy(
            proposal.repair_id, changed_paths=["../outside.py"], diff_text="diff"
        )
        self.assertEqual(traversal.decision, "rejected")
        self.assertIn("ValueError", traversal.reasons[0])
        self.assertEqual(self.ledger.list_proposals()[0].status, "proposed")

    def test_oversized_candidate_is_rejected_without_hashing_full_diff(self):
        proposal = self.ledger.propose("Large patch", "Review patch size.", "issue-11")
        receipt = self.ledger.review_candidate_policy(
            proposal.repair_id, changed_paths=["jarvis/a.py"], diff_text="x" * 64001
        )
        self.assertEqual(receipt.decision, "rejected")
        self.assertEqual(receipt.diff_sha256, "")
        self.assertEqual(receipt.diff_chars, 64001)

    def test_candidate_policy_requires_existing_proposal(self):
        with self.assertRaises(ValueError):
            self.ledger.review_candidate_policy(999, changed_paths=["jarvis/a.py"], diff_text="diff")

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
