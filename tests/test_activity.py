import json
import tempfile
import unittest
from pathlib import Path

from jarvis.activity import ActivityJournal, redact


class ActivityJournalTests(unittest.TestCase):
    def test_redacts_common_secrets(self):
        value = "api_key=AIza123456789012345678901234 password:supersecret"
        result = redact(value)
        self.assertNotIn("AIza123456789012345678901234", result)
        self.assertNotIn("supersecret", result)

    def test_persisted_journal_is_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "activity.jsonl"
            journal = ActivityJournal(path, max_entries=2)
            journal.record("start", "ok")
            journal.record("provider", "error", detail="api_key=AIza123456789012345678901234")
            journal.record("done", "ok")
            rows = journal.recent()
            self.assertEqual([row["event"] for row in rows], ["provider", "done"])
            self.assertNotIn("AIza123456789012345678901234", path.read_text(encoding="utf-8"))
            for line in path.read_text(encoding="utf-8").splitlines():
                json.loads(line)

    def test_memory_mode_does_not_create_files(self):
        journal = ActivityJournal(":memory:", max_entries=2)
        journal.record("one", "ok")
        self.assertEqual(journal.recent()[0]["event"], "one")

    def test_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            ActivityJournal(":memory:", max_entries=0)


if __name__ == "__main__":
    unittest.main()
