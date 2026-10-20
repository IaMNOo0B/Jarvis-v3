"""Small orchestration layer separating deterministic commands from AI providers."""

from jarvis.intents import parse_intent
from jarvis.providers.base import ChatProvider, ChatRequest, ProviderError


class ChatService:
    def __init__(self, provider: ChatProvider | None = None) -> None:
        self._provider = provider

    def respond(self, message: str, timeout_seconds: float = 30.0) -> str:
        intent = parse_intent(message)
        if intent.name == "empty":
            return "Please enter a message."
        if intent.name == "help":
            return "Available commands: /help, /exit. Desktop actions are not enabled yet."
        if intent.name == "exit":
            return "Goodbye, Sir."
        if self._provider is None:
            return "No AI provider is configured yet; no action was performed."
        try:
            response = self._provider.generate(
                ChatRequest(message=intent.argument, timeout_seconds=timeout_seconds)
            )
        except ProviderError:
            return "The AI provider failed; no action was performed. Please try again."
        if not response.text.strip():
            return "The AI provider returned an empty response; no action was performed."
        return response.text
