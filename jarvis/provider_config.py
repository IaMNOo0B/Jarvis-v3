"""Explicit provider construction without implicit network or secret fallbacks."""

from dataclasses import dataclass

from jarvis.credentials import CredentialStore
from jarvis.providers.base import ChatProvider
from jarvis.providers.ollama import OllamaProvider


@dataclass(frozen=True)
class ProviderConfig:
    """Safe defaults: local Ollama only, with a fixed loopback endpoint."""
    name: str = "ollama"
    model: str = "qwen2.5:7b-instruct-q4_K_M"


def build_provider(config: ProviderConfig | None = None, *, credentials: CredentialStore | None = None) -> ChatProvider:
    """Construct a supported provider; never silently falls back to cloud.

    `credentials` is accepted for the future keyed-cloud providers but is not
    read for Ollama. Unsupported provider names fail explicitly.
    """
    selected = config or ProviderConfig()
    name = selected.name.strip().casefold()
    if name == "ollama":
        return OllamaProvider(model=selected.model)
    if name in {"gemini", "openrouter"}:
        if credentials is None:
            raise ValueError("Cloud provider selection requires a secure credential store.")
        raise NotImplementedError("This cloud provider is not implemented yet; no request was sent.")
    raise ValueError("Unsupported provider. Available provider: ollama.")
