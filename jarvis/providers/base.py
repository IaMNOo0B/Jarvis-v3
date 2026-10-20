"""Provider contract with bounded, explicit outcomes."""

from dataclasses import dataclass
from typing import Protocol


class ProviderError(RuntimeError):
    """A provider could not produce a response."""


class ProviderTimeout(ProviderError):
    """A provider exceeded its configured time budget."""


@dataclass(frozen=True)
class ChatRequest:
    message: str
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class ChatResponse:
    text: str
    provider: str


class ChatProvider(Protocol):
    name: str

    def generate(self, request: ChatRequest) -> ChatResponse:
        """Generate one response or raise ProviderError; never fake success."""
