import unittest
from unittest.mock import patch

from jarvis.gui import JarvisWindow
from jarvis.source_inspection import CallReference, InspectionReport, SourceFile, SourceSymbol


class SourceInspectionCommandTests(unittest.TestCase):
    def setUp(self):
        self.window = JarvisWindow.__new__(JarvisWindow)
        self.messages = []
        self.activities = []
        self.window._append = lambda speaker, message: self.messages.append((speaker, message))
        self.window._record_activity = lambda *args: self.activities.append(args)
        self.report = InspectionReport(
            root="project",
            files=(SourceFile("jarvis/example.py", "a" * 64, 10, True),),
            symbols=(SourceSymbol("function", "helper", "helper", "jarvis/example.py", 4, 5),),
            imports=(),
            calls=(CallReference("run", "helper", "jarvis/example.py", 8),),
            warnings=(),
        )

    def test_inspection_command_reports_static_inventory(self):
        with patch("jarvis.gui.inspect_source_tree", return_value=self.report):
            self.assertTrue(self.window._handle_source_inspection_command("/inspect-source"))
        self.assertIn("1 total, 1 parsed", self.messages[0][1])
        self.assertIn("not executed", self.messages[0][1])
        self.assertEqual(self.activities[0][0:2], ("source_inspection", "completed"))

    def test_symbol_command_reports_definition_and_call_site(self):
        with patch("jarvis.gui.inspect_source_tree", return_value=self.report), patch(
            "jarvis.gui.trace_symbol",
            return_value={"definitions": self.report.symbols, "callers": self.report.calls},
        ):
            self.assertTrue(self.window._handle_source_inspection_command("/inspect-source helper"))
        self.assertIn("jarvis/example.py:4", self.messages[0][1])
        self.assertIn("jarvis/example.py:8", self.messages[0][1])

    def test_command_does_not_accept_arbitrary_path(self):
        self.assertTrue(self.window._handle_source_inspection_command("/inspect-source C:\\secret"))
        self.assertIn("arbitrary paths are not accepted", self.messages[0][1])

    def test_unrelated_message_is_not_consumed(self):
        self.assertFalse(self.window._handle_source_inspection_command("inspect source"))
        self.assertEqual(self.messages, [])


if __name__ == "__main__":
    unittest.main()
