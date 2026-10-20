"""Manual Windows smoke test for the fixed Notepad UI Automation adapter.

Run from the repository root with:
    python scripts/smoke_test_notepad_uia.py

The script never launches apps, saves files, deletes files, or replaces existing text.
It types one harmless line only into a detected blank Notepad document after an
explicit console confirmation, then asks the adapter to read the text back exactly.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jarvis.desktop_automation import (  # noqa: E402
    AppRegistry,
    PowerShellUIAutomationBackend,
    UIActionRequest,
    execute_ui_action,
)


TEST_TEXT = "JARVIS UIA smoke test: exact read-back verified."


def main() -> int:
    print("JARVIS V3 — Notepad UI Automation smoke test")
    if os.name != "nt":
        print("NOT RUN: this test requires a real Windows desktop.", file=sys.stderr)
        return 2

    backend = PowerShellUIAutomationBackend()
    if not backend.available:
        print(
            "NOT RUN: Windows PowerShell or the fixed UI Automation helper is unavailable.",
            file=sys.stderr,
        )
        return 2

    print()
    print("Before continuing:")
    print("  1. Open exactly one blank Notepad document.")
    print("  2. Make sure it contains no text you need to keep.")
    print("  3. Leave Notepad visible; this script will not launch it.")
    print()
    print("The script will type one test line, verify an exact read-back, and will not save the document.")
    try:
        confirmation = input("Type RUN to perform the desktop test: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("Cancelled; no desktop action was attempted.")
        return 0
    if confirmation != "RUN":
        print("Cancelled; no desktop action was attempted.")
        return 0

    request = UIActionRequest(
        app_name="notepad",
        action="type_text",
        target_name="blank document",
        text=TEST_TEXT,
    )
    result = execute_ui_action(
        request,
        registry=AppRegistry(),
        backend=backend,
        user_approved=True,
    )
    print()
    print(f"Result: {result.status}")
    print(result.detail)
    if result.success:
        print("PASS: the helper read back the exact test text. The document remains unsaved.")
        return 0
    if result.status in {"adapter_error", "verification_failed", "action_failed"}:
        print("The outcome may be partial. Inspect Notepad before running the test again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
