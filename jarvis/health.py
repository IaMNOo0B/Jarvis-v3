"""Provider health checks that perform a real bounded generation request."""

from dataclasses import dataclass

from jarvis.providers.base import ChatProvider, ProviderError, ChatRequest


@dataclass(frozen=True)
class HealthResult:
    healthy: bool
    provider: str
    detail: str


def check_provider(provider: ChatProvider, timeout_seconds: float = 15.0) -> HealthResult:
    """Run a tiny real request; construction alone is not considered healthy."""
    if timeout_seconds <= 0:
        return HealthResult(False, provider.name, "Health-check timeout must be positive.")
    try:
        result = provider.generate(ChatRequest(
            message="Reply with exactly: OK",
            timeout_seconds=timeout_seconds,
        ))
    except ProviderError:
        return HealthResult(False, provider.name, "Provider did not complete a successful generation request.")
    except Exception:
        # Health checks report a generic failure and never expose keys or tracebacks.
        return HealthResult(False, provider.name, "Provider health check failed unexpectedly.")
    if not result.text.strip():
        return HealthResult(False, provider.name, "Provider returned an empty response.")
    return HealthResult(True, result.provider, "Real generation request succeeded.")
