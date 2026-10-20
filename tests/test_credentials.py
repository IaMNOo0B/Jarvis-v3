import unittest

from jarvis.credentials import CredentialStore, CredentialStoreError


class MemoryBackend:
    def __init__(self):
        self.items = {}

    def write(self, target, secret):
        self.items[target] = secret

    def read(self, target):
        return self.items.get(target)

    def delete(self, target):
        self.items.pop(target, None)


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryBackend()
        self.store = CredentialStore(backend=self.backend)

    def test_round_trip_uses_jarvis_namespace(self):
        self.store.set_secret("Ollama-Token", "not-a-real-key")
        self.assertEqual(self.store.get_secret("ollama-token"), "not-a-real-key")
        self.assertIn("JARVIS.v3/ollama-token", self.backend.items)

    def test_missing_secret_returns_none(self):
        self.assertIsNone(self.store.get_secret("gemini"))

    def test_delete_secret(self):
        self.store.set_secret("gemini", "example")
        self.store.delete_secret("gemini")
        self.assertIsNone(self.store.get_secret("gemini"))

    def test_empty_secret_rejected(self):
        with self.assertRaises(ValueError):
            self.store.set_secret("gemini", "")

    def test_invalid_name_rejected(self):
        with self.assertRaises(ValueError):
            self.store.get_secret("../secrets")


if __name__ == "__main__":
    unittest.main()
