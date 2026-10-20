import tempfile
import unittest
from pathlib import Path

from jarvis.learning import LearningStore, normalize_trigger


class LearningStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "learning.sqlite3"
        self.store = LearningStore(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_episode_persists_and_keeps_evidence(self):
        episode = self.store.record_episode("open notepad", "accepted", evidence="Windows accepted launch")
        again = LearningStore(self.path).recent_episodes()[0]
        self.assertEqual(again, episode)
        self.assertEqual(again.evidence, "Windows accepted launch")

    def test_skill_is_not_retrievable_until_approved(self):
        skill = self.store.propose_skill("  Open   Notepad ", "Launch only after explicit approval.")
        self.assertEqual(skill.status, "pending")
        self.assertIsNone(self.store.find_approved_skill("open notepad"))
        approved = self.store.review_skill(skill.skill_id, approve=True)
        self.assertEqual(approved.status, "approved")
        self.assertEqual(self.store.find_approved_skill("OPEN notepad"), approved)

    def test_rejected_skill_never_retrieves(self):
        skill = self.store.propose_skill("open calculator", "Do a safe action.")
        self.store.review_skill(skill.skill_id, approve=False)
        self.assertIsNone(self.store.find_approved_skill("open calculator"))

    def test_review_is_one_time_and_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            self.store.propose_skill("trigger", "instructions", source_episode_id=999)
        skill = self.store.propose_skill("trigger", "instructions")
        self.store.review_skill(skill.skill_id, approve=True)
        with self.assertRaises(ValueError):
            self.store.review_skill(skill.skill_id, approve=False)

    def test_limits_and_normalization(self):
        self.assertEqual(normalize_trigger("  OPEN   NOTEPAD "), "open notepad")
        with self.assertRaises(ValueError):
            self.store.record_episode("", "failed")
        with self.assertRaises(ValueError):
            self.store.propose_skill("trigger", " ")


if __name__ == "__main__":
    unittest.main()
