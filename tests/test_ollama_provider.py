import json
import unittest
from unittest.mock import patch

from jarvis.providers.base import ChatRequest, ProviderError, ProviderTimeout
from jarvis.providers.ollama import OllamaProvider


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class OllamaProviderTests(unittest.TestCase):
    def test_remote_endpoint_is_rejected(self):
        with self.assertRaises(ValueError):
            OllamaProvider(base_url="https://example.com")

    def test_default_model_is_requested_without_streaming(self):
        provider = OllamaProvider()
        body = json.dumps({"message": {"content": "Hello Sir"}}).encode()
        with patch("jarvis.providers.ollama.urlopen", return_value=FakeResponse(body)) as mocked:
            result = provider.generate(ChatRequest("hello", timeout_seconds=9))
        self.assertEqual(result.text, "Hello Sir")
        self.assertEqual(result.provider, "ollama")
        self.assertEqual(mocked.call_args.kwargs["timeout"], 9)
        sent = json.loads(mocked.call_args.args[0].data.decode())
        self.assertEqual(sent["model"], "qwen2.5:7b-instruct-q4_K_M")
        self.assertFalse(sent["stream"])

    def test_timeout_is_rejected(self):
        with self.assertRaises(ProviderTimeout):
            OllamaProvider().generate(ChatRequest("hi", timeout_seconds=0))

    def test_invalid_response_is_provider_error(self):
        with patch("jarvis.providers.ollama.urlopen", return_value=FakeResponse(b"{}")):
            with self.assertRaises(ProviderError):
                OllamaProvider().generate(ChatRequest("hello"))

    def test_credentials_in_endpoint_are_rejected(self):
        with self.assertRaises(ValueError):
            OllamaProvider(base_url="http://user:pass@localhost:11434")


if __name__ == "__main__":
    unittest.main()
