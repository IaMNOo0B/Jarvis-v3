"""Bounded, local activity journal with conservative secret redaction."""
from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|secret)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)\b(AIza[0-9A-Za-z_-]{20,}|AQ\.[0-9A-Za-z._-]{20,})\b"),
    re.compile(r"(?i)\b(sk-or-v1-[0-9A-Za-z_-]{20,})\b"),
)


def redact(value: str) -> str:
    """Remove common credential patterns before content enters the activity journal."""
    result = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 3:
            result = pattern.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", result)
        else:
            result = pattern.sub("[REDACTED]", result)
    return result


class ActivityJournal:
    """Bounded append-only JSONL activity log; no chat transcript by default."""

    def __init__(self, path: str | Path = "jarvis-data/activity.jsonl", *, max_entries: int = 1000) -> None:
        if not 1 <= max_entries <= 10000:
            raise ValueError("max_entries must be between 1 and 10000.")
        self.path = Path(path)
        self.max_entries = max_entries
        self._lock = Lock()
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._memory: deque[dict[str, Any]] = deque(maxlen=max_entries)

    def record(self, event: str, status: str, *, detail: str = "") -> None:
        clean_event, clean_status, clean_detail = redact(event)[:100], redact(status)[:40], redact(detail)[:500]
        if not clean_event or not clean_status:
            raise ValueError("Activity event and status are required.")
        row = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": clean_event,
            "status": clean_status,
            "detail": clean_detail,
        }
        with self._lock:
            self._memory.append(row)
            if str(self.path) == ":memory:":
                return
            existing = []
            if self.path.exists():
                try:
                    with self.path.open("r", encoding="utf-8") as stream:
                        for line in stream:
                            try:
                                existing.append(json.loads(line))
                            except (json.JSONDecodeError, TypeError):
                                continue
                except OSError:
                    existing = []
            existing = (existing + [row])[-self.max_entries:]
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                with temp.open("w", encoding="utf-8", newline="\n") as stream:
                    for item in existing:
                        stream.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
                temp.replace(self.path)
            finally:
                if temp.exists():
                    temp.unlink()

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= self.max_entries:
            raise ValueError("limit must be between 1 and max_entries.")
        with self._lock:
            if str(self.path) == ":memory:":
                return list(self._memory)[-limit:]
            if not self.path.exists():
                return []
            try:
                with self.path.open("r", encoding="utf-8") as stream:
                    rows = [json.loads(line) for line in stream if line.strip()]
            except (OSError, json.JSONDecodeError):
                return []
            return rows[-limit:]
