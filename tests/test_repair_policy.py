import unittest

from jarvis.repair_policy import review_candidate


class RepairCandidatePolicyTests(unittest.TestCase):
    def test_normal_source_change_is_only_eligible_for_tests(self):
        result = review_candidate(["jarvis/learning.py", "tests/test_learning.py"], "diff")
        self.assertEqual(result.decision, "eligible_for_tests")
        self.assertFalse(result.auto_apply_allowed)
        self.assertIn("human review remains mandatory", result.reasons[0])

    def test_protected_runtime_secret_and_key_paths_require_manual_review(self):
        for path in (
            "jarvis/safety.py",
            "jarvis/orchestration.py",
            "data/memory.json",
            ".github/workflows/test.yml",
            "JARVIS.bat",
            ".env.local",
            "config/service.pem",
            "keys/signing.key",
        ):
            with self.subTest(path=path):
                result = review_candidate([path], "diff")
                self.assertEqual(result.decision, "manual_review_required")
                self.assertFalse(result.auto_apply_allowed)

    def test_rejects_path_traversal_absolute_paths_and_windows_paths(self):
        for path in ("../outside.py", "/tmp/file.py", "C:/Windows/file.py", "jarvis/../secret.py", r"jarvis\secret.py"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    review_candidate([path], "diff")

    def test_rejects_empty_duplicate_and_too_many_paths(self):
        with self.assertRaises(ValueError):
            review_candidate([], "diff")
        with self.assertRaises(ValueError):
            review_candidate(["jarvis/a.py", "jarvis/a.py"], "diff")
        result = review_candidate([f"jarvis/file{i}.py" for i in range(21)], "diff")
        self.assertEqual(result.decision, "rejected")
        self.assertIn("changed-file limit exceeded", result.reasons[0])

    def test_rejects_oversized_or_binary_diff(self):
        result = review_candidate(["jarvis/a.py"], "x" * 64001)
        self.assertEqual(result.decision, "rejected")
        with self.assertRaises(ValueError):
            review_candidate(["jarvis/a.py"], "abc\x00def")

    def test_rejects_invalid_limits_and_non_text_diff(self):
        with self.assertRaises(ValueError):
            review_candidate(["jarvis/a.py"], "diff", max_files=21)
        with self.assertRaises(ValueError):
            review_candidate(["jarvis/a.py"], "diff", max_diff_chars=64001)
        with self.assertRaises(ValueError):
            review_candidate(["jarvis/a.py"], b"diff")


if __name__ == "__main__":
    unittest.main()
