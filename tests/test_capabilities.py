import unittest

from jarvis.capabilities import build_capability_registry
from jarvis.orchestration import run_capability, TaskOutcome
from jarvis.research import ResearchReport, ResearchSource


class FakeResearch:
    def __init__(self):
        self.calls = []

    def search(self, source, query):
        self.calls.append((source, query))
        return ResearchReport(query, (ResearchSource("Example", "https://example.com/item", "Snippet", source),), ("Not independently verified.",))


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.research = FakeResearch()
        self.registry = build_capability_registry(self.research)

    def test_only_three_explicit_capabilities_registered(self):
        self.assertEqual(
            set(self.registry._items),
            {"launch_app", "research_wikipedia", "research_github"},
        )

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

    def test_unapproved_app_name_is_blocked(self):
        outcome = run_capability("launch_app", {"app": "powershell"}, registry=self.registry, approved=True)
        self.assertEqual(outcome.status, "blocked")

    def test_unknown_capability_is_not_invented(self):
        outcome = run_capability("run_shell", {}, registry=self.registry, approved=True)
        self.assertEqual(outcome.status, "blocked")


if __name__ == "__main__":
    unittest.main()
