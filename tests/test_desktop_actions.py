import unittest
from unittest.mock import patch

from jarvis.desktop_actions import launch_allowlisted_app, launch_app_with_approval, parse_app_launch_request


class DesktopLaunchTests(unittest.TestCase):
    def test_natural_polite_and_hinglish_launch_phrases(self):
        self.assertEqual(parse_app_launch_request("Can you please open Notepad for me?"), "notepad")
        self.assertEqual(parse_app_launch_request("Jarvis, zara Chrome kholo"), "chrome")
        self.assertEqual(parse_app_launch_request("Please start Chrome now"), "chrome")

    def test_unknown_app_or_ambiguous_request_is_not_executed(self):
        self.assertIsNone(parse_app_launch_request("please open calculator"))
        self.assertIsNone(parse_app_launch_request("can you explain how Chrome works"))

    def test_exact_launch_phrases(self):
        for phrase, expected in (
            ("open notepad", "notepad"),
            ("Launch Chrome", "chrome"),
            ("start notepad", "notepad"),
            ("notepad kholo", "notepad"),
            ("chrome khol", "chrome"),
            ("kholo chrome", "chrome"),
            ("Jarvis open notepad", "notepad"),
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(parse_app_launch_request(phrase), expected)

    def test_extra_words_do_not_trigger_launch(self):
        for phrase in (
            "open notepad and type hello",
            "open powershell",
            "kindly open chrome",
            "close chrome",
            "notepad kholo abhi",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_app_launch_request(phrase))

    def test_launch_gate_rejects_without_approval(self):
        result = launch_app_with_approval("notepad", user_approved=False)
        self.assertFalse(result.success)
        self.assertIn("approval is required", result.detail)

    def test_launch_gate_rejects_unknown_app_even_when_approved(self):
        result = launch_app_with_approval("powershell", user_approved=True)
        self.assertFalse(result.success)
        self.assertIn("allow-list", result.detail)

    @patch("jarvis.desktop_actions.launch_allowlisted_app")
    def test_approved_launch_calls_allowlisted_handler(self, launch):
        launch.return_value = type("Result", (), {"success": True, "detail": "accepted"})()
        result = launch_app_with_approval("notepad", user_approved=True)
        self.assertTrue(result.success)
        launch.assert_called_once_with("notepad")

    def test_unknown_app_is_rejected(self):
        result = launch_allowlisted_app("powershell")
        self.assertFalse(result.success)
        self.assertIn("allow-list", result.detail)

    @patch("jarvis.desktop_actions.os.name", "posix")
    def test_non_windows_launch_is_rejected(self):
        result = launch_allowlisted_app("notepad")
        self.assertFalse(result.success)
        self.assertIn("only on Windows", result.detail)

    @patch("jarvis.desktop_actions.subprocess.Popen")
    @patch("jarvis.desktop_actions.os.name", "nt")
    @patch("jarvis.desktop_actions.os.path.isfile", return_value=True)
    @patch("jarvis.desktop_actions.shutil.which", return_value=r"C:\Windows\System32\notepad.exe")
    def test_notepad_launch_uses_argument_list_without_shell(self, which, isfile, popen):
        result = launch_allowlisted_app("notepad")
        self.assertTrue(result.success)
        popen.assert_called_once_with([r"C:\Windows\System32\notepad.exe"], shell=False, close_fds=True)
        self.assertIn("not been verified", result.detail)


if __name__ == "__main__":
    unittest.main()
