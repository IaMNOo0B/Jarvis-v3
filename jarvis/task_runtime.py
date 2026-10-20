"""Bridge deterministic plans to the explicit capability registry.

The runtime deliberately does not create handlers from model output. Callers must
register each supported capability in code and supply approval/cancellation state.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from jarvis.cancellation import CancellationToken
from jarvis.orchestration import CapabilityRegistry, TaskOutcome, run_capability
from jarvis.task_planner import TaskPlan


@dataclass(frozen=True)
class RuntimeResult:
    intent: str
    status: str
    detail: str
    evidence: str = "none"
    capability_result: TaskOutcome | None = None


_CAPABILITY_FOR_INTENT = {
    "launch_allowlisted_app": "launch_app",
    "research_wikipedia": "research_wikipedia",
    "research_github": "research_github",
}


def execute_plan(
    plan: TaskPlan,
    *,
    registry: CapabilityRegistry,
    arguments: Mapping[str, object] | None = None,
    approved: bool = False,
    cancellation: CancellationToken | None = None,
) -> RuntimeResult:
    """Execute a single supported plan capability; never execute ordinary chat."""
    if plan.intent == "empty":
        return RuntimeResult(plan.intent, "invalid_request", "The request is empty.")
    if plan.intent == "chat":
        return RuntimeResult(plan.intent, "chat", "This is a chat request; no action capability was executed.")
    if plan.intent == "invalid_research":
        return RuntimeResult(plan.intent, "invalid_request", "A research topic is required.")
    capability_name = _CAPABILITY_FOR_INTENT.get(plan.intent)
    if capability_name is None:
        return RuntimeResult(plan.intent, "blocked", "This intent is not connected to an approved capability.")
    if registry.get(capability_name) is None:
        return RuntimeResult(plan.intent, "unavailable", "The required capability is not registered; no action was run.")
    outcome = run_capability(
        capability_name,
        arguments or {},
        registry=registry,
        approved=approved,
        cancellation=cancellation,
    )
    return RuntimeResult(plan.intent, outcome.status, outcome.detail, outcome.evidence, outcome)
