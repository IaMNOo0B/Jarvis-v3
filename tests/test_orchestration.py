import unittest

from jarvis.cancellation import CancellationToken
from jarvis.orchestration import Capability, CapabilityRegistry, TaskOutcome, run_capability


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.calls = []
        self.registry.register(Capability(
            "safe_read",
            lambda args: TaskOutcome("safe_read", "verified", "Read completed.", "fake-test-evidence", args.get("value")),
            requires_approval=False,
        ))
        self.registry.register(Capability(
            "write_file",
            lambda args: self.calls.append(args) or {"written": True},
            requires_approval=True,
        ))

    def test_unknown_capability_never_runs(self):
        result = run_capability("arbitrary_shell", {}, registry=self.registry, approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(self.calls, [])

    def test_approval_required_before_handler(self):
        result = run_capability("write_file", {"path": "x"}, registry=self.registry)
        self.assertEqual(result.status, "approval_required")
        self.assertEqual(self.calls, [])

    def test_attempt_is_not_reported_as_verified(self):
        result = run_capability("write_file", {"path": "x"}, registry=self.registry, approved=True)
        self.assertEqual(result.status, "attempted")
        self.assertEqual(result.evidence, "none")

    def test_verified_requires_explicit_evidence(self):
        result = run_capability("safe_read", {"value": 3}, registry=self.registry)
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.evidence, "fake-test-evidence")

    def test_pre_cancelled_operation_does_not_run(self):
        token = CancellationToken()
        token.cancel()
        result = run_capability("write_file", {}, registry=self.registry, approved=True, cancellation=token)
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(self.calls, [])

    def test_handler_exception_does_not_leak_details(self):
        def broken(_args):
            raise RuntimeError("secret internal path")
        registry = CapabilityRegistry()
        registry.register(Capability("broken", broken, requires_approval=False))
        result = run_capability("broken", {}, registry=registry)
        self.assertEqual(result.status, "failed")
        self.assertNotIn("secret", result.detail)

    def test_duplicate_capability_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register(Capability("SAFE_READ", lambda _: None))

    def test_mismatched_evidence_is_rejected(self):
        registry = CapabilityRegistry()
        registry.register(Capability(
            "safe_read",
            lambda _: TaskOutcome("different", "verified", "No.", "fake"),
            requires_approval=False,
        ))
        self.assertEqual(run_capability("safe_read", {}, registry=registry).status, "invalid_result")

    def test_unknown_handler_status_is_rejected(self):
        registry = CapabilityRegistry()
        registry.register(Capability(
            "safe_read",
            lambda _: TaskOutcome("safe_read", "magic_success", "Trust me.", "fake"),
            requires_approval=False,
        ))
        self.assertEqual(run_capability("safe_read", {}, registry=registry).status, "invalid_result")

    def test_verified_result_requires_string_evidence(self):
        registry = CapabilityRegistry()
        registry.register(Capability(
            "safe_read",
            lambda _: TaskOutcome("safe_read", "verified", "Looks good.", None),
            requires_approval=False,
        ))
        self.assertEqual(run_capability("safe_read", {}, registry=registry).status, "invalid_result")


if __name__ == "__main__":
    unittest.main()
