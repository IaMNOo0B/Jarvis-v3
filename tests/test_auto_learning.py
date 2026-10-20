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

    def test_verified_ui_postcondition_is_reflected_narrowly(self):
        result = self.learning.reflect(
            "Type text in Notepad", outcome="action_verified",
            evidence="Notepad read-back exactly matched requested text.",
        )
        self.assertEqual(result.episode.outcome, "action_verified")
        self.assertEqual(result.confidence, "high")
        self.assertIn("specific UI postcondition", result.note)
        self.assertIn("broader user-goal completion is not implied", result.note)

    def test_partial_and_unknown_actions_never_claim_success(self):
        partial = self.learning.reflect("Open apps", outcome="action_partial")
        unknown = self.learning.reflect("Type in Notepad", outcome="action_unknown")
        self.assertIn("partially ran", partial.note)
        self.assertIn("may have occurred", unknown.note)
        self.assertNotEqual(partial.outcome, "action_verified")
        self.assertNotEqual(unknown.outcome, "action_verified")

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
