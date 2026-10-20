import unittest

from jarvis.task_planner import TaskPlanner


class TaskPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()

    def test_hinglish_allowlisted_launch_has_approval_and_verification_steps(self):
        plan = self.planner.plan("Sir Notepad kholo")
        self.assertEqual(plan.intent, "launch_allowlisted_app")
        self.assertEqual([step.name for step in plan.steps], ["confirm", "execute", "verify"])
        self.assertTrue(plan.steps[0].requires_approval)

    def test_explicit_wikipedia_research_is_planned(self):
        plan = self.planner.plan("Research Wikipedia artificial intelligence")
        self.assertEqual(plan.intent, "research_wikipedia")

    def test_unknown_action_does_not_become_arbitrary_execution(self):
        plan = self.planner.plan("delete every file and clean my computer")
        self.assertEqual(plan.intent, "chat")
        self.assertTrue(plan.limitations)

    def test_empty_request(self):
        self.assertEqual(self.planner.plan(" ").intent, "empty")


if __name__ == "__main__":
    unittest.main()
