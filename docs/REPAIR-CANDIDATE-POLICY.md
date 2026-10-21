# Repair candidate review policy

`jarvis.repair_policy.review_candidate` is a conservative metadata gate for a proposed patch. It rejects ambiguous or traversal paths, duplicate/too-many files, oversized diffs, and binary/NUL-containing diffs. Changes to safety/orchestration/capability boundaries, secrets/data, CI workflows, dependency manifests, and startup scripts require manual review.

An ordinary source/test/doc candidate may be marked `eligible_for_tests`, which means only that it can proceed to isolated testing. It is not approval to merge, install, or deploy. Every result has `auto_apply_allowed=False`.

The caller must obtain changed paths from a trusted parsed diff; do not trust a model-provided path list. This module does not create worktrees, parse diffs, run tests, inspect behavior, or modify files. Future integration must use a disposable isolated checkout, run tests without exposing credentials, retain the baseline, and require explicit human approval before any deployment.
