import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.write_ci_test_receipt import build_receipt, write_receipt


class CiTestReceiptTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "123456",
            "GITHUB_RUN_ATTEMPT": "2",
            "RUNNER_OS": "Linux",
            "JARVIS_TEST_RESULT": "success",
            "JARVIS_JOB_RESULT": "success",
        }
        self.env_patch = patch.dict(os.environ, self.env, clear=True)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def test_receipt_contains_bounded_provenance_and_fixed_command(self):
        receipt = build_receipt()
        self.assertEqual(receipt["commit_sha"], "a" * 40)
        self.assertEqual(receipt["workflow_run_id"], "123456")
        self.assertEqual(receipt["unit_test_step_result"], "success")
        self.assertEqual(receipt["job_result"], "success")
        self.assertEqual(
            receipt["test_command"],
            "python -m unittest discover -s tests -v",
        )
        self.assertNotIn("token", json.dumps(receipt).casefold())
        self.assertNotIn("secret", json.dumps(receipt).casefold())

    def test_receipt_is_written_as_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "receipt.json"
            receipt = write_receipt(output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), receipt)

    def test_explicit_candidate_sha_overrides_workflow_commit(self):
        os.environ["JARVIS_CANDIDATE_SHA"] = "b" * 40
        receipt = build_receipt()
        self.assertEqual(receipt["commit_sha"], "b" * 40)

    def test_invalid_candidate_sha_is_rejected(self):
        os.environ["JARVIS_CANDIDATE_SHA"] = "not-a-commit"
        with self.assertRaises(ValueError):
            build_receipt()

    def test_invalid_sha_is_rejected(self):
        os.environ["GITHUB_SHA"] = "not-a-commit"
        with self.assertRaises(ValueError):
            build_receipt()

    def test_unrecognized_result_is_rejected(self):
        os.environ["JARVIS_TEST_RESULT"] = "passed-ish"
        with self.assertRaises(ValueError):
            build_receipt()

    def test_unrecognized_runner_is_rejected(self):
        os.environ["RUNNER_OS"] = "Unknown"
        with self.assertRaises(ValueError):
            build_receipt()

    def test_receipt_does_not_accept_arbitrary_test_commands(self):
        receipt = build_receipt()
        self.assertEqual(receipt["test_command"], "python -m unittest discover -s tests -v")
        self.assertNotIn("JARVIS_TEST_COMMAND", receipt)


if __name__ == "__main__":
    unittest.main()
