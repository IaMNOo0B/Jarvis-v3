"""Allow-listed Windows app launching; no shell commands or arbitrary paths."""

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchResult:
    success: bool
    app: str
    detail: str


def launch_allowlisted_app(app_name: str) -> LaunchResult:
    """Launch only known apps with argument arrays; caller must obtain approval first."""
    app = app_name.strip().casefold()
    if app == "notepad":
        executable = shutil.which("notepad.exe") or (r"C:\Windows\System32\notepad.exe" if os.name == "nt" else None)
    elif app == "chrome":
        executable = shutil.which("chrome.exe")
        if not executable and os.name == "nt":
            candidates = (
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            )
            executable = next((path for path in candidates if path and os.path.isfile(path)), None)
    else:
        return LaunchResult(False, app_name, "App is not on the allow-list.")
    if os.name != "nt":
        return LaunchResult(False, app, "Desktop launching is supported only on Windows.")
    if not executable or not os.path.isfile(executable):
        return LaunchResult(False, app, f"{app.title()} was not found on this PC.")
    try:
        subprocess.Popen([executable], shell=False, close_fds=True)
    except OSError:
        return LaunchResult(False, app, f"Windows could not start {app.title()}.")
    return LaunchResult(True, app, f"Windows accepted the launch request for {app.title()}. App visibility has not been verified.")
