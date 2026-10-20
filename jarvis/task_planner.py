"""Deterministic request planner for safe, bounded JARVIS actions.

The planner describes steps; it does not treat model-generated text as authority.
Execution remains behind the GUI approval path and the action registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from jarvis.desktop_actions import parse_app_launch_request


@dataclass(frozen=True)
class PlanStep:
    name: str
    description: str
    requires_approval: bool
    action: str | None = None


@dataclass(frozen=True)
class TaskPlan:
    original_request: str
    intent: str
    steps: tuple[PlanStep, ...]
    limitations: tuple[str, ...] = ()


class TaskPlanner:
    """Classify only supported intents; unknown requests remain ordinary chat."""

    def plan(self, request: str) -> TaskPlan:
        text = request.strip()
        if not text:
            return TaskPlan(text, "empty", ())
        app = parse_app_launch_request(text)
        if app:
            return TaskPlan(
                text, "launch_allowlisted_app",
                (
                    PlanStep("confirm", f"Ask Sir to approve launching {app.title()}.", True),
                    PlanStep("execute", f"Launch allow-listed app {app.title()} without a shell.", True, "launch_app"),
                    PlanStep("verify", "Report the operating-system launch result; app visibility is not guaranteed.", False),
                ),
                ("Only Notepad and Chrome are currently allow-listed.",),
            )
        lowered = text.casefold()
        if lowered.startswith(("research wikipedia ", "wiki research ", "wikipedia par research ")):
            query = text.split(" ", 2)[-1]
            return TaskPlan(text, "research_wikipedia", (
                PlanStep("fetch", "Query Wikipedia's fixed public search API.", False, "research_wikipedia"),
                PlanStep("cite", "Show result titles, snippets, source URLs and evidence limitations.", False),
            ))
        if lowered.startswith(("research github ", "github research ", "github par research ")):
            query = text.split(" ", 2)[-1]
            return TaskPlan(text, "research_github", (
                PlanStep("fetch", "Query GitHub's fixed public repository search API.", False, "research_github"),
                PlanStep("cite", "Show repository links and metadata; do not claim code was audited.", False),
            ))
        return TaskPlan(
            text, "chat",
            (PlanStep("answer", "Use the configured AI provider and relevant local reference material.", False),),
            ("No unsupported desktop or external action will be inferred from an ordinary chat request.",),
        )
