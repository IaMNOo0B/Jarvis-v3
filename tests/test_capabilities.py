import unittest
from unittest.mock import patch

from jarvis.capabilities import build_capability_registry
from jarvis.desktop_actions import LaunchResult
from jarvis.orchestration import run_capability
from jarvis.research import ResearchReport, ResearchSource


class FakeResearch:
    def __init__(self):
        self.calls = []

    def search(self, source, query):
        self.calls.append((source, query))
        return ResearchReport(query, (ResearchSource("Example", "https://example.com/item", "Snippet", source),), ("Not independently verified.",))


class FakeUIAutomationBackend:
    available = True

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


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.research = FakeResearch()
        self.registry = build_capability_registry(self.research)

    def test_only_explicit_capabilities_registered(self):
        self.assertEqual(
            set(self.registry._items),
            {"launch_app", "open_url", "preflight_notepad_uia", "type_notepad_text", "research_wikipedia", "research_github"},
        )

    def test_declared_argument_contract_blocks_unexpected_fields_before_launch(self):
        with patch("jarvis.capabilities.launch_app_with_approval") as launch:
            outcome = run_capability(
                "launch_app", {"app": "notepad", "command": "format c:"},
                registry=self.registry, approved=True,
            )
        self.assertEqual(outcome.status, "blocked")
        self.assertIn("Unexpected argument", outcome.detail)
        launch.assert_not_called()

    def test_declared_argument_contract_blocks_oversized_research_before_provider_call(self):
        outcome = run_capability(
            "research_wikipedia", {"query": "x" * 241}, registry=self.registry,
        )
        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(self.research.calls, [])

    def test_declared_argument_contract_rejects_non_string_url_and_bad_browser(self):
        for arguments in (
            {"browser": "powershell", "url": "https://example.com"},
            {"browser": "chrome", "url": 123},
            {"browser": "chrome", "url": "https://example.com", "extra": "ignored"},
        ):
            with self.subTest(arguments=arguments):
                result = run_capability("open_url", arguments, registry=self.registry, approved=True)
                self.assertEqual(result.status, "blocked")

    def test_research_is_bounded_and_returns_source_evidence(self):
        outcome = run_capability("research_wikipedia", {"query": "AI"}, registry=self.registry)
        self.assertEqual(outcome.status, "verified")
        self.assertIn("https://example.com/item", outcome.evidence)
        self.assertEqual(self.research.calls, [("wikipedia", "AI")])

    def test_invalid_research_query_does_not_call_provider(self):
        outcome = run_capability("research_github", {"query": " "}, registry=self.registry)
        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(self.research.calls, [])

    def test_app_launch_needs_approval(self):
        outcome = run_capability("launch_app", {"app": "notepad"}, registry=self.registry)
        self.assertEqual(outcome.status, "approval_required")

    def test_all_fixed_allowlisted_apps_can_reach_the_launcher(self):
        # Mock the OS side effect: this test verifies routing, not a real launch.
        with patch(
            "jarvis.capabilities.launch_app_with_approval",
            return_value=LaunchResult(True, "calculator", "mock launch accepted"),
        ) as launch:
            outcome = run_capability(
                "launch_app", {"app": " calculator "},
                registry=self.registry, approved=True,
            )
        self.assertEqual(outcome.status, "attempted")
        launch.assert_called_once_with("calculator", user_approved=True)

    def test_unapproved_app_name_is_blocked(self):
        with patch("jarvis.capabilities.launch_app_with_approval") as launch:
            outcome = run_capability("launch_app", {"app": "powershell"}, registry=self.registry, approved=True)
        self.assertEqual(outcome.status, "blocked")
        launch.assert_not_called()

    def test_open_url_capability_requires_approval(self):
        outcome = run_capability(
            "open_url", {"browser": "chrome", "url": "https://example.com"},
            registry=self.registry,
        )
        self.assertEqual(outcome.status, "approval_required")

    def test_open_url_capability_uses_validated_allowlisted_browser(self):
        with patch(
            "jarvis.capabilities.open_url_with_approval",
            return_value=LaunchResult(True, "edge", "Windows accepted URL request."),
        ) as opener:
            outcome = run_capability(
                "open_url", {"browser": " edge ", "url": "https://example.com/path"},
                registry=self.registry, approved=True,
            )
        self.assertEqual(outcome.status, "attempted")
        self.assertEqual(outcome.evidence, "os_open_url_request_accepted")
        opener.assert_called_once_with("edge", "https://example.com/path", user_approved=True)

    def test_open_url_capability_rejects_invalid_scheme_without_browser_launch(self):
        with patch("jarvis.capabilities.open_url_with_approval") as opener:
            outcome = run_capability(
                "open_url", {"browser": "chrome", "url": "javascript:alert(1)"},
                registry=self.registry, approved=True,
            )
        self.assertEqual(outcome.status, "blocked")
        opener.assert_not_called()

    def test_notepad_preflight_verifies_fixed_ui_automation_helper_availability(self):
        backend = FakeUIAutomationBackend()
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability("preflight_notepad_uia", {}, registry=registry)
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.evidence, "powershell_uia_helper_available")
        self.assertEqual(backend.calls, [])

    def test_notepad_preflight_fails_before_any_desktop_action_when_unavailable(self):
        backend = FakeUIAutomationBackend()
        backend.available = False
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability("preflight_notepad_uia", {}, registry=registry)
        self.assertEqual(result.status, "failed")
        self.assertIn("Notepad was not launched", result.detail)
        self.assertEqual(backend.calls, [])

    def test_notepad_text_entry_rejects_utf16_oversize_before_touching_backend(self):
        backend = FakeUIAutomationBackend()
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability(
            "type_notepad_text",
            {"target": "blank document", "text": "😀" * 1001},
            registry=registry,
            approved=True,
        )
        self.assertEqual(result.status, "blocked")
        self.assertEqual(backend.calls, [])

    def test_notepad_text_entry_requires_approval(self):
        backend = FakeUIAutomationBackend()
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability(
            "type_notepad_text",
            {"target": "blank document", "text": "hello"},
            registry=registry,
        )
        self.assertEqual(result.status, "approval_required")
        self.assertEqual(backend.calls, [])

    def test_notepad_text_entry_requires_exact_readback(self):
        backend = FakeUIAutomationBackend()
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability(
            "type_notepad_text",
            {"target": "blank document", "text": "hello Sir"},
            registry=registry,
            approved=True,
        )
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.evidence, "notepad_readback_exact_match")
        self.assertEqual([call[0] for call in backend.calls], ["target_exists", "perform", "verify"])
        self.assertEqual(backend.calls[1][1].text, "hello Sir")

    def test_unverified_notepad_input_is_reported_as_unknown(self):
        backend = FakeUIAutomationBackend(verify=False)
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability(
            "type_notepad_text",
            {"target": "blank document", "text": "hello"},
            registry=registry,
            approved=True,
        )
        self.assertEqual(result.status, "unknown")
        self.assertIn("inspect Notepad before retrying", result.detail)

    def test_unavailable_notepad_adapter_does_not_type(self):
        backend = FakeUIAutomationBackend()
        backend.available = False
        registry = build_capability_registry(self.research, ui_backend=backend)
        result = run_capability(
            "type_notepad_text",
            {"target": "blank document", "text": "hello"},
            registry=registry,
            approved=True,
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(backend.calls, [])

    def test_unknown_capability_is_not_invented(self):
        outcome = run_capability("run_shell", {}, registry=self.registry, approved=True)
        self.assertEqual(outcome.status, "blocked")


if __name__ == "__main__":
    unittest.main()
