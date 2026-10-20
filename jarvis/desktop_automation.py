"""UI Automation-first desktop action contract.

This module deliberately contains no Windows UIA dependency and performs no real
desktop I/O. A future Windows adapter must implement this contract and verify
postconditions before it can be wired into the GUI.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AppEntry:
    name: str
    executable: str
    allowed_actions: tuple[str, ...]


class AppRegistry:
    """Small explicit registry; unknown apps/actions are rejected by default."""

    def __init__(self, entries: tuple[AppEntry, ...] | None = None) -> None:
        defaults = entries if entries is not None else (
            AppEntry("notepad", "notepad.exe", ("focus", "type_text", "press_enter")),
            AppEntry("chrome", "chrome.exe", ("focus",)),
        )
        self._entries: dict[str, AppEntry] = {}
        for entry in defaults:
            key = entry.name.strip().casefold()
            if not key or key in self._entries:
                raise ValueError("App names must be non-empty and unique.")
            if not entry.executable or not entry.allowed_actions:
                raise ValueError("App entries need an executable and allowed actions.")
            self._entries[key] = entry

    def get(self, app_name: str) -> AppEntry | None:
        return self._entries.get(app_name.strip().casefold())

    def allows(self, app_name: str, action: str) -> bool:
        entry = self.get(app_name)
        return entry is not None and action in entry.allowed_actions


@dataclass(frozen=True)
class UIActionRequest:
    app_name: str
    action: str
    target_name: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class UIActionResult:
    success: bool
    status: str
    detail: str


class UIAutomationBackend(Protocol):
    """Adapter contract: implementations must use semantic UIA selectors, not coordinates."""

    def target_exists(self, app_name: str, target_name: str | None) -> bool: ...
    def perform(self, request: UIActionRequest) -> bool: ...
    def verify(self, request: UIActionRequest) -> bool: ...


def execute_ui_action(
    request: UIActionRequest,
    *,
    registry: AppRegistry,
    backend: UIAutomationBackend,
    user_approved: bool = False,
) -> UIActionResult:
    """Execute a narrowly allow-listed UIA action only after approval and verification."""
    app = request.app_name.strip().casefold()
    action = request.action.strip().casefold()
    if not registry.allows(app, action):
        return UIActionResult(False, "blocked", "App/action is not on the allow-list.")
    if not user_approved:
        return UIActionResult(False, "approval_required", "Explicit approval is required.")
    if action in {"type_text", "press_enter"} and not request.target_name:
        return UIActionResult(False, "precondition_failed", "A named UI target is required.")
    if action == "type_text" and request.text is None:
        return UIActionResult(False, "precondition_failed", "Text input is missing.")
    try:
        if not backend.target_exists(app, request.target_name):
            return UIActionResult(False, "precondition_failed", "The requested UI target was not found.")
        if not backend.perform(request):
            return UIActionResult(False, "action_failed", "The UI Automation adapter did not confirm the action.")
        if not backend.verify(request):
            return UIActionResult(False, "verification_failed", "The action ran, but its postcondition was not verified.")
    except Exception:
        return UIActionResult(False, "adapter_error", "UI Automation failed safely; outcome is unknown.")
    return UIActionResult(True, "verified", "Action completed and its postcondition was verified.")
