import tempfile
import unittest
from pathlib import Path

from jarvis.task_receipts import TaskReceiptStore


class TaskReceiptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TaskReceiptStore(Path(self.temp.name) / "receipts.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_records_observed_outcome_and_evidence(self):
        item = self.store.record("Open Notepad", "action_accepted", evidence="OS accepted request")
        self.assertEqual(item["outcome"], "action_accepted")
        self.assertEqual(item["evidence"], "OS accepted request")
        self.assertIn("T", item["created_at"])
        self.assertEqual(self.store.recent()[0], item)

    def test_rejects_unknown_outcome_and_invalid_limits(self):
        with self.assertRaises(ValueError):
            self.store.record("task", "success")
        with self.assertRaises(ValueError):
            self.store.recent(0)

    def test_redacts_obvious_secrets_from_task_and_evidence(self):
        item = self.store.record(
            "Use api_key=AIza1234567890123456789012345",
            "response_generated",
            evidence="token=ghp_abcdefghijklmnopqrstuvwxyz123456",
        )
        self.assertNotIn("AIza1234567890123456789012345", item["task"])
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", item["evidence"])

    def test_clear_removes_only_receipts(self):
        self.store.record("task one", "response_generated")
        self.store.record("task two", "provider_failed")
        self.assertEqual(self.store.clear(), 2)
        self.assertEqual(self.store.recent(), [])

    def test_bounds_task_and_evidence(self):
        with self.assertRaises(ValueError):
            self.store.record("x" * 4001, "response_generated")
        with self.assertRaises(ValueError):
            self.store.record("task", "response_generated", evidence="x" * 4001)


if __name__ == "__main__":
    unittest.main()
