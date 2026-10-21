# Deterministic planner evaluation

`jarvis.evaluation.evaluate_default_golden_suite(planner)` runs the curated baseline suite for greetings, casual chat, app launching, Hinglish, Wikipedia/GitHub research, explicit URL navigation, and a destructive/unsupported request. Each case checks the expected intent and exact registered action sequence.

The lower-level `evaluate_planner` accepts a separate curated suite, with at most 500 cases per run and 2,000 characters per request. It reports mismatches and planner exceptions; it never auto-corrects the planner.

The evaluator is offline and side-effect-free: it does not execute plans, invoke providers, launch applications, or ingest user chat automatically. Review expected results manually. A passing score is evidence for routing only, not proof of Windows end-to-end behavior or permission to auto-deploy a change.

When changing routing rules, add regression cases for English, Hinglish, ambiguous requests, unsupported/destructive requests, and prompt-injection attempts. Candidate changes still require focused tests, full CI, human review, and rollback readiness.
