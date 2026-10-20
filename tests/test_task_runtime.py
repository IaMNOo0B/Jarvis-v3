import unittest

from jarvis.cancellation import CancellationToken
from jarvis.orchestration import Capability, CapabilityRegistry, TaskOutcome
from jarvis.task_planner import TaskPlanner
from jarvis.task_runtime import execute_plan


class TaskRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()
        self.registry = CapabilityRegistry()
        self.calls = []
        self.registry.register(Capability(
            "launch_app",
            lambda args: self.calls.append(("launch", args)) or {"accepted": True},
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
