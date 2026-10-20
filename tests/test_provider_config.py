import unittest

from jarvis.provider_config import ProviderConfig, build_provider
from jarvis.providers.ollama import OllamaProvider


class ProviderConfigTests(unittest.TestCase):
    def test_default_is_configured_local_model(self):
        provider = build_provider()
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider._model, "qwen2.5:7b-instruct-q4_K_M")

    def test_custom_local_model_is_respected(self):
        provider = build_provider(ProviderConfig(model="custom-local-model"))
        self.assertEqual(provider._model, "custom-local-model")

    def test_unknown_provider_fails_explicitly(self):
        with self.assertRaises(ValueError):
            build_provider(ProviderConfig(name="mystery"))

    def test_cloud_provider_does_not_silently_fallback(self):
        with self.assertRaises(ValueError):
            build_provider(ProviderConfig(name="gemini"))


if __name__ == "__main__":
    unittest.main()
