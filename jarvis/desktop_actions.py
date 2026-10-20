"""Allow-listed Windows app launching; never launch arbitrary paths or shell commands."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from jarvis.safety import ActionRegistry, ActionSpec, RiskLevel, SafetyGate


@dataclass(frozen=True)
class LaunchResult:
    success: bool
    app: str
    detail: str


# Canonical application names and natural-language aliases. Only these apps can
# be launched by the task router; an arbitrary name never becomes an executable.
APP_ALIASES = {
    "notepad": ("notepad", "notes", "text editor"),
    "chrome": ("chrome", "google chrome"),
    "edge": ("edge", "microsoft edge", "ms edge"),
    "calculator": ("calculator", "calc"),
    "explorer": ("explorer", "file explorer", "windows explorer"),
    "task manager": ("task manager", "taskmgr"),
    "paint": ("paint", "mspaint", "microsoft paint"),
    "terminal": ("terminal", "windows terminal", "wt"),
    "vs code": ("vs code", "vscode", "visual studio code"),
}
APP_EXECUTABLES = {
    "notepad": ("notepad.exe",),
    "chrome": ("chrome.exe",),
    "edge": ("msedge.exe",),
    "calculator": ("calc.exe",),
    "explorer": ("explorer.exe",),
    "task manager": ("taskmgr.exe",),
    "paint": ("mspaint.exe",),
    "terminal": ("wt.exe",),
    "vs code": ("code.exe",),
}


def parse_app_launch_request(message: str) -> str | None:
    """Recognize explicit English/Hinglish app-launch requests.

    The user must clearly request an action verb plus an allow-listed app. A
    negated, question-about-the-action, compound, or unknown request is not run.
    """
    normalized = message.casefold()
    for punctuation in ",?.!;:":
        normalized = normalized.replace(punctuation, " ")
    words = normalized.split()
    if not words or len(words) > 30:
        return None
    # Never treat a refusal or a question about whether to act as a launch order.
    if any(word in {"not", "never", "dont", "don't", "avoid", "cancel", "stop"} for word in words):
        return None
    if len(words) >= 2 and words[0:2] in (["should", "i"], ["can", "i"], ["could", "i"], ["shall", "i"]):
        return None

    wrappers = {
        "jarvis", "please", "can", "could", "you", "will", "would", "kindly",
        "zara", "sir", "for", "me", "now", "abhi", "the", "a", "an",
        "app", "application", "desktop", "immediately", "right", "away",
    }
    words = [word for word in words if word not in wrappers]
    launch_verbs = {"open", "launch", "start", "run", "kholo", "khol", "kholna", "chalao", "shuru"}
    words = [word for word in words if word not in {"do"}]
    if len(words) < 2 or words[0] not in launch_verbs:
        # Also support app-first commands like "Notepad kholo".
        if len(words) < 2 or words[-1] not in {"kholo", "khol", "chalao"}:
            return None
        app_words = words[:-1]
    else:
        app_words = words[1:]
    app_name = " ".join(app_words).strip()
    for canonical, aliases in APP_ALIASES.items():
        if app_name == canonical or app_name in aliases:
            return canonical
    return None


def parse_app_launch_batch(message: str) -> tuple[str, ...] | None:
    """Parse a short, explicit sequence of allow-listed app launches.

    Examples: "open Notepad and open Calculator" and "Notepad kholo aur
    Calculator kholo". A bare second app name is accepted only after an
    explicit first launch command ("open Notepad and Calculator"). Unknown,
    mixed-purpose, repeated, or oversized sequences fail closed.
    """
    text = message.strip()
    if not text or len(text) > 240:
        return None
    parts = re.split(r"\s+(?:and\\s+then|and|then|aur)\\s+", text, flags=re.IGNORECASE)
    if len(parts) < 2 or len(parts) > 5:
        return None

    apps: list[str] = []
    for index, part in enumerate(parts):
        app = parse_app_launch_request(part)
        if app is None and index > 0:
            alias = part.casefold().strip().strip(".,!?;:")
            for canonical, aliases in APP_ALIASES.items():
                if alias == canonical or alias in aliases:
                    app = canonical
                    break
        if app is None or app in apps:
            return None
        apps.append(app)
    return tuple(apps)


def launch_app_with_approval(app_name: str, *, user_approved: bool) -> LaunchResult:
    """Launch an allow-listed local app after a per-request safety decision."""
    app = app_name.strip().casefold()
    if app not in APP_EXECUTABLES:
        return LaunchResult(False, app_name, "App is not on the allow-list.")
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="launch_app",
        risk=RiskLevel.REVERSIBLE,
        description=f"Launch allow-listed app: {app}",
        handler=lambda: launch_allowlisted_app(app),
    ))
    gate = SafetyGate()
    try:
        result = gate.execute("launch_app", registry, user_approved=user_approved)
    except PermissionError:
        return LaunchResult(False, app, "Launch blocked: explicit user intent/approval is required.")
    return result


def _find_executable(app: str) -> str | None:
    for command in APP_EXECUTABLES[app]:
        executable = shutil.which(command)
        if executable:
            return executable

    if os.name != "nt":
        return None
    drive = os.environ.get("SystemDrive", "C:")
    root = drive + os.sep
    windows = os.environ.get("WINDIR", os.path.join(root, "Windows"))
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", os.path.join(root, "Program Files"))
    program_files_x86 = os.environ.get("ProgramFiles(x86)", os.path.join(root, "Program Files (x86)"))
    candidates = {
        "notepad": (os.path.join(windows, "System32", "notepad.exe"),),
        "calculator": (os.path.join(windows, "System32", "calc.exe"),),
        "explorer": (os.path.join(windows, "explorer.exe"), os.path.join(windows, "System32", "explorer.exe")),
        "task manager": (os.path.join(windows, "System32", "taskmgr.exe"),),
        "paint": (os.path.join(windows, "System32", "mspaint.exe"),),
        "chrome": (
            os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        ),
        "edge": (
            os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
        ),
        "terminal": (),
        "vs code": (
            os.path.join(local, "Programs", "Microsoft VS Code", "Code.exe"),
            os.path.join(program_files, "Microsoft VS Code", "Code.exe"),
        ),
    }
    return next((path for path in candidates.get(app, ()) if os.path.isfile(path)), None)


def launch_allowlisted_app(app_name: str) -> LaunchResult:
    """Launch a known Windows application with shell=False and fixed arguments."""
    app = app_name.strip().casefold()
    if app not in APP_EXECUTABLES:
        return LaunchResult(False, app_name, "App is not on the allow-list.")
    if os.name != "nt":
        return LaunchResult(False, app, "Desktop launching is supported only on Windows.")
    executable = _find_executable(app)
    if not executable or not os.path.isfile(executable):
        return LaunchResult(False, app, f"{app.title()} was not found on this PC.")
    try:
        subprocess.Popen([executable], shell=False, close_fds=True)
    except OSError:
        return LaunchResult(False, app, f"Windows could not start {app.title()}.")
    return LaunchResult(True, app, f"Windows accepted the launch request for {app.title()}. App visibility has not been verified.")


def parse_notepad_type_request(message: str) -> str | None:
    """Parse explicit requests to place provided text in a blank Notepad document."""
    import re

    text = message.strip()
    if not text or len(text) > 5000:
        return None
    patterns = (
        r"^(?:jarvis[, ]+)?(?:(?:can|could) you )?(?:please )?(?:open|launch|start) notepad(?:,?\s+and(?:\s+then)?|,?\s+then)\s+(?:type|write|enter|put)\s+(.+)$",
        r"^(?:jarvis[, ]+)?notepad\s+(?:kholo|khol)\s+(?:aur|and)\s+(?:likho|type|write)\s+(.+)$",
        r"^(?:please )?(?:type|write|enter)\s+(.+?)\s+(?:in|into) notepad$",
    )
    captured = None
    for pattern in patterns:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            captured = match.group(1).strip()
            break
    if captured is None:
        return None
    if len(captured) >= 2 and captured[0] == captured[-1] and captured[0] in {"'", '"'}:
        captured = captured[1:-1]
    captured = captured.strip()
    if not captured or len(captured) > 2000:
        return None
    return captured
