import unittest

from jarvis.evaluation import (
    DEFAULT_GOLDEN_CASES,
    EvaluationCase,
    evaluate_default_golden_suite,
    evaluate_planner,
)
from jarvis.task_planner import TaskPlanner


class PlannerEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.planner = TaskPlanner()

    def test_default_golden_suite_covers_chat_hinglish_research_and_safe_actions(self):
        report = evaluate_default_golden_suite(self.planner)
        self.assertEqual(report.total, len(DEFAULT_GOLDEN_CASES))
        self.assertEqual(report.failed, 0, [result for result in report.results if not result.passed])
        self.assertEqual(report.pass_rate, 1.0)

    def test_golden_cases_score_intent_and_action_sequence_without_execution(self):
        cases = (
            EvaluationCase("open-notepad", "open Notepad", "launch_allowlisted_app", ("launch_app",)),
            EvaluationCase("wikipedia", "Research Wikipedia black holes", "research_wikipedia", ("research_wikipedia",)),
            EvaluationCase("unsafe", "delete every file and clean my computer", "chat", ()),
        )
        report = evaluate_planner(self.planner, cases)
        self.assertEqual((report.total, report.passed, report.failed), (3, 3, 0))
        self.assertEqual(report.pass_rate, 1.0)

    def test_reports_regressions_instead_of_auto_fixing_them(self):
        cases = (EvaluationCase("expected-open", "open Notepad", "chat", ()),)
        report = evaluate_planner(self.planner, cases)
        self.assertEqual(report.failed, 1)
        self.assertFalse(report.results[0].passed)
        self.assertIn("expected intent", report.results[0].detail)

    def test_rejects_duplicate_ids_invalid_limits_and_unbounded_suites(self):
        with self.assertRaises(ValueError):
            evaluate_planner(self.planner, (
                EvaluationCase("same", "open Notepad", "launch_allowlisted_app"),
                EvaluationCase("same", "open Calculator", "launch_allowlisted_app"),
            ))
        with self.assertRaises(ValueError):
            evaluate_planner(self.planner, (EvaluationCase(7, "open Notepad", "launch_allowlisted_app"),))
        with self.assertRaises(ValueError):
            evaluate_planner(self.planner, (), max_cases=501)
        with self.assertRaises(ValueError):
            evaluate_planner(self.planner, (
                EvaluationCase(str(i), "open Notepad", "launch_allowlisted_app")
                for i in range(3)
            ), max_cases=2)

    def test_empty_suite_has_neutral_rate(self):
        report = evaluate_planner(self.planner, ())
        self.assertEqual(report.total, 0)
        self.assertEqual(report.pass_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
