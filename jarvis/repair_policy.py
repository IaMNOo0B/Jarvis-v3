"""Review-only policy gate for proposed self-repair diffs.

This module classifies candidate metadata; it does not apply patches, run tests,
create branches, or authorize deployment. Callers must obtain changed paths from
a trusted diff parser rather than model-supplied summaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Iterable


MAX_CHANGED_FILES = 20
MAX_DIFF_CHARS = 64_000

# Changes here can alter the permission boundary, dependency trust, or startup path.
PROTECTED_EXACT_PATHS = {
    "jarvis/safety.py",
    "jarvis/orchestration.py",
    "jarvis/capabilities.py",
    "jarvis/self_healing.py",
    "jarvis/credentials.py",
    "jarvis/secrets.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "JARVIS.bat",
    "Install_JARVIS.bat",
    ".env",
    "credentials.json",
    "secrets.json",
    "token.json",
    "id_rsa",
}
PROTECTED_PREFIXES = (
    ".github/workflows/",
    "data/",
    "jarvis-data/",
    "protocols/",
    "secrets/",
    "credentials/",
)
PROTECTED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".env")


@dataclass(frozen=True)
class CandidateReview:
    decision: str
    reasons: tuple[str, ...]
    changed_files: tuple[str, ...]
    diff_chars: int
    auto_apply_allowed: bool = False


def _normalize_path(path: object) -> str:
    if not isinstance(path, str) or not path or len(path) > 500:
        raise ValueError("Each changed path must be a non-empty string up to 500 characters.")
    if "\x00" in path or "\\" in path:
        raise ValueError("Changed paths must use safe repository-relative POSIX paths.")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValueError("Absolute paths are not allowed.")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Path traversal or ambiguous path segments are not allowed.")
    return str(PurePosixPath(*parts))


def review_candidate(
    changed_paths: Iterable[str],
    diff_text: str,
    *,
    max_files: int = MAX_CHANGED_FILES,
    max_diff_chars: int = MAX_DIFF_CHARS,
) -> CandidateReview:
    """Classify a candidate for tests/review; never returns permission to apply it."""
    if type(max_files) is not int or not 1 <= max_files <= MAX_CHANGED_FILES:
        raise ValueError("max_files must be an integer from 1 to 20.")
    if type(max_diff_chars) is not int or not 1 <= max_diff_chars <= MAX_DIFF_CHARS:
        raise ValueError("max_diff_chars must be an integer from 1 to 64000.")
    if not isinstance(diff_text, str):
        raise ValueError("Diff must be text.")
    if "\x00" in diff_text:
        raise ValueError("Binary or NUL-containing diffs are not supported.")
    if not diff_text.strip():
        return CandidateReview("rejected", ("candidate diff is empty",), (), 0)
    if len(diff_text) > max_diff_chars:
        return CandidateReview("rejected", ("diff exceeds configured size limit",), (), len(diff_text))

    normalized: list[str] = []
    for path in changed_paths:
        normalized.append(_normalize_path(path))
        if len(normalized) > max_files:
            return CandidateReview("rejected", ("changed-file limit exceeded",), tuple(normalized[:max_files]), len(diff_text))
    if not normalized:
        return CandidateReview("rejected", ("candidate has no changed paths",), (), len(diff_text))
    if len(set(normalized)) != len(normalized):
        return CandidateReview("rejected", ("duplicate changed paths are ambiguous",), tuple(normalized), len(diff_text))

    protected = []
    exact_paths = {item.casefold() for item in PROTECTED_EXACT_PATHS}
    for path in normalized:
        lower = path.casefold()
        filename = lower.rsplit("/", 1)[-1]
        if (
            lower in exact_paths
            or any(lower.startswith(prefix.casefold()) for prefix in PROTECTED_PREFIXES)
            or filename.startswith(".env.")
            or filename.endswith(PROTECTED_SUFFIXES)
        ):
            protected.append(path)

    if protected:
        return CandidateReview(
            "manual_review_required",
            ("candidate touches protected paths: " + ", ".join(sorted(protected)),),
            tuple(normalized),
            len(diff_text),
        )
    return CandidateReview(
        "eligible_for_tests",
        ("bounded candidate may proceed to isolated tests; human review remains mandatory",),
        tuple(normalized),
        len(diff_text),
    )
