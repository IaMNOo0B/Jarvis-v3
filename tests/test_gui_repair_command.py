import tempfile
import unittest
from pathlib import Path

from jarvis.gui import JarvisWindow
from jarvis.self_healing import RepairLedger


class RepairCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = RepairLedger(Path(self.temp.name) / "repairs.sqlite3")
        self.window = object.__new__(JarvisWindow)
        self.window.repairs = self.ledger
        self.messages = []
        self.window._append = lambda speaker, message: self.messages.append((speaker, message))

    def tearDown(self):
        self.temp.cleanup()

    def test_repairs_command_lists_recent_proposals_without_applying_them(self):
        proposal = self.ledger.propose(
            "Unexpected desktop-action worker error; task content omitted.",
            "Reproduce with a fake adapter, add a regression test, then verify on Windows.",
            "gui-desktop-action-failure",
        )
        handled = self.window._handle_repair_command("/Repairs")
        self.assertTrue(handled)
        self.assertEqual(len(self.messages), 1)
        speaker, message = self.messages[0]
        self.assertEqual(speaker, "JARVIS")
        self.assertIn(f"#{proposal.repair_id} [PROPOSED]", message)
        self.assertIn("fake adapter", message)
        self.assertIn("nothing is auto-applied", message.casefold())
        self.assertEqual(self.ledger.list_proposals()[0].status, "proposed")

    def test_repairs_command_reports_empty_history(self):
        self.assertTrue(self.window._handle_repair_command("/repairs"))
        self.assertIn("No repair proposals are saved", self.messages[0][1])

    def test_unrelated_message_is_not_consumed_by_repair_handler(self):
        self.assertFalse(self.window._handle_repair_command("repair this"))
        self.assertEqual(self.messages, [])

    def test_unreadable_repair_history_fails_safely(self):
        class BrokenLedger:
            def list_proposals(self, limit=10):
                raise OSError("private storage path")

        self.window.repairs = BrokenLedger()
        self.assertTrue(self.window._handle_repair_command("/repairs"))
        self.assertIn("could not be read", self.messages[0][1])
        self.assertNotIn("private storage path", self.messages[0][1])


if __name__ == "__main__":
    unittest.main()
