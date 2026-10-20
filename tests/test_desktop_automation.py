import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from jarvis.desktop_automation import (
    AppEntry,
    AppRegistry,
    UIActionRequest,
    PowerShellUIAutomationBackend,
    execute_ui_action,
)


class FakeBackend:
    def __init__(self, *, target=True, perform=True, verify=True):
        self.target = target
        self.perform_result = perform
        self.verify_result = verify
        self.calls = []

    def target_exists(self, app_name, target_name):
        self.calls.append(("target_exists", app_name, target_name))
        return self.target

    def perform(self, request):
        self.calls.append(("perform", request))
        return self.perform_result

    def verify(self, request):
        self.calls.append(("verify", request))
        return self.verify_result


class DesktopAutomationContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = AppRegistry()
        self.request = UIActionRequest("notepad", "type_text", "Document", "hello")
        self.backend = FakeBackend()

    def test_requires_explicit_approval(self):
        result = execute_ui_action(self.request, registry=self.registry, backend=self.backend)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "approval_required")
        self.assertEqual(self.backend.calls, [])

    def test_unknown_app_or_action_is_blocked(self):
        request = UIActionRequest("powershell", "type_text", "Console", "hello")
        result = execute_ui_action(request, registry=self.registry, backend=self.backend, user_approved=True)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.backend.calls, [])

    def test_target_must_exist_before_action(self):
        backend = FakeBackend(target=False)
        result = execute_ui_action(self.request, registry=self.registry, backend=backend, user_approved=True)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "precondition_failed")
        self.assertFalse(any(call[0] == "perform" for call in backend.calls))

    def test_missing_named_target_is_rejected(self):
        request = UIActionRequest("notepad", "type_text", None, "hello")
        result = execute_ui_action(request, registry=self.registry, backend=self.backend, user_approved=True)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "precondition_failed")

    def test_success_requires_verified_postcondition(self):
        result = execute_ui_action(self.request, registry=self.registry, backend=self.backend, user_approved=True)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "verified")
        self.assertEqual([call[0] for call in self.backend.calls], ["target_exists", "perform", "verify"])

    def test_unverified_postcondition_is_not_success(self):
        backend = FakeBackend(verify=False)
        result = execute_ui_action(self.request, registry=self.registry, backend=backend, user_approved=True)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "verification_failed")

    def test_adapter_exception_fails_closed(self):
        class BrokenBackend(FakeBackend):
            def perform(self, request):
                raise RuntimeError("sensitive internal detail")

        result = execute_ui_action(self.request, registry=self.registry, backend=BrokenBackend(), user_approved=True)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "adapter_error")
        self.assertNotIn("sensitive", result.detail)

    def test_powershell_adapter_passes_user_text_as_json_stdin_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fixed.ps1"
            script.write_text("# fixed test helper", encoding="utf-8")
            backend = PowerShellUIAutomationBackend(
                powershell_executable="powershell.exe", script_path=script, platform_name="nt",
            )
            completed = CompletedProcess(args=["powershell.exe"], returncode=0, stdout='{"success": true}', stderr="")
            with patch("jarvis.desktop_automation.subprocess.run", return_value=completed) as run:
                self.assertTrue(backend._invoke("type_text", "notepad", "blank document", "Hello & $Sir"))
            args, kwargs = run.call_args
            self.assertFalse(kwargs["shell"])
            payload = json.loads(kwargs["input"])
            self.assertEqual(payload["text"], "Hello & $Sir")
            self.assertEqual(payload["app"], "notepad")

    def test_powershell_adapter_rejects_unsupported_targets_and_oversized_text(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fixed.ps1"
            script.write_text("# fixed test helper", encoding="utf-8")
            backend = PowerShellUIAutomationBackend(
                powershell_executable="powershell.exe", script_path=script, platform_name="nt",
            )
            with patch("jarvis.desktop_automation.subprocess.run") as run:
                self.assertFalse(backend._invoke("type_text", "powershell", "blank document", "hello"))
                self.assertFalse(backend._invoke("type_text", "notepad", "other target", "hello"))
                self.assertFalse(backend._invoke("type_text", "notepad", "blank document", "x" * 2001))
            run.assert_not_called()

    def test_powershell_adapter_reports_nonzero_exit_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "fixed.ps1"
            script.write_text("# fixed test helper", encoding="utf-8")
            backend = PowerShellUIAutomationBackend(
                powershell_executable="powershell.exe", script_path=script, platform_name="nt",
            )
            failed = CompletedProcess(args=["powershell.exe"], returncode=1, stdout="{}", stderr="failed")
            with patch("jarvis.desktop_automation.subprocess.run", return_value=failed):
                self.assertFalse(backend._invoke("type_text", "notepad", "blank document", "hello"))

    def test_registry_rejects_duplicate_apps(self):
        with self.assertRaises(ValueError):
            AppRegistry((AppEntry("Notepad", "notepad.exe", ("focus",)), AppEntry("notepad", "other.exe", ("focus",))))


if __name__ == "__main__":
    unittest.main()
