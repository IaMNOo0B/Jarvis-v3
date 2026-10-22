"""Write a bounded, non-secret CI test receipt for GitHub Actions.

This script records the outcome supplied by the trusted workflow runner. It does
not run tests, prove sandbox isolation, or authorize candidate code for deployment.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import sys


_ALLOWED_RESULTS = {"success", "failure", "cancelled"}
_ALLOWED_OS = {"Windows", "Linux", "macOS"}


def _required_env(name: str, pattern: str, maximum: int = 100) -> str:
    value = os.environ.get(name, "").strip()
    if len(value) > maximum or not re.fullmatch(pattern, value):
        raise ValueError(f"Invalid or missing CI receipt field: {name}")
    return value


def build_receipt() -> dict[str, str]:
    """Build receipt only from bounded, validated workflow metadata."""
    commit_sha = _required_env("GITHUB_SHA", r"[0-9a-fA-F]{40}", 40).lower()
    run_id = _required_env("GITHUB_RUN_ID", r"[0-9]{1,20}", 20)
    run_attempt = _required_env("GITHUB_RUN_ATTEMPT", r"[0-9]{1,5}", 5)
    runner_os = _required_env("RUNNER_OS", r"[A-Za-z]{1,10}", 10)
    if runner_os not in _ALLOWED_OS:
        raise ValueError("Unsupported runner OS.")
    result = _required_env("JARVIS_TEST_RESULT", r"[a-z]{1,10}", 10)
    if result not in _ALLOWED_RESULTS:
        raise ValueError("Unsupported CI test result.")
    python_version = platform.python_version()
    return {
        "schema_version": "1",
        "commit_sha": commit_sha,
        "workflow_run_id": run_id,
        "run_attempt": run_attempt,
        "runner_os": runner_os,
        "python_version": python_version,
        "test_command": "python -m unittest discover -s tests -v",
        "result": result,
    }


def write_receipt(output_path: str | Path) -> dict[str, str]:
    receipt = build_receipt()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/write_ci_test_receipt.py OUTPUT_PATH")
    try:
        result = write_receipt(sys.argv[1])
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, sort_keys=True))
