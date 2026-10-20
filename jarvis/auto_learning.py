"""Automatic, evidence-labelled task reflection for the conversational loop.

Records interactions without requiring slash commands. This is deliberately
not autonomous code execution or proof that a user's real-world goal succeeded.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from jarvis.learning import Episode, LearningStore

Outcome = Literal["response_generated", "action_accepted", "action_verified", "action_failed", "action_partial", "action_unknown", "provider_failed"]


def redact_task(text: str) -> str:
    """Reduce obvious credential leakage in the automatically stored task label."""
    text = re.sub(r"(?i)\b(api[_ -]?key|token|password|passwd|secret)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
    text = re.sub(r"\bAIza[0-9A-Za-z_-]{20,}\b", "[REDACTED_API_KEY]", text)
    text = re.sub(r"\bAQ\.[0-9A-Za-z._-]{30,}", "[REDACTED_API_KEY]", text)
    text = re.sub(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "[REDACTED_TOKEN]", text)
    return text[:1000]


@dataclass(frozen=True)
class TaskReflection:
    episode: Episode
    outcome: Outcome
    confidence: str
    note: str


class AutomaticLearning:
    """Record each completed interaction and label only what the app can verify."""

    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def reflect(
        self,
        task: str,
        *,
        outcome: Outcome,
        evidence: str = "",
    ) -> TaskReflection:
        allowed = {
            "response_generated",
            "action_accepted",
            "action_verified",
            "action_failed",
            "action_partial",
            "action_unknown",
            "provider_failed",
        }
        if outcome not in allowed:
            raise ValueError("Unknown evidence-based outcome.")
        task = task.strip()
        if not task:
            raise ValueError("Task must not be empty.")
        labels = {
            "response_generated": ("low", "A response was generated; user-goal completion is unverified."),
            "action_accepted": ("low", "The OS accepted the launch request; app visibility is unverified."),
            "action_verified": ("high", "The specific UI postcondition was read back exactly; broader user-goal completion is not implied."),
            "action_partial": ("medium", "A multi-step action partially ran; inspect the desktop before retrying."),
            "action_unknown": ("low", "A desktop side effect may have occurred; inspect state before retrying."),
            "action_failed": ("high", "The action adapter reported failure."),
            "provider_failed": ("high", "The provider did not produce a usable response."),
        }
        confidence, note = labels[outcome]
        combined_evidence = f"Automatic reflection: {note}"
        if evidence.strip():
            combined_evidence += f" Evidence: {evidence.strip()}"
        episode = self.store.record_episode(redact_task(task), outcome, evidence=combined_evidence[:4000])
        return TaskReflection(episode, outcome, confidence, note)
