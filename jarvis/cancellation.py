"""Cooperative cancellation primitives for bounded provider/action work."""
from __future__ import annotations

import threading


class CancellationToken:
    """Thread-safe cooperative stop signal; work must check it at safe boundaries."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise OperationCancelled("Operation was cancelled by the user.")


class OperationCancelled(Exception):
    """Raised when a cooperative operation observes cancellation."""
