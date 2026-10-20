"""Safe task orchestration primitives.

This module coordinates registered capabilities only. It never evaluates model text
as code, invents handlers, or treats an attempted action as verified success.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from jarvis.cancellation import CancellationToken, OperationCancelled


@dataclass(frozen=True)
class Capability:
    name: str
    handler: Callable[[Mapping[str, object]], object]
    requires_approval: bool = True
    description: str = ""


@dataclass(frozen=True)
class TaskOutcome:
    capability: str
    status: str
    detail: str
    evidence: str = "none"
    value: object | None = None


class CapabilityRegistry:
    """Explicit registry; registration is code-owned, never model-created."""

    def __init__(self) -> None:
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        name = capability.name.strip().casefold()
        if not name or name in self._items:
            raise ValueError("Capability names must be non-empty and unique.")
        self._items[name] = capability

    def get(self, name: str) -> Capability | None:
        return self._items.get(name.strip().casefold())


def run_capability(
    name: str,
    arguments: Mapping[str, object],
    *,
    registry: CapabilityRegistry,
    approved: bool = False,
    cancellation: CancellationToken | None = None,
) -> TaskOutcome:
    """Run one known capability, with cancellation and explicit approval boundaries.

    Handler results are considered verified only when the handler returns a
    TaskOutcome marked verified. Arbitrary return values are merely attempted.
    """
    capability = registry.get(name)
    if capability is None:
        return TaskOutcome(name, "blocked", "Unknown capability; no action was run.")
    if capability.requires_approval and not approved:
        return TaskOutcome(capability.name, "approval_required", "Explicit approval is required.")
    try:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        result = capability.handler(dict(arguments))
        if cancellation is not None:
            cancellation.raise_if_cancelled()
    except OperationCancelled:
        return TaskOutcome(capability.name, "cancelled", "Task cancelled at a safe boundary.")
    except Exception:
        return TaskOutcome(capability.name, "failed", "Capability failed; internal details were withheld.")
    if isinstance(result, TaskOutcome):
        if not isinstance(result.capability, str) or result.capability.casefold() != capability.name.casefold():
            return TaskOutcome(capability.name, "invalid_result", "Handler returned mismatched capability evidence.")
        allowed_statuses = {"verified", "attempted", "failed", "blocked", "cancelled", "unknown"}
        if result.status not in allowed_statuses:
            return TaskOutcome(capability.name, "invalid_result", "Handler returned an unsupported outcome status.")
        if not isinstance(result.detail, str) or len(result.detail) > 2000:
            return TaskOutcome(capability.name, "invalid_result", "Handler returned invalid or oversized detail.")
        if result.status == "verified":
            if not isinstance(result.evidence, str) or not result.evidence.strip() or len(result.evidence) > 2000:
                return TaskOutcome(capability.name, "invalid_result", "Verified outcomes require bounded, explicit evidence.")
            return result
        evidence = result.evidence if isinstance(result.evidence, str) and result.evidence else "none"
        if len(evidence) > 2000:
            return TaskOutcome(capability.name, "invalid_result", "Handler returned oversized evidence.")
        return TaskOutcome(capability.name, result.status, result.detail, evidence, result.value)
    return TaskOutcome(
        capability.name,
        "attempted",
        "Handler returned without explicit postcondition evidence.",
        "none",
        result,
    )
