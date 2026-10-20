import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jarvis.reminders import ReminderStore


class ReminderStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ReminderStore(Path(self.temp.name) / "reminders.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_create_persists_across_store_instances(self):
        item = self.store.create("2030-01-01T10:00:00+05:30", "Study")
        other = ReminderStore(Path(self.temp.name) / "reminders.sqlite3")
        self.assertEqual(other.list()[0].reminder_id, item.reminder_id)
        self.assertEqual(item.message, "Study")

    def test_requires_timezone_and_nonempty_message(self):
        with self.assertRaises(ValueError):
            self.store.create("2030-01-01T10:00:00", "Study")
        with self.assertRaises(ValueError):
            self.store.create("2030-01-01T10:00:00+00:00", " ")

    def test_due_and_cancel_lifecycle(self):
        item = self.store.create("2020-01-01T10:00:00+00:00", "Past task")
        self.assertEqual([r.reminder_id for r in self.store.due(datetime(2021, 1, 1, tzinfo=timezone.utc))], [item.reminder_id])
        self.assertTrue(self.store.cancel(item.reminder_id))
        self.assertFalse(self.store.cancel(item.reminder_id))
        self.assertEqual(self.store.due(datetime(2030, 1, 1, tzinfo=timezone.utc)), [])

    def test_mark_fired_is_idempotent_and_removes_pending(self):
        item = self.store.create("2030-01-01T10:00:00+00:00", "Call")
        self.assertTrue(self.store.mark_fired(item.reminder_id))
        self.assertFalse(self.store.mark_fired(item.reminder_id))
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.list(include_finished=True)[0].status, "fired")


if __name__ == "__main__":
    unittest.main()
