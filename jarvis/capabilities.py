"""Explicit first-party capabilities wired to JARVIS task orchestration."""
from __future__ import annotations

from typing import Mapping

from jarvis.desktop_actions import launch_app_with_approval
from jarvis.orchestration import Capability, CapabilityRegistry, TaskOutcome
from jarvis.research import PublicResearch


def build_capability_registry(research: PublicResearch) -> CapabilityRegistry:
    """Create a fresh registry of supported operations; no model-defined handlers."""

    registry = CapabilityRegistry()

    def launch(arguments: Mapping[str, object]) -> TaskOutcome:
        app = arguments.get("app")
        if not isinstance(app, str) or app.casefold() not in {"notepad", "chrome"}:
            return TaskOutcome("launch_app", "blocked", "App is not on the allow-list.")
        result = launch_app_with_approval(app, user_approved=True)
        if not result.success:
            return TaskOutcome("launch_app", "failed", result.detail)
        return TaskOutcome("launch_app", "attempted", result.detail, "os_process_launch_accepted")

    def research_source(source: str, capability_name: str, arguments: Mapping[str, object]) -> TaskOutcome:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 240:
            return TaskOutcome(capability_name, "blocked", "Research query is missing or invalid.")
        try:
            report = research.search(source, query)
        except Exception:
            return TaskOutcome(capability_name, "failed", "Public research failed; no result was fabricated.")
        evidence = "\n".join(item.url for item in report.sources if item.url.startswith("https://"))[:2000]
        # An empty result is still a completed lookup, but not evidence that the topic has no facts.
        return TaskOutcome(
            capability_name,
            "verified",
            "Public-source lookup returned a report; independent fact verification is not implied.",
            evidence or "source_request_completed_no_urls_returned",
            report,
        )

    registry.register(Capability("launch_app", launch, requires_approval=True, description="Launch Notepad or Chrome"))
    registry.register(Capability("research_wikipedia", lambda args: research_source("wikipedia", "research_wikipedia", args), requires_approval=False, description="Search Wikipedia's public API"))
    registry.register(Capability("research_github", lambda args: research_source("github", "research_github", args), requires_approval=False, description="Search GitHub repository metadata"))
    return registry
