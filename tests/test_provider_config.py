import unittest

from jarvis.provider_config import ProviderConfig, build_provider
from jarvis.providers.gemini import GeminiProvider
from jarvis.providers.ollama import OllamaProvider


class FakeCredentials:
    def __init__(self, secret): self.secret = secret
    def get_secret(self, name):
        if name != "gemini.api_key": raise AssertionError("Unexpected credential name")
        return self.secret


class ProviderConfigTests(unittest.TestCase):
    def test_default_is_configured_local_model(self):
        provider = build_provider()
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider._model, "qwen2.5:7b-instruct-q4_K_M")

    def test_custom_local_model_is_respected(self):
        provider = build_provider(ProviderConfig(model="custom-local-model"))
        self.assertEqual(provider._model, "custom-local-model")

    def test_gemini_uses_gemini_default_model(self):
        provider = build_provider(ProviderConfig(name="gemini"), credentials=FakeCredentials("test-only-key"))
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider._model, "gemini-2.5-flash")

    def test_gemini_custom_model_is_respected(self):
        provider = build_provider(ProviderConfig(name="gemini", model="gemini-test-model"), credentials=FakeCredentials("test-only-key"))
        self.assertEqual(provider._model, "gemini-test-model")

    def test_gemini_missing_key_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "not saved in secure storage"):
            build_provider(ProviderConfig(name="gemini"), credentials=FakeCredentials(None))

    def test_cloud_provider_does_not_silently_fallback(self):
        with self.assertRaisesRegex(ValueError, "Windows Credential Manager"):
            build_provider(ProviderConfig(name="gemini"))

    def test_unknown_provider_fails_explicitly(self):
        with self.assertRaises(ValueError):
            build_provider(ProviderConfig(name="mystery"))


if __name__ == "__main__":
    unittest.main()
