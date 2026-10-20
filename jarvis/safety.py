"""Fail-closed action registry. This module validates requests; it executes nothing."""

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    EXTERNAL = "external"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ActionSpec:
    name: str
    risk: RiskLevel
    description: str
    handler: Callable[..., object] | None = None


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    reason: str


class ActionRegistry:
    """Explicit allow-list. Unknown actions are always denied."""

    def __init__(self) -> None:
        self._actions: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        key = spec.name.strip().casefold()
        if not key or key in self._actions:
            raise ValueError("Action name must be non-empty and unique.")
        if spec.handler is None:
            raise ValueError("An action must have an explicit handler before registration.")
        self._actions[key] = spec

    def get(self, name: str) -> ActionSpec | None:
        return self._actions.get(name.strip().casefold())

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._actions))


class SafetyGate:
    """Fail-closed approval checks; approvals are not persisted by this class."""

    def evaluate(
        self,
        action_name: str,
        registry: ActionRegistry,
        *,
        user_approved: bool = False,
    ) -> ActionDecision:
        spec = registry.get(action_name)
        if spec is None:
            return ActionDecision(False, "Unknown action is not allow-listed.")
        if spec.risk in {RiskLevel.EXTERNAL, RiskLevel.DESTRUCTIVE} and not user_approved:
            return ActionDecision(False, "This action requires explicit user approval.")
        if spec.risk == RiskLevel.REVERSIBLE and not user_approved:
            return ActionDecision(False, "This action requires explicit user approval until policy permits it.")
        return ActionDecision(True, "Action is allow-listed; caller must still verify preconditions and outcome.")

    def execute(
        self,
        action_name: str,
        registry: ActionRegistry,
        *,
        user_approved: bool = False,
        **kwargs: object,
    ) -> object:
        decision = self.evaluate(action_name, registry, user_approved=user_approved)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        spec = registry.get(action_name)
        # Re-checking is defensive; registry is in-memory and not shared externally.
        if spec is None or spec.handler is None:
            raise PermissionError("Action handler is unavailable.")
        return spec.handler(**kwargs)
