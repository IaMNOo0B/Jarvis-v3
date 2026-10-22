"""Validate bounded GitHub Actions receipts before recording repair verification.

A receipt's JSON fields are consistency evidence, not a cryptographic signature.
Callers must obtain it from the artifact attached to the expected GitHub Actions
run through an authenticated GitHub API client; never trust an arbitrary local
JSON file as proof that tests ran.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re


EXPECTED_TEST_COMMAND = "python -m unittest discover -s tests -v"
_RECEIPT_FIELDS = {
    "schema_version",
    "commit_sha",
    "workflow_run_id",
    "run_attempt",
    "runner_os",
    "python_version",
    "test_command",
    "unit_test_step_result",
    "job_result",
}
_SUPPORTED_OS = {"Windows", "Linux", "macOS"}


@dataclass(frozen=True)
class VerifiedCiTestReceipt:
    commit_sha: str
    workflow_run_id: str
    run_attempt: str
    runner_os: str
    python_version: str
    test_command: str
    result: str


def verify_ci_test_receipt(
    receipt: Mapping[str, object],
    *,
    expected_commit_sha: str,
    expected_run_id: str,
    expected_run_attempt: str,
    expected_runner_os: str,
) -> VerifiedCiTestReceipt:
    """Validate receipt shape and bind it to expected trusted workflow metadata.

    This rejects failures and metadata mismatches. It cannot prove artifact
    authenticity by itself; callers must fetch the artifact from the expected
    workflow run using an authenticated GitHub API client.
    """
    if not isinstance(receipt, Mapping):
        raise ValueError("CI receipt must be a JSON object.")
    if set(receipt.keys()) != _RECEIPT_FIELDS:
        raise ValueError("CI receipt has missing or unexpected fields.")

    commit_sha = receipt["commit_sha"]
    run_id = receipt["workflow_run_id"]
    attempt = receipt["run_attempt"]
    runner_os = receipt["runner_os"]
    python_version = receipt["python_version"]

    if not isinstance(expected_commit_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", expected_commit_sha):
        raise ValueError("Expected commit SHA must be a full 40-character Git SHA.")
    if not isinstance(expected_run_id, str) or not re.fullmatch(r"[0-9]{1,20}", expected_run_id):
        raise ValueError("Expected workflow run ID is invalid.")
    if not isinstance(expected_run_attempt, str) or not re.fullmatch(r"[0-9]{1,5}", expected_run_attempt):
        raise ValueError("Expected workflow run attempt is invalid.")
    if expected_runner_os not in _SUPPORTED_OS:
        raise ValueError("Expected runner OS is unsupported.")

    if not isinstance(commit_sha, str) or commit_sha.lower() != expected_commit_sha.lower():
        raise ValueError("CI receipt commit does not match the expected candidate.")
    if run_id != expected_run_id or attempt != expected_run_attempt:
        raise ValueError("CI receipt workflow run metadata does not match the expected run.")
    if runner_os != expected_runner_os or runner_os not in _SUPPORTED_OS:
        raise ValueError("CI receipt runner OS does not match the expected runner.")
    if receipt["schema_version"] != "1":
        raise ValueError("Unsupported CI receipt schema version.")
    if not isinstance(python_version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", python_version):
        raise ValueError("CI receipt Python version is invalid.")
    if receipt["test_command"] != EXPECTED_TEST_COMMAND:
        raise ValueError("CI receipt does not identify the fixed test command.")
    if receipt["unit_test_step_result"] != "success" or receipt["job_result"] != "success":
        raise ValueError("CI test step and overall workflow job must both succeed.")

    return VerifiedCiTestReceipt(
        commit_sha=commit_sha.lower(),
        workflow_run_id=run_id,
        run_attempt=attempt,
        runner_os=runner_os,
        python_version=python_version,
        test_command=EXPECTED_TEST_COMMAND,
        result="passed",
    )
