"""Gemini REST provider. API keys must be injected from secure storage."""

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from jarvis.providers.base import ChatRequest, ChatResponse, ProviderError, ProviderTimeout


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Gemini API key must be provided from secure storage.")
        if not model.strip() or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in model):
            raise ValueError("Invalid Gemini model name.")
        self._api_key = api_key.strip()
        self._model = model.strip()

    def generate(self, request: ChatRequest) -> ChatResponse:
        if request.timeout_seconds <= 0:
            raise ProviderTimeout("Timeout must be greater than zero.")
        # Google API expects the key in a header; avoid placing it in the URL.
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + quote(self._model, safe="") + ":generateContent"
        payload = json.dumps({"contents": [{"role": "user", "parts": [{"text": request.message}]}], "generationConfig": {"maxOutputTokens": 1024}}).encode("utf-8")
        http_request = Request(url, data=payload, headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key}, method="POST")
        try:
            with urlopen(http_request, timeout=request.timeout_seconds) as response:
                raw = response.read()
        except (socket.timeout, TimeoutError) as exc:
            raise ProviderTimeout("Gemini request timed out.") from exc
        except HTTPError as exc:
            # Do not include response bodies or credential-bearing request details.
            raise ProviderError(f"Gemini returned HTTP {exc.code}.") from exc
        except (URLError, OSError) as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (socket.timeout, TimeoutError)):
                raise ProviderTimeout("Gemini request timed out.") from exc
            raise ProviderError("Gemini service could not be reached.") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
            text = "".join(part["text"] for part in data["candidates"][0]["content"]["parts"] if isinstance(part.get("text"), str))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Gemini returned an invalid response.") from exc
        if not text.strip():
            raise ProviderError("Gemini returned an empty response.")
        return ChatResponse(text=text.strip(), provider=self.name)
