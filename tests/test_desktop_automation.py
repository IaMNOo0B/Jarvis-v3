import unittest

from jarvis.desktop_automation import (
    AppEntry,
    AppRegistry,
    UIActionRequest,
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

    def test_registry_rejects_duplicate_apps(self):
        with self.assertRaises(ValueError):
            AppRegistry((AppEntry("Notepad", "notepad.exe", ("focus",)), AppEntry("notepad", "other.exe", ("focus",))))


if __name__ == "__main__":
    unittest.main()
