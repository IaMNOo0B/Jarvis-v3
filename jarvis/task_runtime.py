"""Execute bounded plans through code-registered capabilities only.

Plans may describe multiple steps, but executable steps must map to known intents and
registered capabilities. Multi-app launch plans run sequentially and stop at the first
failure so the result can report partial side effects accurately.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from jarvis.cancellation import CancellationToken
from jarvis.desktop_actions import APP_EXECUTABLES
from jarvis.orchestration import CapabilityRegistry, TaskOutcome, run_capability
from jarvis.task_planner import TaskPlan, PlanStep


@dataclass(frozen=True)
class RuntimeStepResult:
    name: str
    status: str
    detail: str
    evidence: str = "none"
    target: str | None = None


@dataclass(frozen=True)
class RuntimeResult:
    intent: str
    status: str
    detail: str
    evidence: str = "none"
    capability_result: TaskOutcome | None = None
    step_results: tuple[RuntimeStepResult, ...] = ()


_CAPABILITY_FOR_INTENT = {
    "launch_allowlisted_app": "launch_app",
    "launch_allowlisted_apps": "launch_app",
    "research_wikipedia": "research_wikipedia",
    "research_github": "research_github",
}
_CONTINUE_STATUSES = {"verified", "attempted"}


def execute_plan(
    plan: TaskPlan,
    *,
    registry: CapabilityRegistry,
    arguments: Mapping[str, object] | None = None,
    approved: bool = False,
    cancellation: CancellationToken | None = None,
) -> RuntimeResult:
    """Execute supported plan steps sequentially; never execute ordinary chat.

    The multi-app path accepts only 2–5 unique allow-listed targets. Each app is
    attempted in plan order. On failure, later steps are skipped, and prior
    side effects are called out instead of being rolled back or retried blindly.
    """
    if plan.intent == "empty":
        return RuntimeResult(plan.intent, "invalid_request", "The request is empty.")
    if plan.intent == "chat":
        return RuntimeResult(plan.intent, "chat", "This is a chat request; no action capability was executed.")
    if plan.intent == "invalid_research":
        return RuntimeResult(plan.intent, "invalid_request", "A research topic is required.")

    expected_capability = _CAPABILITY_FOR_INTENT.get(plan.intent)
    if expected_capability is None:
        return RuntimeResult(plan.intent, "blocked", "This intent is not connected to an approved capability.")

    action_steps = tuple(step for step in plan.steps if step.action is not None)
    if not action_steps:
        return RuntimeResult(plan.intent, "blocked", "The plan contains no executable registered capability.")
    if any(step.action != expected_capability for step in action_steps):
        return RuntimeResult(plan.intent, "blocked", "A plan step does not match the intent's registered capability.")

    is_batch = plan.intent == "launch_allowlisted_apps"
    if is_batch:
        targets = tuple(step.target for step in action_steps)
        if (
            not 2 <= len(action_steps) <= 5
            or any(not isinstance(target, str) or target not in APP_EXECUTABLES for target in targets)
            or len(set(targets)) != len(targets)
        ):
            return RuntimeResult(plan.intent, "blocked", "The multi-app plan contains invalid or repeated allow-list targets.")
    elif len(action_steps) != 1:
        return RuntimeResult(plan.intent, "blocked", "This intent supports exactly one executable capability step.")

    if registry.get(expected_capability) is None:
        return RuntimeResult(plan.intent, "unavailable", "The required capability is not registered; no action was run.")

    base_arguments = dict(arguments or {})
    outcomes: list[TaskOutcome] = []
    traces: list[RuntimeStepResult] = []
    for index, step in enumerate(action_steps):
        step_arguments = dict(base_arguments)
        if step.target is not None:
            if plan.intent in {"launch_allowlisted_app", "launch_allowlisted_apps"}:
                if step.target not in APP_EXECUTABLES:
                    return RuntimeResult(plan.intent, "blocked", "The app target is not allow-listed.", step_results=tuple(traces))
                step_arguments["app"] = step.target
        elif is_batch:
            return RuntimeResult(plan.intent, "blocked", "A multi-app step is missing its target.", step_results=tuple(traces))

        outcome = run_capability(
            expected_capability,
            step_arguments,
            registry=registry,
            approved=approved,
            cancellation=cancellation,
        )
        outcomes.append(outcome)
        traces.append(RuntimeStepResult(step.name, outcome.status, outcome.detail, outcome.evidence, step.target))

        if outcome.status not in _CONTINUE_STATUSES:
            if is_batch and any(item.status in _CONTINUE_STATUSES for item in outcomes[:-1]):
                accepted = sum(item.status in _CONTINUE_STATUSES for item in outcomes[:-1])
                detail = (
                    f"Partial execution: {accepted} of {len(action_steps)} app-launch requests were accepted "
                    f"before step {index + 1} ({step.target or step.name}) returned {outcome.status}. "
                    f"{outcome.detail} Check which apps opened before retrying."
                )
                return RuntimeResult(plan.intent, "partial", detail, outcome.evidence, outcome, tuple(traces))
            return RuntimeResult(plan.intent, outcome.status, outcome.detail, outcome.evidence, outcome, tuple(traces))

    last = outcomes[-1]
    if is_batch:
        names = [str(step.target).title() for step in action_steps]
        detail = (
            "Windows accepted launch requests for " + ", ".join(names)
            + ". App visibility and readiness have not been verified."
        )
        return RuntimeResult(plan.intent, "attempted", detail, last.evidence, last, tuple(traces))

    return RuntimeResult(plan.intent, last.status, last.detail, last.evidence, last, tuple(traces))
