"""UI Automation-first desktop action contract.

This module deliberately contains no Windows UIA dependency and performs no real
desktop I/O. A future Windows adapter must implement this contract and verify
postconditions before it can be wired into the GUI.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Protocol

from jarvis.desktop_actions import is_supported_notepad_text


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


class PowerShellUIAutomationBackend:
    """Windows-only semantic UIA adapter, with no coordinates or shell commands.

    The fixed PowerShell script receives requests as JSON on stdin. User text is
    never inserted into source code or command-line arguments. An operation is
    considered verified only when the helper can read the exact text back.
    """

    def __init__(
        self,
        *,
        powershell_executable: str | None = None,
        script_path: str | Path | None = None,
        timeout_seconds: float = 10.0,
        platform_name: str | None = None,
    ) -> None:
        self.platform_name = os.name if platform_name is None else platform_name
        self.powershell_executable = powershell_executable or shutil.which("powershell.exe") or shutil.which("powershell")
        default_script = Path(__file__).resolve().parent.parent / "scripts" / "jarvis_notepad_uia.ps1"
        self.script_path = Path(script_path) if script_path is not None else default_script
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 20.0))

    @property
    def available(self) -> bool:
        return (
            self.platform_name == "nt"
            and bool(self.powershell_executable)
            and self.script_path.is_file()
        )

    def _invoke(self, action: str, app_name: str, target_name: str | None, text: str | None = None) -> bool:
        if not self.available or app_name.strip().casefold() != "notepad":
            return False
        if action not in {"target_exists", "type_text", "verify"}:
            return False
        if target_name != "blank document":
            return False
        if text is not None and not is_supported_notepad_text(text):
            return False
        payload = json.dumps({
            "action": action,
            "app": "notepad",
            "target": target_name,
            "text": text or "",
        }, ensure_ascii=True)
        args = [
            str(self.powershell_executable),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-File",
            str(self.script_path),
        ]
        kwargs = {
            "input": payload,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": self.timeout_seconds,
            "shell": False,
            "check": False,
        }
        # Do not flash an extra console window when called from the GUI.
        if self.platform_name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        try:
            completed = subprocess.run(args, **kwargs)
        except (OSError, subprocess.SubprocessError, ValueError):
            return False
        if completed.returncode != 0 or len(completed.stdout) > 8192:
            return False
        try:
            result = json.loads(completed.stdout.strip())
        except (json.JSONDecodeError, TypeError):
            return False
        return isinstance(result, dict) and result.get("success") is True

    def target_exists(self, app_name: str, target_name: str | None) -> bool:
        return self._invoke("target_exists", app_name, target_name)

    def perform(self, request: UIActionRequest) -> bool:
        if request.action != "type_text" or request.text is None:
            return False
        return self._invoke("type_text", request.app_name, request.target_name, request.text)

    def verify(self, request: UIActionRequest) -> bool:
        if request.action != "type_text" or request.text is None:
            return False
        return self._invoke("verify", request.app_name, request.target_name, request.text)
