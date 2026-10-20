import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jarvis.reminders import ReminderStore, parse_natural_reminder


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


    def test_parse_relative_natural_reminders_in_local_timezone(self):
        local = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 10, 20, 19, 0, tzinfo=local)
        due_at, message = parse_natural_reminder("Remind me in 20 minutes to study", now)
        self.assertEqual(message, "study")
        self.assertEqual(datetime.fromisoformat(due_at), datetime(2026, 10, 20, 19, 20, tzinfo=local))

    def test_parse_reversed_relative_natural_reminder(self):
        local = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 10, 20, 19, 0, tzinfo=local)
        due_at, message = parse_natural_reminder("Please remind me to call home in 2 hours", now)
        self.assertEqual(message, "call home")
        self.assertEqual(datetime.fromisoformat(due_at), datetime(2026, 10, 20, 21, 0, tzinfo=local))

    def test_parse_tomorrow_clock_time_without_guessing_ambiguous_hours(self):
        local = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 10, 20, 19, 0, tzinfo=local)
        due_at, message = parse_natural_reminder("Remind me tomorrow at 8:30 PM to study", now)
        self.assertEqual(message, "study")
        self.assertEqual(datetime.fromisoformat(due_at), datetime(2026, 10, 21, 20, 30, tzinfo=local))
        self.assertIsNone(parse_natural_reminder("Remind me tomorrow at 8 to study", now))

    def test_unsupported_or_ambiguous_reminder_is_not_guessed(self):
        local = timezone(timedelta(hours=5, minutes=30))
        now = datetime(2026, 10, 20, 19, 0, tzinfo=local)
        self.assertIsNone(parse_natural_reminder("Remind me next Friday to study", now))
        self.assertIsNone(parse_natural_reminder("Remind me at 8 to study", now))
        with self.assertRaises(ValueError):
            parse_natural_reminder("Remind me in 5 minutes to study", datetime(2026, 10, 20, 19, 0))

    def test_mark_fired_is_idempotent_and_removes_pending(self):
        item = self.store.create("2030-01-01T10:00:00+00:00", "Call")
        self.assertTrue(self.store.mark_fired(item.reminder_id))
        self.assertFalse(self.store.mark_fired(item.reminder_id))
        self.assertEqual(self.store.list(), [])
        self.assertEqual(self.store.list(include_finished=True)[0].status, "fired")


if __name__ == "__main__":
    unittest.main()
