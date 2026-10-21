"""Safe task orchestration primitives with strict, code-owned argument contracts.

The registry coordinates only explicitly registered capabilities. Model output cannot
register handlers, bypass argument validation, or turn an attempted action into success.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from jarvis.cancellation import CancellationToken, OperationCancelled


@dataclass(frozen=True)
class ArgumentField:
    """A small dependency-free argument contract for one capability field."""

    value_type: type
    required: bool = True
    max_length: int | None = None
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.value_type, type):
            raise TypeError("Argument field value_type must be a type.")
        if self.max_length is not None and self.max_length < 0:
            raise ValueError("max_length cannot be negative.")
        if self.max_length is not None and self.value_type is not str:
            raise ValueError("max_length is supported only for string fields.")
        if self.allowed_values and self.value_type is not str:
            raise ValueError("allowed_values is supported only for string fields.")


@dataclass(frozen=True)
class Capability:
    name: str
    handler: Callable[[Mapping[str, object]], object]
    requires_approval: bool = True
    description: str = ""
    argument_schema: Mapping[str, ArgumentField] | None = None


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
        if capability.argument_schema is not None:
            for key, field_spec in capability.argument_schema.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("Capability schema keys must be non-empty strings.")
                if not isinstance(field_spec, ArgumentField):
                    raise TypeError("Capability schema values must be ArgumentField instances.")
        self._items[name] = capability

    def get(self, name: str) -> Capability | None:
        return self._items.get(name.strip().casefold())

    def validate_arguments(self, capability: Capability, arguments: Mapping[str, object]) -> str | None:
        """Return a safe validation message, or None when arguments satisfy the schema.

        A schema of None preserves compatibility for internal/test capabilities that
        have not declared a contract. First-party capabilities declare strict schemas.
        """
        schema = capability.argument_schema
        if schema is None:
            return None
        if not isinstance(arguments, Mapping):
            return "Arguments must be a mapping."
        if any(not isinstance(key, str) for key in arguments):
            return "Argument names must be strings."
        unexpected = sorted(set(arguments) - set(schema))
        if unexpected:
            return "Unexpected argument field(s): " + ", ".join(unexpected[:8]) + "."
        for key, field_spec in schema.items():
            if key not in arguments:
                if field_spec.required:
                    return f"Required argument '{key}' is missing."
                continue
            value = arguments[key]
            if type(value) is not field_spec.value_type:
                return f"Argument '{key}' must be {field_spec.value_type.__name__}."
            if field_spec.max_length is not None and len(value) > field_spec.max_length:
                return f"Argument '{key}' exceeds the {field_spec.max_length}-character limit."
            if field_spec.allowed_values and value not in field_spec.allowed_values:
                return f"Argument '{key}' is not an allowed value."
        return None


def run_capability(
    name: str,
    arguments: Mapping[str, object],
    *,
    registry: CapabilityRegistry,
    approved: bool = False,
    cancellation: CancellationToken | None = None,
) -> TaskOutcome:
    """Run one known capability, with strict inputs and explicit approval boundaries.

    Handler results are considered verified only when the handler returns a
    TaskOutcome marked verified with explicit, bounded evidence.
    """
    capability = registry.get(name)
    if capability is None:
        return TaskOutcome(name, "blocked", "Unknown capability; no action was run.")
    validation_error = registry.validate_arguments(capability, arguments)
    if validation_error:
        return TaskOutcome(capability.name, "blocked", validation_error)
    if capability.requires_approval and not approved:
        return TaskOutcome(capability.name, "approval_required", "Explicit approval is required.")
    try:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
    except OperationCancelled:
        return TaskOutcome(capability.name, "cancelled", "Task was cancelled before the capability started.")
    try:
        result = capability.handler(dict(arguments))
    except Exception:
        return TaskOutcome(capability.name, "failed", "Capability failed; internal details were withheld.")
    if cancellation is not None and cancellation.cancelled:
        return TaskOutcome(
            capability.name,
            "unknown",
            "Cancellation arrived after execution began; the side effect may have occurred. Verify state before retrying.",
        )
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
