"""Explicit provider construction without implicit network or secret fallbacks."""

from dataclasses import dataclass

from jarvis.credentials import CredentialStore
from jarvis.providers.base import ChatProvider
from jarvis.providers.gemini import GeminiProvider
from jarvis.providers.ollama import OllamaProvider


@dataclass(frozen=True)
class ProviderConfig:
    """Safe defaults: local Ollama only, with a fixed loopback endpoint."""
    name: str = "ollama"
    model: str = "qwen2.5:7b-instruct-q4_K_M"


def build_provider(config: ProviderConfig | None = None, *, credentials: CredentialStore | None = None) -> ChatProvider:
    """Construct a provider; cloud is used only when explicitly selected."""
    selected = config or ProviderConfig()
    name = selected.name.strip().casefold()
    if name == "ollama":
        return OllamaProvider(model=selected.model)
    if name == "gemini":
        if credentials is None:
            raise ValueError("Gemini requires Windows Credential Manager credentials.")
        api_key = credentials.get_secret("gemini.api_key")
        if not api_key:
            raise ValueError("Gemini API key is not saved in secure storage.")
        return GeminiProvider(api_key=api_key, model=selected.model or "gemini-2.5-flash")
    if name == "openrouter":
        raise NotImplementedError("OpenRouter is not implemented yet; no request was sent.")
    raise ValueError("Unsupported provider. Available providers: ollama, gemini.")
