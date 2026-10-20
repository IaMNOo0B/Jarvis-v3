import unittest
from unittest.mock import patch

from jarvis.desktop_actions import launch_allowlisted_app, parse_app_launch_request


class DesktopLaunchTests(unittest.TestCase):
    def test_exact_launch_phrases(self):
        self.assertEqual(parse_app_launch_request("open notepad"), "notepad")
        self.assertEqual(parse_app_launch_request("Launch Chrome"), "chrome")
        self.assertEqual(parse_app_launch_request("start notepad"), "notepad")

    def test_extra_words_do_not_trigger_launch(self):
        self.assertIsNone(parse_app_launch_request("open notepad and type hello"))
        self.assertIsNone(parse_app_launch_request("open powershell"))
        self.assertIsNone(parse_app_launch_request("please open chrome"))

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
