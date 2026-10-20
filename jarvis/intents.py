"""Small deterministic intent parser; never executes actions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    argument: str = ""


_HELP = {"help", "/help", "commands", "/commands"}
_EXIT = {"exit", "quit", "/exit", "/quit"}
_ACTION_STARTS = ("open ", "launch ", "start ", "close ", "click ", "type ", "press ", "shutdown ", "restart ")


def parse_intent(text: str) -> Intent:
    """Route known commands and obvious action requests before ordinary chat."""
    normalized = text.strip()
    lowered = normalized.casefold()
    if not normalized:
        return Intent("empty")
    if lowered in _HELP:
        return Intent("help")
    if lowered in _EXIT:
        return Intent("exit")
    if lowered.startswith(_ACTION_STARTS):
        return Intent("action_unavailable", normalized)
    return Intent("chat", normalized)
