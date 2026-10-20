""""Explicit provider construction without implicit network or secret fallbacks."""

from dataclasses import dataclass

from jarvis.credentials import CredentialStore
from jarvis.providers.base import ChatProvider
from jarvis.providers.gemini import GeminiProvider
from jarvis.providers.ollama import OllamaProvider


OLLAMA_DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class ProviderConfig:
    """Safe defaults: local Ollama only, with a fixed loopback endpoint."""
    name: str = "ollama"
    model: str | None = None


def build_provider(config: ProviderConfig | None = None, *, credentials: CredentialStore | None = None) -> ChatProvider:
    """Construct a provider; cloud is used only when explicitly selected."""
    selected = config or ProviderConfig()
    name = selected.name.strip().casefold()
    if name == "ollama":
        return OllamaProvider(model=selected.model or OLLAMA_DEFAULT_MODEL)
    if name == "gemini":
        if credentials is None:
            raise ValueError("Gemini requires Windows Credential Manager credentials.")
        api_key = credentials.get_secret("gemini.api_key")
        if not api_key:
            raise ValueError("Gemini API key is not saved in secure storage.")
        model = selected.model or GEMINI_DEFAULT_MODEL
        return GeminiProvider(api_key=api_key, model=model)
    if name == "openrouter":
        raise NotImplementedError("OpenRouter is not implemented yet; no request was sent.")
    raise ValueError("Unsupported provider. Available providers: ollama, gemini.")
"