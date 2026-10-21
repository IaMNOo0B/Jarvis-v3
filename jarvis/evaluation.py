"""Deterministic golden-task evaluation for planner changes.

This harness measures classification and planned capability sequences only. It never
executes a plan, calls providers, launches apps, or treats a passing score as release
approval. Keep cases curated and reviewed; user conversations are not auto-imported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


class Planner(Protocol):
    def plan(self, request: str): ...


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    request: str
    expected_intent: str
    expected_actions: tuple[str, ...] | None = None


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    actual_intent: str
    actual_actions: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class EvaluationReport:
    total: int
    passed: int
    failed: int
    results: tuple[CaseResult, ...]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0


def evaluate_planner(
    planner: Planner,
    cases: Iterable[EvaluationCase],
    *,
    max_cases: int = 500,
) -> EvaluationReport:
    """Run a bounded, side-effect-free planner benchmark against curated cases."""
    if type(max_cases) is not int or not 1 <= max_cases <= 500:
        raise ValueError("max_cases must be an integer between 1 and 500.")

    materialized: list[EvaluationCase] = []
    seen: set[str] = set()
    for case in cases:
        if len(materialized) >= max_cases:
            raise ValueError("Evaluation case limit exceeded.")
        if not isinstance(case, EvaluationCase):
            raise TypeError("Every evaluation item must be an EvaluationCase.")
        if not isinstance(case.case_id, str) or not case.case_id.strip() or case.case_id in seen:
            raise ValueError("Case IDs must be non-empty unique strings.")
        if not isinstance(case.request, str) or not case.request.strip() or len(case.request) > 2000:
            raise ValueError("Each request must contain 1–2000 characters.")
        if not isinstance(case.expected_intent, str) or not case.expected_intent.strip():
            raise ValueError("Each case needs a non-empty expected intent.")
        if case.expected_actions is not None and (
            not isinstance(case.expected_actions, tuple)
            or any(not isinstance(action, str) or not action.strip() for action in case.expected_actions)
        ):
            raise ValueError("expected_actions must be a tuple of non-empty strings or None.")
        seen.add(case.case_id)
        materialized.append(case)

    results: list[CaseResult] = []
    for case in materialized:
        try:
            plan = planner.plan(case.request)
            actual_intent = getattr(plan, "intent", "")
            actual_actions = tuple(
                step.action for step in getattr(plan, "steps", ())
                if getattr(step, "action", None) is not None
            )
            intent_matches = actual_intent == case.expected_intent
            actions_match = case.expected_actions is None or actual_actions == case.expected_actions
            passed = intent_matches and actions_match
            detail = "matched expected intent and action sequence" if passed else (
                f"expected intent={case.expected_intent!r}, actions={case.expected_actions!r}; "
                f"got intent={actual_intent!r}, actions={actual_actions!r}"
            )
        except Exception as exc:
            actual_intent = "planner_error"
            actual_actions = ()
            passed = False
            detail = f"planner raised {type(exc).__name__}; exception message withheld"
        results.append(CaseResult(case.case_id, passed, actual_intent, actual_actions, detail))

    passed_count = sum(result.passed for result in results)
    return EvaluationReport(len(results), passed_count, len(results) - passed_count, tuple(results))
