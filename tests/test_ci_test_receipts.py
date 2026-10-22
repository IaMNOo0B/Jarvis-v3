import tempfile
import unittest
from pathlib import Path

from jarvis.ci_test_receipts import verify_ci_test_receipt
from jarvis.self_healing import RepairLedger


class CiTestReceiptVerificationTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.receipt = {
            "schema_version": "1",
            "commit_sha": self.sha,
            "workflow_run_id": "123456",
            "run_attempt": "1",
            "runner_os": "Windows",
            "python_version": "3.12.10",
            "test_command": "python -m unittest discover -s tests -v",
            "unit_test_step_result": "success",
            "job_result": "success",
        }
        self.expected = {
            "expected_commit_sha": self.sha,
            "expected_run_id": "123456",
            "expected_run_attempt": "1",
            "expected_runner_os": "Windows",
        }

    def test_accepts_successful_receipt_matching_trusted_metadata(self):
        verified = verify_ci_test_receipt(self.receipt, **self.expected)
        self.assertEqual(verified.commit_sha, self.sha)
        self.assertEqual(verified.result, "passed")
        self.assertEqual(verified.runner_os, "Windows")

    def test_rejects_commit_run_attempt_os_and_failed_tests(self):
        cases = [
            ({**self.receipt, "commit_sha": "b" * 40}, self.expected),
            (self.receipt, {**self.expected, "expected_run_id": "999"}),
            (self.receipt, {**self.expected, "expected_run_attempt": "2"}),
            (self.receipt, {**self.expected, "expected_runner_os": "Linux"}),
            ({**self.receipt, "unit_test_step_result": "failure"}, self.expected),
            ({**self.receipt, "job_result": "failure"}, self.expected),
        ]
        for receipt, expected in cases:
            with self.subTest(receipt=receipt, expected=expected):
                with self.assertRaises(ValueError):
                    verify_ci_test_receipt(receipt, **expected)

    def test_rejects_extra_fields_and_arbitrary_test_command(self):
        with self.assertRaises(ValueError):
            verify_ci_test_receipt({**self.receipt, "secret": "no"}, **self.expected)
        with self.assertRaises(ValueError):
            verify_ci_test_receipt(
                {**self.receipt, "test_command": "python attacker.py"}, **self.expected
            )

    def test_ledger_requires_windows_and_linux_when_ci_evidence_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = RepairLedger(Path(directory) / "repairs.sqlite3")
            proposal = ledger.propose("Regression", "Fix the regression safely.", "issue-22")
            windows = dict(self.receipt)
            ledger.record_ci_test_receipt(
                proposal.repair_id, windows,
                expected_commit_sha=self.sha, expected_run_id="123456",
                expected_run_attempt="1", expected_runner_os="Windows",
            )
            ledger.record_verification(
                proposal.repair_id, result="passed", test_summary="unit tests passed",
                baseline_ref="main", candidate_ref=self.sha,
            )
            with self.assertRaises(PermissionError):
                ledger.review(proposal.repair_id, approve_for_manual_review=True)

            linux = {**self.receipt, "runner_os": "Linux", "workflow_run_id": "123457"}
            ledger.record_ci_test_receipt(
                proposal.repair_id, linux,
                expected_commit_sha=self.sha, expected_run_id="123457",
                expected_run_attempt="1", expected_runner_os="Linux",
            )
            reviewed = ledger.review(proposal.repair_id, approve_for_manual_review=True)
            self.assertEqual(reviewed.status, "approved_for_manual_review")
            stored = ledger.recent_ci_test_receipts(proposal.repair_id)
            self.assertEqual({item["runner_os"] for item in stored}, {"Windows", "Linux"})

    def test_ci_receipt_cannot_be_added_to_unknown_or_reviewed_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = RepairLedger(Path(directory) / "repairs.sqlite3")
            with self.assertRaises(ValueError):
                ledger.record_ci_test_receipt(
                    999, self.receipt,
                    expected_commit_sha=self.sha, expected_run_id="123456",
                    expected_run_attempt="1", expected_runner_os="Windows",
                )
            proposal = ledger.propose("Regression", "Fix the regression safely.", "issue-23")
            ledger.record_verification(
                proposal.repair_id, result="passed", test_summary="unit tests passed",
                baseline_ref="main", candidate_ref=self.sha,
            )
            ledger.review(proposal.repair_id, approve_for_manual_review=True)
            with self.assertRaises(ValueError):
                ledger.record_ci_test_receipt(
                    proposal.repair_id, self.receipt,
                    expected_commit_sha=self.sha, expected_run_id="123456",
                    expected_run_attempt="1", expected_runner_os="Windows",
                )


if __name__ == "__main__":
    unittest.main()
