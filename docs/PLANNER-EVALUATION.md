# Deterministic planner evaluation

`jarvis.evaluation.evaluate_planner` runs a curated golden-task suite against a planner and reports intent/action-sequence regressions. It is intentionally offline and side-effect-free: it does not execute plans, invoke providers, launch applications, or ingest user chat automatically.

Use it when changing routing rules or comparing candidate planners. Include normal English, Hinglish, ambiguous requests, unsupported/destructive requests, and prompt-injection attempts. Review expected results manually; a passing score is evidence for routing only, not proof of Windows end-to-end behavior or permission to auto-deploy a change.

The suite is capped at 500 cases per run and each request at 2,000 characters. Planner exceptions are counted as failures without persisting their exception messages. Candidate changes still require focused tests, the full CI suite, human review, and rollback readiness.
