"""Deterministic request planner for safe, bounded JARVIS actions.

The planner describes steps; it does not treat model-generated text as authority.
Execution remains behind the GUI approval path and the action registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from jarvis.desktop_actions import APP_EXECUTABLES, parse_app_launch_request


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
                    PlanStep("authorize", f"Treat Sir's explicit request to open {app.title()} as one-request authorization.", False),
                    PlanStep("execute", f"Launch allow-listed app {app.title()} without a shell or another confirmation dialog.", True, "launch_app"),
                    PlanStep("verify", "Report the operating-system launch result; app visibility is not guaranteed.", False),
                ),
                ("A successful process-launch request does not prove the app window is visible or ready.",),
            )
        lowered = text.casefold()
        prefixes = (
            ("research wikipedia ", "research_wikipedia", "wikipedia"),
            ("wiki research ", "research_wikipedia", "wikipedia"),
            ("wikipedia par research ", "research_wikipedia", "wikipedia"),
            ("look up on wikipedia ", "research_wikipedia", "wikipedia"),
            ("find on wikipedia ", "research_wikipedia", "wikipedia"),
            ("research github ", "research_github", "github"),
            ("github research ", "research_github", "github"),
            ("github par research ", "research_github", "github"),
            ("look up on github ", "research_github", "github"),
            ("find on github ", "research_github", "github"),
        )
        for prefix, intent, source in prefixes:
            if lowered.startswith(prefix):
                query = text[len(prefix):].strip()
                if not query:
                    return TaskPlan(text, "invalid_research", (), ("Add a topic after the research source.",))
                return TaskPlan(text, intent, (
                    PlanStep("fetch", f"Query {source.title()}'s fixed public search API.", False, intent),
                    PlanStep("cite", "Show source URLs, bounded snippets and evidence limitations.", False),
                ))

        generic_lookup_prefixes = (
            "research ", "look up ", "search for ", "find information about ",
            "find out about ", "can you research ",
            "can you find information about ", "please research ",
            "please look up ", "please search for ",
        )
        for prefix in generic_lookup_prefixes:
            if lowered.startswith(prefix):
                query = text[len(prefix):].strip()
                if query.casefold().startswith("on wikipedia "):
                    query = query[len("on wikipedia "):].strip()
                if query.casefold().startswith("on github "):
                    query = query[len("on github "):].strip()
                    if query:
                        return TaskPlan(text, "research_github", (
                            PlanStep("fetch", "Query GitHub's fixed public repository API.", False, "research_github"),
                            PlanStep("cite", "Show repository metadata, URLs and evidence limitations.", False),
                        ))
                if query.casefold().startswith("github "):
                    query = query[len("github "):].strip()
                    if query:
                        return TaskPlan(text, "research_github", (
                            PlanStep("fetch", "Query GitHub's fixed public repository API.", False, "research_github"),
                            PlanStep("cite", "Show repository metadata, URLs and evidence limitations.", False),
                        ))
                if not query:
                    return TaskPlan(text, "invalid_research", (), ("Add a topic to look up.",))
                return TaskPlan(text, "research_wikipedia", (
                    PlanStep("fetch", "Query Wikipedia's fixed public search API.", False, "research_wikipedia"),
                    PlanStep("cite", "Show source URLs, bounded snippets and evidence limitations.", False),
                ))
        return TaskPlan(
            text, "chat",
            (PlanStep("answer", "Use the configured AI provider and relevant local reference material.", False),),
            ("No unsupported desktop or external action will be inferred from an ordinary chat request.",),
        )


def extract_research_query(request: str, intent: str) -> str:
    """Extract only the topic text for an already-classified public lookup."""
    text = request.strip()
    lowered = text.casefold()
    prefixes = {
        "research_wikipedia": (
            "research wikipedia ", "wiki research ", "wikipedia par research ",
            "look up on wikipedia ", "find on wikipedia ", "research ",
            "look up ", "search for ", "find information about ", "find out about ",
            "tell me about ", "can you research ", "can you find information about ",
            "please research ", "please look up ", "please search for ",
        ),
        "research_github": (
            "research github ", "github research ", "github par research ",
            "look up on github ", "find on github ",
        ),
    }
    for prefix in prefixes.get(intent, ()):
        if lowered.startswith(prefix):
            query = text[len(prefix):].strip()
            if intent == "research_wikipedia" and query.casefold().startswith("on wikipedia "):
                query = query[len("on wikipedia "):].strip()
            if intent == "research_github" and query.casefold().startswith("on github "):
                query = query[len("on github "):].strip()
            return query
    if intent == "research_github":
        for prefix in (
            "search for ", "find information about ", "look up ", "research ",
            "please search for ", "please research ", "please look up ",
            "can you research ", "can you find information about ",
        ):
            if lowered.startswith(prefix):
                query = text[len(prefix):].strip()
                if query.casefold().startswith("github "):
                    return query[len("github "):].strip()
                if query.casefold().startswith("on github "):
                    return query[len("on github "):].strip()
    return ""
