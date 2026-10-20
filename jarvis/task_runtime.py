"""Execute bounded plans through code-registered capabilities only.

Plans may contain a small fixed sequence. Each executable step must match the
intent's code-owned capability sequence; model text never creates new handlers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from jarvis.cancellation import CancellationToken
from jarvis.desktop_actions import APP_EXECUTABLES, is_supported_notepad_text, validate_http_url
from jarvis.orchestration import CapabilityRegistry, TaskOutcome, run_capability
from jarvis.task_planner import TaskPlan


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


def action_event_for_runtime(result: RuntimeResult) -> tuple[str, str]:
    """Map a desktop runtime result to a UI event without hiding partial work.

    Runtime status is authoritative: pre-action cancellation stays cancelled,
    cancellation during a side effect is unknown, and known prior work followed
    by a stopped/failed step remains partial rather than being mislabeled unknown.
    """
    if result.status == "partial":
        return "action_partial", result.detail
    if result.status == "unknown":
        detail = result.detail
        if "retry" not in detail.casefold():
            detail += " Inspect the desktop before retrying."
        return "action_unknown", detail
    if result.status == "cancelled":
        return "cancelled", result.detail
    if result.status == "verified":
        return "action_verified", result.detail
    if result.status == "attempted" and result.capability_result is not None:
        return "action_accepted", result.detail
    return "action_failed", result.detail


_CAPABILITIES_FOR_INTENT = {
    "launch_allowlisted_app": ("launch_app",),
    "open_url": ("open_url",),
    "launch_allowlisted_apps": ("launch_app",),
    "research_wikipedia": ("research_wikipedia",),
    "research_github": ("research_github",),
    "notepad_type_text": ("launch_app", "type_notepad_text"),
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
    """Execute registered steps sequentially and report side effects honestly.

    Multi-app plans are bounded to five unique allow-listed targets. The Notepad
    typing workflow is a fixed two-capability sequence and types only into a
    detected blank document, with exact read-back verification from its handler.
    """
    if plan.intent == "empty":
        return RuntimeResult(plan.intent, "invalid_request", "The request is empty.")
    if plan.intent == "chat":
        return RuntimeResult(plan.intent, "chat", "This is a chat request; no action capability was executed.")
    if plan.intent == "invalid_research":
        return RuntimeResult(plan.intent, "invalid_request", "A research topic is required.")

    expected = _CAPABILITIES_FOR_INTENT.get(plan.intent)
    if expected is None:
        return RuntimeResult(plan.intent, "blocked", "This intent is not connected to an approved capability.")

    action_steps = tuple(step for step in plan.steps if step.action is not None)
    if not action_steps:
        return RuntimeResult(plan.intent, "blocked", "The plan contains no executable registered capability.")

    is_batch = plan.intent == "launch_allowlisted_apps"
    is_notepad_sequence = plan.intent == "notepad_type_text"
    is_url_navigation = plan.intent == "open_url"
    if is_batch:
        targets = tuple(step.target for step in action_steps)
        if (
            not 2 <= len(action_steps) <= 5
            or tuple(step.action for step in action_steps) != ("launch_app",) * len(action_steps)
            or any(not isinstance(target, str) or target not in APP_EXECUTABLES for target in targets)
            or len(set(targets)) != len(targets)
        ):
            return RuntimeResult(plan.intent, "blocked", "The multi-app plan contains invalid or repeated allow-list targets.")
    elif is_url_navigation:
        if (
            tuple(step.action for step in action_steps) != expected
            or len(action_steps) != 1
            or action_steps[0].target not in {"chrome", "edge"}
            or validate_http_url(action_steps[0].input_text) is None
        ):
            return RuntimeResult(plan.intent, "blocked", "The browser URL step is malformed or unsafe; no action was run.")
    elif is_notepad_sequence:
        if (
            tuple(step.action for step in action_steps) != expected
            or action_steps[0].target != "notepad"
            or action_steps[1].target != "blank document"
            or not is_supported_notepad_text(action_steps[1].input_text)
        ):
            return RuntimeResult(plan.intent, "blocked", "The Notepad plan is malformed; no action was run.")
    elif tuple(step.action for step in action_steps) != expected:
        return RuntimeResult(plan.intent, "blocked", "Plan steps do not match the intent's registered capability sequence.")

    # Resolve every required capability before starting the first side effect.
    capability_names = tuple(step.action for step in action_steps)
    missing = [name for name in capability_names if name is not None and registry.get(name) is None]
    if missing:
        return RuntimeResult(plan.intent, "unavailable", f"Required capability '{missing[0]}' is not registered; no action was run.")

    base_arguments = dict(arguments or {})
    outcomes: list[TaskOutcome] = []
    traces: list[RuntimeStepResult] = []
    for index, step in enumerate(action_steps):
        capability_name = step.action
        if capability_name is None:
            return RuntimeResult(plan.intent, "blocked", "A planned executable step has no capability.", step_results=tuple(traces))
        step_arguments = dict(base_arguments)

        if capability_name == "launch_app":
            if step.target is not None:
                if not isinstance(step.target, str) or step.target not in APP_EXECUTABLES:
                    return RuntimeResult(plan.intent, "blocked", "The app target is not allow-listed.", step_results=tuple(traces))
                step_arguments["app"] = step.target
            elif is_batch or is_notepad_sequence:
                return RuntimeResult(plan.intent, "blocked", "A launch step is missing its allow-listed target.", step_results=tuple(traces))
        elif capability_name == "open_url":
            if step.target not in {"chrome", "edge"} or validate_http_url(step.input_text) is None:
                return RuntimeResult(plan.intent, "blocked", "The browser URL target is not allow-listed or the URL is invalid.", step_results=tuple(traces))
            step_arguments["browser"] = step.target
            step_arguments["url"] = step.input_text
        elif capability_name == "type_notepad_text":
            if step.target != "blank document":
                return RuntimeResult(plan.intent, "blocked", "Typing target is not allow-listed.", step_results=tuple(traces))
            step_arguments["target"] = step.target
            step_arguments["text"] = step.input_text

        outcome = run_capability(
            capability_name,
            step_arguments,
            registry=registry,
            approved=approved,
            cancellation=cancellation,
        )
        outcomes.append(outcome)
        traces.append(RuntimeStepResult(step.name, outcome.status, outcome.detail, outcome.evidence, step.target))

        if outcome.status not in _CONTINUE_STATUSES:
            for remaining in action_steps[index + 1:]:
                traces.append(RuntimeStepResult(
                    remaining.name, "skipped",
                    "Skipped because an earlier step did not complete.",
                    "none", remaining.target,
                ))
            earlier_steps_ran = any(item.status in _CONTINUE_STATUSES for item in outcomes[:-1])
            if len(action_steps) > 1 and earlier_steps_ran:
                if is_batch:
                    accepted = sum(item.status in _CONTINUE_STATUSES for item in outcomes[:-1])
                    detail = (
                        f"Partial execution: {accepted} of {len(action_steps)} app-launch requests were accepted "
                        f"before step {index + 1} ({step.target or step.name}) returned {outcome.status}; "
                        f"all remaining steps were skipped. {outcome.detail} Check which apps opened before retrying."
                    )
                else:
                    detail = (
                        f"Partial execution: an earlier step ran before step {index + 1} "
                        f"({capability_name}) returned {outcome.status}; all remaining steps were skipped. "
                        f"{outcome.detail} Check the desktop state before retrying."
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
    if is_notepad_sequence:
        return RuntimeResult(plan.intent, "verified", last.detail, last.evidence, last, tuple(traces))
    return RuntimeResult(plan.intent, last.status, last.detail, last.evidence, last, tuple(traces))
