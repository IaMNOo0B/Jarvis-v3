import tempfile
import unittest
from pathlib import Path

from jarvis.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_memory_keeps_source_and_persists(self):
        item = self.store.remember("prefers concise answers", source="explicit_user_request")
        self.assertEqual(item.source, "explicit_user_request")
        self.assertEqual(MemoryStore(Path(self.temp.name) / "memory.sqlite3").list()[0], item)

    def test_rejects_missing_provenance_and_empty_content(self):
        with self.assertRaises(ValueError):
            self.store.remember("fact", source="")
        with self.assertRaises(ValueError):
            self.store.remember(" ", source="user")

    def test_forget_one_and_confirm_forget_all(self):
        one = self.store.remember("first", source="test")
        self.assertTrue(self.store.forget(one.memory_id))
        self.assertFalse(self.store.forget(one.memory_id))
        self.store.remember("second", source="test")
        with self.assertRaises(PermissionError):
            self.store.forget_all()
        self.assertEqual(self.store.forget_all(confirmed=True), 1)
        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()
