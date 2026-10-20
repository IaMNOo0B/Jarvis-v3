import unittest

from jarvis.safety import ActionRegistry, ActionSpec, RiskLevel, SafetyGate


class SafetyGateTests(unittest.TestCase):
    def setUp(self):
        self.registry = ActionRegistry()
        self.calls = []
        self.registry.register(ActionSpec(
            name="open_notepad",
            risk=RiskLevel.REVERSIBLE,
            description="Open Notepad",
            handler=lambda **kwargs: self.calls.append(kwargs) or "opened",
        ))
        self.gate = SafetyGate()

    def test_unknown_action_is_denied(self):
        decision = self.gate.evaluate("delete_everything", self.registry, user_approved=True)
        self.assertFalse(decision.allowed)

    def test_reversible_action_requires_approval_by_default(self):
        decision = self.gate.evaluate("open_notepad", self.registry)
        self.assertFalse(decision.allowed)

    def test_approved_allowlisted_action_can_call_handler(self):
        result = self.gate.execute("open_notepad", self.registry, user_approved=True, source="test")
        self.assertEqual(result, "opened")
        self.assertEqual(self.calls, [{"source": "test"}])

    def test_registration_requires_handler(self):
        with self.assertRaises(ValueError):
            self.registry.register(ActionSpec("no_handler", RiskLevel.READ_ONLY, "not wired"))

    def test_duplicate_action_is_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register(ActionSpec("OPEN_NOTEPAD", RiskLevel.READ_ONLY, "duplicate", handler=lambda: None))

    def test_external_action_requires_approval(self):
        self.registry.register(ActionSpec("send_message", RiskLevel.EXTERNAL, "Send a message", handler=lambda: True))
        self.assertFalse(self.gate.evaluate("send_message", self.registry).allowed)


if __name__ == "__main__":
    unittest.main()
