import unittest

from scripts.read_candidate_job_results import extract_job_results


def job(name, job_result, test_result):
    return {
        "name": name,
        "conclusion": job_result,
        "steps": [
            {"name": "Run fixed candidate test suite", "conclusion": test_result},
        ],
    }


class CandidateJobResultTests(unittest.TestCase):
    def test_extracts_both_platforms(self):
        results = extract_job_results({
            "jobs": [
                job("Candidate tests (ubuntu-latest)", "success", "success"),
                job("Candidate tests (windows-latest)", "failure", "skipped"),
            ]
        })
        self.assertEqual(results, {
            "linux_test_result": "success",
            "linux_job_result": "success",
            "windows_test_result": "skipped",
            "windows_job_result": "failure",
        })

    def test_rejects_missing_duplicate_or_unfinished_jobs(self):
        with self.assertRaises(ValueError):
            extract_job_results({"jobs": []})
        with self.assertRaises(ValueError):
            extract_job_results({"jobs": [
                job("Candidate tests (ubuntu-latest)", "success", "success"),
                job("Candidate tests (ubuntu-latest)", "success", "success"),
                job("Candidate tests (windows-latest)", "success", "success"),
            ]})
        with self.assertRaises(ValueError):
            extract_job_results({"jobs": [
                job("Candidate tests (ubuntu-latest)", None, "success"),
                job("Candidate tests (windows-latest)", "success", "success"),
            ]})

    def test_rejects_missing_or_ambiguous_test_step(self):
        bad = {
            "name": "Candidate tests (ubuntu-latest)",
            "conclusion": "success",
            "steps": [],
        }
        with self.assertRaises(ValueError):
            extract_job_results({"jobs": [
                bad,
                job("Candidate tests (windows-latest)", "success", "success"),
            ]})

    def test_rejects_malformed_payload(self):
        for payload in (None, [], {}, {"jobs": "not-a-list"}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    extract_job_results(payload)


if __name__ == "__main__":
    unittest.main()
