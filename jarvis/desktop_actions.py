"""Allow-listed Windows app launching; never launch arbitrary paths or shell commands."""

import ipaddress
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit

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


def validate_http_url(value: object) -> str | None:
    """Validate an explicit HTTP(S) URL before passing it to a browser process.

    Only HTTP and HTTPS are allowed. URL user-info, whitespace/control
    characters, backslashes, malformed hosts, and invalid ports are rejected.
    Private/LAN hosts are not automatically blocked because the user supplies
    the exact destination explicitly (for example, a local development server).
    """
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value) or "\\" in value:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        hostname = parts.hostname
        if not hostname:
            return None
        port = parts.port
        if port is not None and not 1 <= port <= 65535:
            return None
        # Ensure that a non-IP hostname is syntactically valid and IDNA-encodable.
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            ascii_host = hostname.encode("idna").decode("ascii")
            if len(ascii_host) > 253:
                return None
            labels = ascii_host.rstrip(".").split(".")
            if not labels or any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in labels
            ):
                return None
    except (UnicodeError, ValueError):
        return None
    return value


def parse_explicit_url_request(message: str) -> tuple[str, str] | None:
    """Parse a direct request to open one explicit HTTP(S) URL in Chrome or Edge."""
    text = message.strip()
    if not text or len(text) > 2200:
        return None
    patterns = (
        r"^(?:jarvis[, ]+)?(?:please\s+)?(?:open|visit|go to|navigate to|browse to|kholo)\s+(?P<url>https?://\S+?)(?:\s+(?:in|using|with)\s+(?P<browser>google chrome|chrome|microsoft edge|ms edge|edge))?$",
        r"^(?:jarvis[, ]+)?(?:please\s+)?(?P<browser>google chrome|chrome|microsoft edge|ms edge|edge)\s+(?:open|visit|to|go to|navigate to|kholo)\s+(?P<url>https?://\S+)$",
        r"^(?:jarvis[, ]+)?(?:please\s+)?open\s+(?P<browser>google chrome|chrome|microsoft edge|ms edge|edge)\s+(?:and\s+)?(?:go to|navigate to|visit|open|to)\s+(?P<url>https?://\S+)$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        url = match.group("url")
        safe_url = validate_http_url(url)
        if safe_url is None:
            return None
        browser_value = (match.groupdict().get("browser") or "chrome").casefold()
        browser = "edge" if "edge" in browser_value or browser_value == "ms edge" else "chrome"
        return browser, safe_url
    return None


def open_url_in_browser(browser_name: str, url: str) -> LaunchResult:
    """Open one explicitly supplied HTTP(S) URL in the fixed Chrome/Edge executable."""
    browser = browser_name.strip().casefold()
    safe_url = validate_http_url(url)
    if browser not in {"chrome", "edge"}:
        return LaunchResult(False, browser_name, "Browser is not on the allow-list.")
    if safe_url is None:
        return LaunchResult(False, browser, "URL rejected; only a valid HTTP(S) URL without embedded credentials is allowed.")
    if os.name != "nt":
        return LaunchResult(False, browser, "Browser navigation is supported only on Windows.")
    executable = _find_executable(browser)
    if not executable or not os.path.isfile(executable):
        return LaunchResult(False, browser, f"{browser.title()} was not found on this PC.")
    try:
        subprocess.Popen([executable, safe_url], shell=False, close_fds=True)
    except OSError:
        return LaunchResult(False, browser, f"Windows could not open the URL in {browser.title()}.")
    return LaunchResult(
        True, browser,
        f"Windows accepted the request to open the supplied URL in {browser.title()}; page load and page contents are not verified.",
    )


def open_url_with_approval(browser_name: str, url: str, *, user_approved: bool) -> LaunchResult:
    """Open a validated URL only after an explicit per-request approval decision."""
    browser = browser_name.strip().casefold()
    if browser not in {"chrome", "edge"}:
        return LaunchResult(False, browser_name, "Browser is not on the allow-list.")
    safe_url = validate_http_url(url)
    if safe_url is None:
        return LaunchResult(False, browser, "URL rejected; only a valid HTTP(S) URL without embedded credentials is allowed.")
    registry = ActionRegistry()
    registry.register(ActionSpec(
        name="open_explicit_url",
        risk=RiskLevel.REVERSIBLE,
        description=f"Open an explicitly supplied URL in {browser.title()}",
        handler=lambda: open_url_in_browser(browser, safe_url),
    ))
    try:
        result = SafetyGate().execute("open_explicit_url", registry, user_approved=user_approved)
    except PermissionError:
        return LaunchResult(False, browser, "Navigation blocked: explicit user intent/approval is required.")
    return result


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
    parts = re.split(r"\s+(?:and\s+then|and|then|aur)\s+", text, flags=re.IGNORECASE)
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


def is_supported_notepad_text(value: object) -> bool:
    """Apply the same 2000 UTF-16-code-unit limit used by the Windows helper."""
    if not isinstance(value, str) or not value.strip() or len(value) > 2000 or "\\x00" in value:
        return False
    try:
        utf16_units = len(value.encode("utf-16-le", errors="strict")) // 2
    except UnicodeEncodeError:
        return False
    return utf16_units <= 2000


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
    captured = captured.strip()
    explicitly_quoted = (
        len(captured) >= 2
        and captured[0] == captured[-1]
        and captured[0] in {"'", '"'}
    )
    if explicitly_quoted:
        captured = captured[1:-1].strip()
    elif re.search(
        r"\b(?:then|and)\s+(?:open|launch|start|run|visit|navigate|click|delete|send|submit|type|write)\b",
        captured,
        flags=re.IGNORECASE,
    ):
        # Do not absorb a second apparent command into a typing payload. The
        # user can quote the intended literal text to disambiguate it.
        return None
    if not is_supported_notepad_text(captured):
        return None
    return captured
