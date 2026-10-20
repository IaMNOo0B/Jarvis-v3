"""Safe default used until a real provider is configured."""

from jarvis.providers.base import ChatRequest, ChatResponse, ProviderError


class UnavailableProvider:
    name = "unconfigured"

    def generate(self, request: ChatRequest) -> ChatResponse:
        raise ProviderError("No AI provider is configured.")
