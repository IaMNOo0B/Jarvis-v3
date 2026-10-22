# Repair candidate review policy

`jarvis.repair_policy.review_candidate` is a conservative metadata gate for a proposed patch. It rejects ambiguous or traversal paths, duplicate/too-many files, oversized diffs, and binary/NUL-containing diffs. Changes to safety/orchestration/capability boundaries, secrets/data, CI workflows, dependency manifests, and startup scripts require manual review.

An ordinary source/test/doc candidate may be marked `eligible_for_tests`, which means only that it can proceed to isolated testing. It is not approval to merge, install, or deploy. Every result has `auto_apply_allowed=False`.

The caller must obtain changed paths from a trusted parsed diff; do not trust a model-provided path list. This module does not create worktrees, parse diffs, run tests, inspect behavior, or modify files. Future integration must use a disposable isolated checkout, run tests without exposing credentials, retain the baseline, and require explicit human approval before any deployment.


## Repair ledger audit integration

`RepairLedger.review_candidate_policy` records the policy decision against an existing repair proposal. It stores the decision, bounded reasons/path metadata, character count, timestamp, and SHA-256 of the diff only when the diff is within the configured size limit. Oversized diffs are rejected without hashing or storing their contents. Candidate source/diff text is never persisted by this audit method.

A policy receipt does not change the proposal status, count as a test result, authorize a merge, or approve deployment. Unknown proposals are rejected. Unsafe path input is recorded as a rejected policy result. Callers must still supply paths from a trusted diff parser; this method is not itself a Git diff parser or isolated test runner.


## Trusted changed-path parsing

`parse_git_changed_paths` accepts raw bytes from a controlled `git diff --name-only -z` invocation. It does not invoke Git itself. It requires NUL-terminated UTF-8 paths, caps the output at 40,000 bytes and 20 paths, and rejects traversal/absolute/Windows paths, empty entries, duplicate paths (case-insensitive), and malformed encoding. The caller remains responsible for running Git with fixed arguments, a trusted repository directory, no shell, and bounded time/output. Never pass a model-generated path list as if it were Git output.
