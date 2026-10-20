"""Double-click launcher for JARVIS v3 with safe startup diagnostics."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import sys
import traceback


PROJECT_DIR = Path(__file__).resolve().parent
# The application keeps its local SQLite databases beside the repository. Explorer
# shortcuts can supply an unrelated working directory, so normalize it here.
os.chdir(PROJECT_DIR)


def _redact_diagnostic(value: str) -> str:
    """Redact common credential forms before writing startup diagnostics."""
    value = re.sub(
        r"(?i)\b(api[_ -]?key|access[_ -]?token|token|password|passwd|secret)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        value,
    )
    value = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED_API_KEY]", value)
    value = re.sub(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED_TOKEN]", value)
    value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*\b", "Bearer [REDACTED]", value)
    return value[-12000:]


def _report_startup_failure(exc: BaseException) -> None:
    """Show a useful error even when started with pythonw.exe (no console)."""
    log_path = PROJECT_DIR / "jarvis-data" / "startup-error.log"
    saved = False
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        report = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        log_path.write_text(_redact_diagnostic(report), encoding="utf-8")
        saved = True
    except OSError:
        # Error reporting must not hide the original startup failure.
        pass

    if saved:
        message = (
            "JARVIS could not start. A redacted diagnostic log was saved here:\n\n"
            f"{log_path}\n\nReview the log before sharing it. You can also run "
            "JARVIS.bat --menu and choose diagnostics."
        )
    else:
        message = (
            f"JARVIS could not start ({type(exc).__name__}), and the diagnostic log "
            "could not be saved. Run JARVIS.bat --menu and choose diagnostics."
        )

    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, "JARVIS v3 startup error", 0x10)
            return
        except Exception:
            pass
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from jarvis.gui import main
        main()
    except Exception as exc:
        _report_startup_failure(exc)
