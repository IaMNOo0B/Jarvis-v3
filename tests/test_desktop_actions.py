import unittest
from unittest.mock import patch

from jarvis.desktop_actions import (launch_allowlisted_app, launch_app_with_approval, parse_app_launch_request, parse_notepad_type_request, parse_explicit_url_request, validate_http_url, open_url_in_browser, open_url_with_approval, is_supported_notepad_text)


class DesktopLaunchTests(unittest.TestCase):
    def test_natural_polite_and_hinglish_launch_phrases(self):
        self.assertEqual(parse_app_launch_request("Can you please open Notepad for me?"), "notepad")
        self.assertEqual(parse_app_launch_request("Jarvis, zara Chrome kholo"), "chrome")
        self.assertEqual(parse_app_launch_request("Please start Chrome now"), "chrome")

    def test_unknown_app_or_ambiguous_request_is_not_executed(self):
        self.assertEqual(parse_app_launch_request("please open calculator"), "calculator")
        self.assertEqual(parse_app_launch_request("please open the file explorer"), "explorer")
        self.assertEqual(parse_app_launch_request("launch Visual Studio Code"), "vs code")
        self.assertEqual(parse_app_launch_request("Can you please open Microsoft Edge for me?"), "edge")
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

    def test_explicit_url_parser_supports_explicit_browser_and_default_chrome(self):
        self.assertEqual(
            parse_explicit_url_request("open https://example.com/docs in Edge"),
            ("edge", "https://example.com/docs"),
        )
        self.assertEqual(
            parse_explicit_url_request("go to https://example.com"),
            ("chrome", "https://example.com"),
        )
        self.assertEqual(
            parse_explicit_url_request("open Chrome and go to https://example.com/path"),
            ("chrome", "https://example.com/path"),
        )
        self.assertEqual(
            parse_explicit_url_request("Edge open https://example.com"),
            ("edge", "https://example.com"),
        )

    def test_http_url_validator_rejects_non_web_schemes_credentials_and_malformed_values(self):
        for value in (
            "file:///C:/Windows/win.ini",
            "javascript:alert(1)",
            "data:text/html,hello",
            "https://user:password@example.com",
            "https://example.com:99999",
            "https://bad host.example",
            "https://example.com\\\\@evil.example",
            "https://example.com/path\\nheader",
        ):
            with self.subTest(value=value):
                self.assertIsNone(validate_http_url(value))
        self.assertEqual(validate_http_url("http://localhost:3000/"), "http://localhost:3000/")

    @patch("jarvis.desktop_actions.subprocess.Popen")
    @patch("jarvis.desktop_actions.os.name", "nt")
    @patch("jarvis.desktop_actions.os.path.isfile", return_value=True)
    @patch("jarvis.desktop_actions.shutil.which", return_value=r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
    def test_explicit_url_open_uses_fixed_browser_argument_without_shell(self, which, isfile, popen):
        url = "https://example.com/path?q=1"
        result = open_url_in_browser("chrome", url)
        self.assertTrue(result.success)
        popen.assert_called_once_with(
            [r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", url],
            shell=False,
            close_fds=True,
        )
        self.assertIn("page load and page contents are not verified", result.detail)

    def test_explicit_url_open_requires_approval_and_rejects_unknown_browser(self):
        result = open_url_with_approval("chrome", "https://example.com", user_approved=False)
        self.assertFalse(result.success)
        self.assertIn("approval is required", result.detail)
        blocked = open_url_with_approval("powershell", "https://example.com", user_approved=True)
        self.assertFalse(blocked.success)
        self.assertIn("allow-list", blocked.detail)

    def test_explicit_notepad_text_parser_supports_english_hinglish_and_quoted_text(self):
        self.assertEqual(parse_notepad_type_request("open Notepad and type Hello Sir"), "Hello Sir")
        self.assertEqual(parse_notepad_type_request('type "Hello Sir" in Notepad'), "Hello Sir")
        self.assertEqual(
            parse_notepad_type_request('open Notepad and type "hello then open Chrome"'),
            "hello then open Chrome",
        )
        self.assertEqual(parse_notepad_type_request("Notepad kholo aur likho Assalam o alaikum"), "Assalam o alaikum")

    def test_notepad_text_parser_fails_closed_on_empty_ambiguous_or_oversized_text(self):
        self.assertIsNone(parse_notepad_type_request("open Notepad and type"))
        self.assertIsNone(parse_notepad_type_request("open Notepad and type " + "x" * 2001))
        self.assertIsNone(parse_notepad_type_request("open Notepad and type " + "😀" * 1100))
        self.assertIsNone(parse_notepad_type_request("open Notepad and type hello then open Chrome"))

    def test_notepad_text_limit_uses_utf16_code_units(self):
        self.assertTrue(is_supported_notepad_text("😀" * 1000))
        self.assertFalse(is_supported_notepad_text("😀" * 1001))
        self.assertFalse(is_supported_notepad_text("  "))

    def test_extra_words_do_not_trigger_launch(self):
        for phrase in (
            "open notepad and type hello",
            "open powershell",
            "close chrome",
            "please open chrome and then type hello",
        ):
            with self.subTest(phrase=phrase):
                self.assertIsNone(parse_app_launch_request(phrase))

    def test_explicit_request_allows_normal_time_adverbs(self):
        self.assertEqual(parse_app_launch_request("please open chrome immediately"), "chrome")

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
