import tempfile
import unittest
from pathlib import Path

from jarvis.auto_learning import AutomaticLearning
from jarvis.learning import LearningStore


class AutomaticLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LearningStore(Path(self.temp.name) / "learning.sqlite3")
        self.learning = AutomaticLearning(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_reflection_records_without_manual_command(self):
        result = self.learning.reflect("Explain binary search", outcome="response_generated")
        self.assertEqual(result.episode.task, "Explain binary search")
        self.assertEqual(result.episode.outcome, "response_generated")
        self.assertIn("unverified", result.episode.evidence)
        self.assertEqual(result.confidence, "low")

    def test_action_acceptance_does_not_claim_app_visible(self):
        result = self.learning.reflect("Open Notepad", outcome="action_accepted")
        self.assertIn("visibility is unverified", result.note)

    def test_failure_is_recorded(self):
        result = self.learning.reflect("Search the web", outcome="provider_failed")
        self.assertEqual(result.episode.outcome, "provider_failed")
        self.assertEqual(result.confidence, "high")

    def test_obvious_secrets_are_redacted_from_automatic_history(self):
        result = self.learning.reflect("Use api_key=AIza1234567890123456789012345", outcome="response_generated")
        self.assertNotIn("AIza1234567890123456789012345", result.episode.task)
        self.assertIn("[REDACTED", result.episode.task)

    def test_rejects_empty_task_and_unknown_outcome(self):
        with self.assertRaises(ValueError):
            self.learning.reflect(" ", outcome="response_generated")
        with self.assertRaises(ValueError):
            self.learning.reflect("task", outcome="success")


if __name__ == "__main__":
    unittest.main()
