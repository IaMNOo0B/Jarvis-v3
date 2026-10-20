import unittest

from jarvis.desktop_actions import APP_ALIASES
from jarvis.task_planner import TaskPlanner, extract_research_query


class TaskPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()

    def test_hinglish_allowlisted_launch_has_approval_and_verification_steps(self):
        plan = self.planner.plan("Sir Notepad kholo")
        self.assertEqual(plan.intent, "launch_allowlisted_app")
        self.assertEqual([step.name for step in plan.steps], ["authorize", "execute", "verify"])
        self.assertTrue(plan.steps[1].requires_approval)
        self.assertFalse(plan.steps[0].requires_approval)

    def test_every_registered_app_alias_can_be_planned(self):
        # Parser/planner coverage only; this never launches an application.
        for canonical, aliases in APP_ALIASES.items():
            for alias in aliases:
                with self.subTest(app=canonical, alias=alias):
                    plan = self.planner.plan(f"open {alias}")
                    self.assertEqual(plan.intent, "launch_allowlisted_app")
                    self.assertEqual([step.name for step in plan.steps], ["authorize", "execute", "verify"])

    def test_launch_plan_does_not_claim_window_visibility_is_verified(self):
        plan = self.planner.plan("open calculator")
        self.assertTrue(any("does not prove" in item for item in plan.limitations))

    def test_explicit_wikipedia_research_is_planned(self):
        plan = self.planner.plan("Research Wikipedia artificial intelligence")
        self.assertEqual(plan.intent, "research_wikipedia")

    def test_natural_lookup_does_not_require_special_command(self):
        plan = self.planner.plan("Can you find information about black holes?")
        self.assertEqual(plan.intent, "research_wikipedia")
        self.assertEqual(extract_research_query("Can you find information about black holes?", plan.intent), "black holes?")

    def test_natural_github_lookup_extracts_topic(self):
        plan = self.planner.plan("Please search for GitHub agent frameworks")
        self.assertEqual(plan.intent, "research_github")
        self.assertEqual(extract_research_query("Please search for GitHub agent frameworks", plan.intent), "agent frameworks")

    def test_unknown_action_does_not_become_arbitrary_execution(self):
        plan = self.planner.plan("delete every file and clean my computer")
        self.assertEqual(plan.intent, "chat")
        self.assertTrue(plan.limitations)

    def test_empty_request(self):
        self.assertEqual(self.planner.plan(" ").intent, "empty")


if __name__ == "__main__":
    unittest.main()
