"""Explicit first-party capabilities wired to JARVIS task orchestration."""
from __future__ import annotations

from typing import Mapping

from jarvis.desktop_actions import APP_EXECUTABLES, launch_app_with_approval, open_url_with_approval, validate_http_url
from jarvis.desktop_automation import AppRegistry, PowerShellUIAutomationBackend, UIActionRequest, execute_ui_action
from jarvis.orchestration import Capability, CapabilityRegistry, TaskOutcome
from jarvis.research import PublicResearch


def build_capability_registry(
    research: PublicResearch,
    *,
    ui_backend=None,
) -> CapabilityRegistry:
    """Create a fresh registry of code-owned handlers; model output cannot register actions."""
    registry = CapabilityRegistry()
    notepad_backend = ui_backend if ui_backend is not None else PowerShellUIAutomationBackend()
    ui_registry = AppRegistry()

    def launch(arguments: Mapping[str, object]) -> TaskOutcome:
        app = arguments.get("app")
        if not isinstance(app, str) or app.strip().casefold() not in APP_EXECUTABLES:
            return TaskOutcome("launch_app", "blocked", "App is not on the allow-list.")
        app = app.strip().casefold()
        result = launch_app_with_approval(app, user_approved=True)
        if not result.success:
            return TaskOutcome("launch_app", "failed", result.detail)
        return TaskOutcome("launch_app", "attempted", result.detail, "os_process_launch_accepted")

    def open_url(arguments: Mapping[str, object]) -> TaskOutcome:
        browser = arguments.get("browser")
        url = arguments.get("url")
        if not isinstance(browser, str) or browser.strip().casefold() not in {"chrome", "edge"}:
            return TaskOutcome("open_url", "blocked", "Browser is not on the allow-list.")
        browser = browser.strip().casefold()
        if validate_http_url(url) is None:
            return TaskOutcome("open_url", "blocked", "URL rejected; provide one valid HTTP(S) URL without embedded credentials.")
        result = open_url_with_approval(browser, url, user_approved=True)
        if not result.success:
            status = "blocked" if "rejected" in result.detail.casefold() or "allow-list" in result.detail.casefold() else "failed"
            return TaskOutcome("open_url", status, result.detail)
        return TaskOutcome("open_url", "attempted", result.detail, "os_open_url_request_accepted")

    def type_notepad_text(arguments: Mapping[str, object]) -> TaskOutcome:
        text = arguments.get("text")
        target = arguments.get("target")
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            return TaskOutcome("type_notepad_text", "blocked", "Text is missing or exceeds the supported 2000-character limit.")
        if target != "blank document":
            return TaskOutcome("type_notepad_text", "blocked", "Typing is restricted to a detected blank Notepad document.")
        if getattr(notepad_backend, "available", True) is False:
            return TaskOutcome("type_notepad_text", "failed", "Windows UI Automation is unavailable; no text was sent.")
        request = UIActionRequest("notepad", "type_text", "blank document", text)
        result = execute_ui_action(
            request, registry=ui_registry, backend=notepad_backend, user_approved=True,
        )
        if result.success:
            return TaskOutcome(
                "type_notepad_text", "verified", result.detail,
                "notepad_readback_exact_match",
            )
        if result.status == "blocked":
            return TaskOutcome("type_notepad_text", "blocked", result.detail)
        if result.status == "precondition_failed":
            return TaskOutcome("type_notepad_text", "failed", result.detail)
        if result.status in {"adapter_error", "verification_failed", "action_failed"}:
            return TaskOutcome(
                "type_notepad_text", "unknown",
                f"{result.detail} Text may have been partially entered; inspect Notepad before retrying.",
            )
        return TaskOutcome("type_notepad_text", "failed", result.detail)

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

    registry.register(Capability("launch_app", launch, requires_approval=True, description="Launch a fixed allow-listed Windows app"))
    registry.register(Capability(
        "open_url", open_url, requires_approval=True,
        description="Open one explicit, validated HTTP(S) URL in allow-listed Chrome or Edge",
    ))
    registry.register(Capability(
        "type_notepad_text", type_notepad_text, requires_approval=True,
        description="Type requested text only into a detected blank Notepad document and verify exact read-back",
    ))
    registry.register(Capability("research_wikipedia", lambda args: research_source("wikipedia", "research_wikipedia", args), requires_approval=False, description="Search Wikipedia's public API"))
    registry.register(Capability("research_github", lambda args: research_source("github", "research_github", args), requires_approval=False, description="Search GitHub repository metadata"))
    return registry
