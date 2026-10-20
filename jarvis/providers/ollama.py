"""Local Ollama provider using only the Python standard library.

The endpoint is restricted to loopback so this provider cannot silently send
chat content to a remote host. No model is downloaded or started automatically.
"""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from jarvis.providers.base import ChatRequest, ChatResponse, ProviderError, ProviderTimeout


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        model: str = "qwen2.5:7b-instruct-q4_K_M",
        base_url: str = "http://127.0.0.1:11434",
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Ollama endpoint must use HTTP on loopback only.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Ollama endpoint must not contain credentials or query parameters.")
        if not model.strip():
            raise ValueError("Ollama model name must not be empty.")
        self._model = model.strip()
        self._endpoint = base_url.rstrip("/") + "/api/chat"

    def generate(self, request: ChatRequest) -> ChatResponse:
        if request.timeout_seconds <= 0:
            raise ProviderTimeout("Timeout must be greater than zero.")
        payload = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": request.message}],
            "stream": False,
        }).encode("utf-8")
        http_request = Request(
            self._endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw = response.read()
        except (socket.timeout, TimeoutError) as exc:
            raise ProviderTimeout("Ollama request timed out.") from exc
        except HTTPError as exc:
            # Do not echo response bodies; they may contain private prompt data.
            if exc.code == 404:
                raise ProviderError("Ollama model or endpoint was not found.") from exc
            raise ProviderError(f"Ollama returned HTTP {exc.code}.") from exc
        except (URLError, OSError) as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (socket.timeout, TimeoutError)):
                raise ProviderTimeout("Ollama request timed out.") from exc
            raise ProviderError("Ollama is unavailable on the local machine.") from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
            text = decoded["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ProviderError("Ollama returned an invalid response.") from exc
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("Ollama returned an empty response.")
        return ChatResponse(text=text.strip(), provider=self.name)
