"""Small deterministic intent parser; never executes actions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    name: str
    argument: str = ""


_HELP = {"help", "/help", "commands", "/commands"}
_EXIT = {"exit", "quit", "/exit", "/quit"}


def parse_intent(text: str) -> Intent:
    """Parse only safe, known intents; leave everything else as ordinary chat."""
    normalized = text.strip()
    lowered = normalized.casefold()
    if not normalized:
        return Intent("empty")
    if lowered in _HELP:
        return Intent("help")
    if lowered in _EXIT:
        return Intent("exit")
    if lowered.startswith("/ "):
        return Intent("chat", normalized)
    return Intent("chat", normalized)
