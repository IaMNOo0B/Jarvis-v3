import unittest

from jarvis.cancellation import CancellationToken
from jarvis.orchestration import Capability, CapabilityRegistry, TaskOutcome
from jarvis.task_planner import TaskPlanner
from jarvis.task_runtime import RuntimeResult, action_event_for_runtime, execute_plan


class TaskRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()
        self.registry = CapabilityRegistry()
        self.calls = []
        self.registry.register(Capability(
            "preflight_notepad_uia",
            lambda args: TaskOutcome(
                "preflight_notepad_uia", "verified",
                "The fixed Notepad UI Automation helper is available.",
                "powershell_uia_helper_available",
            ),
            requires_approval=False,
        ))
        self.registry.register(Capability(
            "launch_app",
            lambda args: self.calls.append(("launch", args)) or {"accepted": True},
            requires_approval=True,
        ))
        self.type_calls = []
        self.registry.register(Capability(
            "type_notepad_text",
            lambda args: self.type_calls.append(args) or TaskOutcome(
                "type_notepad_text", "verified", "Notepad text exactly matches the requested text.",
                "notepad_readback_exact_match",
            ),
            requires_approval=True,
        ))
        self.url_calls = []
        self.registry.register(Capability(
            "open_url",
            lambda args: self.url_calls.append(args) or TaskOutcome(
                "open_url", "attempted",
                "Windows accepted the request to open the supplied URL; page load is not verified.",
                "os_open_url_request_accepted",
            ),
            requires_approval=True,
        ))
        self.registry.register(Capability(
            "research_wikipedia",
            lambda args: TaskOutcome("research_wikipedia", "verified", "Sources retrieved.", "test-source-url"),
            requires_approval=False,
        ))

    def test_chat_never_executes_capability(self):
        result = execute_plan(self.planner.plan("Tell me about the moon"), registry=self.registry, approved=True)
        self.assertEqual(result.status, "chat")
        self.assertEqual(self.calls, [])

    def test_launch_needs_explicit_approval(self):
        plan = self.planner.plan("open Notepad")
        result = execute_plan(plan, registry=self.registry, arguments={"app": "notepad"})
        self.assertEqual(result.status, "approval_required")
        self.assertEqual(self.calls, [])

    def test_approved_launch_is_only_attempted_without_postcondition(self):
        plan = self.planner.plan("open Notepad")
        result = execute_plan(plan, registry=self.registry, arguments={"app": "notepad"}, approved=True)
        self.assertEqual(result.status, "attempted")
        self.assertEqual(len(self.calls), 1)

    def test_explicit_url_plan_runs_only_registered_browser_handler(self):
        plan = self.planner.plan("open https://example.com/path in Edge")
        result = execute_plan(plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "attempted")
        self.assertEqual(
            self.url_calls,
            [{"browser": "edge", "url": "https://example.com/path"}],
        )
        self.assertEqual(action_event_for_runtime(result)[0], "action_accepted")

    def test_malformed_url_plan_is_blocked_before_browser_handler(self):
        plan = self.planner.plan("open https://example.com in Chrome")
        bad_steps = tuple(
            type(step)(step.name, step.description, step.requires_approval,
                       step.action, step.target, "javascript:alert(1)")
            if step.action == "open_url" else step
            for step in plan.steps
        )
        bad_plan = type(plan)(plan.original_request, plan.intent, bad_steps, plan.limitations)
        result = execute_plan(bad_plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.url_calls, [])

    def test_notepad_typing_runs_launch_then_verified_text_entry(self):
        plan = self.planner.plan("open Notepad and type Hello Sir")
        result = execute_plan(plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "verified")
        self.assertEqual([call[1]["app"] for call in self.calls], ["notepad"])
        self.assertEqual(self.type_calls, [{"target": "blank document", "text": "Hello Sir"}])
        self.assertEqual([step.status for step in result.step_results], ["verified", "attempted", "verified"])
        self.assertEqual(result.evidence, "notepad_readback_exact_match")

    def test_oversized_utf16_notepad_plan_is_blocked_before_launch(self):
        plan = self.planner.plan("open Notepad and type hello")
        bad_steps = tuple(
            type(step)(
                step.name, step.description, step.requires_approval,
                step.action, step.target, "😀" * 1100,
            )
            if step.action == "type_notepad_text" else step
            for step in plan.steps
        )
        bad_plan = type(plan)(plan.original_request, plan.intent, bad_steps, plan.limitations)
        result = execute_plan(bad_plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.type_calls, [])

    def test_unavailable_notepad_uia_preflight_stops_before_launch(self):
        registry = CapabilityRegistry()
        launch_calls = []
        registry.register(Capability(
            "preflight_notepad_uia",
            lambda args: TaskOutcome(
                "preflight_notepad_uia", "failed",
                "Windows PowerShell UI Automation is unavailable; Notepad was not launched.",
            ),
            requires_approval=False,
        ))
        registry.register(Capability(
            "launch_app",
            lambda args: launch_calls.append(args["app"]) or {"accepted": True},
            requires_approval=True,
        ))
        registry.register(Capability(
            "type_notepad_text",
            lambda args: TaskOutcome(
                "type_notepad_text", "verified", "Read-back matches.",
                "notepad_readback_exact_match",
            ),
            requires_approval=True,
        ))
        result = execute_plan(
            self.planner.plan("open Notepad and type Hello Sir"),
            registry=registry, approved=True,
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(launch_calls, [])
        self.assertEqual([step.status for step in result.step_results], ["failed", "skipped", "skipped"])

    def test_notepad_typing_failure_after_launch_is_partial_not_success(self):
        registry = CapabilityRegistry()
        launch_calls = []
        registry.register(Capability(
            "preflight_notepad_uia",
            lambda args: TaskOutcome(
                "preflight_notepad_uia", "verified", "Helper available.",
                "powershell_uia_helper_available",
            ),
            requires_approval=False,
        ))
        registry.register(Capability(
            "launch_app",
            lambda args: launch_calls.append(args["app"]) or {"accepted": True},
            requires_approval=True,
        ))
        registry.register(Capability(
            "type_notepad_text",
            lambda args: TaskOutcome("type_notepad_text", "unknown", "Read-back failed; inspect Notepad."),
            requires_approval=True,
        ))
        plan = self.planner.plan("open Notepad and type Hello Sir")
        result = execute_plan(plan, registry=registry, approved=True)
        self.assertEqual(result.status, "partial")
        self.assertEqual(launch_calls, ["notepad"])
        self.assertIn("check the desktop state before retrying", result.detail.casefold())

    def test_missing_composite_capability_fails_before_launch(self):
        registry = CapabilityRegistry()
        calls = []
        registry.register(Capability(
            "preflight_notepad_uia",
            lambda args: TaskOutcome(
                "preflight_notepad_uia", "verified", "Helper available.",
                "powershell_uia_helper_available",
            ),
            requires_approval=False,
        ))
        registry.register(Capability(
            "launch_app", lambda args: calls.append(args) or {"accepted": True}, requires_approval=True,
        ))
        result = execute_plan(
            self.planner.plan("open Notepad and type Hello Sir"),
            registry=registry, approved=True,
        )
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(calls, [])

    def test_multi_app_plan_runs_registered_steps_in_order(self):
        plan = self.planner.plan("open Notepad and Calculator")
        result = execute_plan(plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "attempted")
        self.assertEqual([call[1]["app"] for call in self.calls], ["notepad", "calculator"])
        self.assertEqual([step.target for step in result.step_results], ["notepad", "calculator"])
        self.assertIn("visibility and readiness have not been verified", result.detail)

    def test_multi_app_plan_stops_after_failure_and_reports_partial_side_effects(self):
        registry = CapabilityRegistry()
        called = []

        def launch(args):
            app = args["app"]
            called.append(app)
            if app == "calculator":
                return TaskOutcome("launch_app", "failed", "Calculator launch failed.")
            return TaskOutcome("launch_app", "attempted", "Launch request accepted.", "os_process_launch_accepted")

        registry.register(Capability("launch_app", launch, requires_approval=True))
        plan = self.planner.plan("open Notepad and open Calculator and open Paint")
        result = execute_plan(plan, registry=registry, approved=True)
        self.assertEqual(result.status, "partial")
        self.assertEqual(called, ["notepad", "calculator"])
        self.assertIn("1 of 3 app-launch requests were accepted", result.detail)
        self.assertIn("check which apps opened", result.detail.casefold())
        self.assertEqual([step.status for step in result.step_results], ["attempted", "failed", "skipped"])

    def test_invalid_multi_app_target_is_blocked_without_running(self):
        plan = self.planner.plan("open Notepad and Calculator")
        bad_steps = tuple(
            type(step)(step.name, step.description, step.requires_approval, step.action, "powershell")
            if step.target == "calculator" else step
            for step in plan.steps
        )
        bad_plan = type(plan)(plan.original_request, plan.intent, bad_steps, plan.limitations)
        result = execute_plan(bad_plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.calls, [])

    def test_runtime_event_mapping_preserves_cancelled_unknown_and_partial_outcomes(self):
        partial = RuntimeResult(
            "launch_allowlisted_apps", "partial",
            "Partial execution: one app accepted; remaining actions skipped.",
        )
        unknown = RuntimeResult(
            "notepad_type_text", "unknown",
            "Cancellation arrived during typing; inspect the desktop before retrying.",
        )
        cancelled = RuntimeResult(
            "launch_allowlisted_app", "cancelled",
            "Task was cancelled before the capability started.",
        )
        self.assertEqual(action_event_for_runtime(partial)[0], "action_partial")
        self.assertEqual(action_event_for_runtime(unknown)[0], "action_unknown")
        self.assertEqual(action_event_for_runtime(cancelled)[0], "cancelled")

    def test_runtime_event_mapping_does_not_hide_completed_postconditions(self):
        verified = RuntimeResult(
            "notepad_type_text", "verified", "Notepad read-back matched.",
            "notepad_readback_exact_match",
            TaskOutcome("type_notepad_text", "verified", "Notepad read-back matched.",
                        "notepad_readback_exact_match"),
        )
        attempted = RuntimeResult(
            "launch_allowlisted_app", "attempted", "Windows accepted the launch.",
            "os_process_launch_accepted",
            TaskOutcome("launch_app", "attempted", "Windows accepted the launch.",
                        "os_process_launch_accepted"),
        )
        self.assertEqual(action_event_for_runtime(verified)[0], "action_verified")
        self.assertEqual(action_event_for_runtime(attempted)[0], "action_accepted")

    def test_research_uses_only_registered_handler(self):
        plan = self.planner.plan("research Wikipedia artificial intelligence")
        result = execute_plan(plan, registry=self.registry, arguments={"query": "artificial intelligence"})
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.evidence, "test-source-url")

    def test_missing_capability_fails_closed(self):
        result = execute_plan(self.planner.plan("research GitHub agents"), registry=self.registry)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(self.calls, [])

    def test_cancelled_capability_does_not_run(self):
        token = CancellationToken()
        token.cancel()
        result = execute_plan(
            self.planner.plan("open Notepad"), registry=self.registry,
            arguments={"app": "notepad"}, approved=True, cancellation=token,
        )
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(self.calls, [])

    def test_unknown_intent_is_blocked(self):
        plan = self.planner.plan("some unsupported thing")
        plan = type(plan)(plan.original_request, "arbitrary_shell", plan.steps)
        result = execute_plan(plan, registry=self.registry, approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
