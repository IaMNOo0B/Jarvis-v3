import unittest

from jarvis.app import respond
from jarvis.intents import parse_intent


class IntentTests(unittest.TestCase):
    def test_empty_input_is_detected(self):
        self.assertEqual(parse_intent("  ").name, "empty")

    def test_help_is_case_insensitive(self):
        self.assertEqual(parse_intent(" /HELP ").name, "help")

    def test_exit_aliases(self):
        self.assertEqual(parse_intent("Quit").name, "exit")
        self.assertEqual(parse_intent("/exit").name, "exit")

    def test_unknown_input_remains_chat(self):
        self.assertEqual(parse_intent("open chrome").name, "chat")

    def test_no_desktop_action_is_claimed(self):
        self.assertIn("not enabled yet", respond("open chrome"))

    def test_help_discloses_current_scope(self):
        self.assertIn("not enabled yet", respond("help"))


if __name__ == "__main__":
    unittest.main()
