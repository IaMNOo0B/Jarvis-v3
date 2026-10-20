import json
import unittest
from unittest.mock import patch

from jarvis.providers.base import ChatRequest, ProviderError
from jarvis.providers.gemini import GeminiProvider


class FakeResponse:
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


class GeminiProviderTests(unittest.TestCase):
    def test_key_is_sent_in_header_and_response_parsed(self):
        body = json.dumps({"candidates": [{"content": {"parts": [{"text": "Hello Sir"}]}}]}).encode()
        with patch("jarvis.providers.gemini.urlopen", return_value=FakeResponse(body)) as mocked:
            result = GeminiProvider("example-secret").generate(ChatRequest("hi", timeout_seconds=7))
        self.assertEqual(result.text, "Hello Sir")
        req = mocked.call_args.args[0]
        self.assertEqual(req.get_header("X-goog-api-key"), "example-secret")
        self.assertNotIn("example-secret", req.full_url)
        self.assertEqual(mocked.call_args.kwargs["timeout"], 7)

    def test_missing_key_rejected(self):
        with self.assertRaises(ValueError):
            GeminiProvider("")

    def test_invalid_response_raises_provider_error(self):
        with patch("jarvis.providers.gemini.urlopen", return_value=FakeResponse(b"{}")):
            with self.assertRaises(ProviderError):
                GeminiProvider("example-secret").generate(ChatRequest("hi"))


if __name__ == "__main__": unittest.main()
