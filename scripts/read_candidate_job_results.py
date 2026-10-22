"""Read trusted GitHub Actions job outcomes for the manual candidate-test workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen


_RUNNER_NAMES = {
    "linux": "Candidate tests (ubuntu-latest)",
    "windows": "Candidate tests (windows-latest)",
}
_ALLOWED_OUTCOMES = {"success", "failure", "cancelled", "skipped"}


def extract_job_results(payload: object) -> dict[str, str]:
    """Extract bounded results from the GitHub Actions jobs API response."""
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("GitHub Actions jobs response is malformed.")
    jobs = payload["jobs"]
    if len(jobs) > 100:
        raise ValueError("Unexpectedly large GitHub Actions jobs response.")

    by_name: dict[str, dict[str, object]] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = job.get("name")
        if isinstance(name, str) and name in _RUNNER_NAMES.values():
            if name in by_name:
                raise ValueError("Duplicate candidate test job in GitHub Actions response.")
            by_name[name] = job

    output: dict[str, str] = {}
    for platform, name in _RUNNER_NAMES.items():
        job = by_name.get(name)
        if job is None:
            raise ValueError(f"Missing expected candidate test job: {name}")
        job_result = job.get("conclusion")
        if job_result not in {"success", "failure", "cancelled"}:
            raise ValueError(f"Candidate job has unsupported conclusion: {name}")
        steps = job.get("steps")
        if not isinstance(steps, list):
            raise ValueError(f"Candidate job steps are missing: {name}")
        test_steps = [
            step for step in steps
            if isinstance(step, dict) and step.get("name") == "Run fixed candidate test suite"
        ]
        if len(test_steps) != 1:
            raise ValueError(f"Expected exactly one candidate test step: {name}")
        test_result = test_steps[0].get("conclusion")
        if test_result not in _ALLOWED_OUTCOMES:
            raise ValueError(f"Candidate test step has unsupported conclusion: {name}")
        output[f"{platform}_test_result"] = test_result
        output[f"{platform}_job_result"] = job_result
    return output


def fetch_job_results(repository: str, run_id: str, token: str) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid GitHub repository identifier.")
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("Invalid GitHub Actions run ID.")
    if not token or len(token) > 4096:
        raise ValueError("Missing or invalid GitHub Actions token.")
    url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Jarvis-CI-Receipt-Reader",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read(1_000_001).decode("utf-8"))
    return extract_job_results(payload)


def main() -> int:
    try:
        results = fetch_job_results(
            os.environ.get("JARVIS_REPOSITORY", ""),
            os.environ.get("JARVIS_RUN_ID", ""),
            os.environ.get("GITHUB_TOKEN", ""),
        )
        output_path = os.environ.get("GITHUB_OUTPUT", "")
        if not output_path:
            raise ValueError("GitHub Actions output path is missing.")
        with Path(output_path).open("a", encoding="utf-8", newline="\n") as output:
            for key, value in results.items():
                if value not in _ALLOWED_OUTCOMES:
                    raise ValueError("Unexpected result value.")
                output.write(f"{key}={value}\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Could not verify candidate job outcomes: {exc}", file=sys.stderr)
        return 1
    print("Retrieved candidate test outcomes from GitHub Actions job metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
