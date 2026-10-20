import tempfile
import unittest
from pathlib import Path

from jarvis.knowledge_base import KnowledgeBase


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs" / "research-ledger.md").write_text(
            "# Self healing\n\nSelf-healing means diagnose failures, test repairs, and rollback regressions.\n",
            encoding="utf-8",
        )
        (self.root / "docs" / "unrelated.md").write_text(
            "# Cooking\n\nPasta water should be salted.\n", encoding="utf-8"
        )
        (self.root / "secrets").mkdir()
        (self.root / "secrets" / "keys.txt").write_text(
            "self healing api key secret should not be indexed", encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_search_returns_relevant_source_and_bounded_excerpt(self):
        kb = KnowledgeBase([self.root / "docs"])
        hits = kb.search("self healing repairs", limit=2)
        self.assertTrue(hits)
        self.assertIn("research-ledger.md", hits[0].source)
        self.assertIn("rollback", hits[0].excerpt)
        self.assertLessEqual(len(hits[0].excerpt), 1200)

    def test_context_contains_provenance_and_untrusted_data_warning(self):
        kb = KnowledgeBase([self.root / "docs"])
        context = kb.context_for("self healing", limit=2)
        self.assertIn("untrusted data", context)
        self.assertIn("research-ledger.md", context)
        self.assertIn("<reference>", context)

    def test_no_match_returns_empty_context(self):
        kb = KnowledgeBase([self.root / "docs"])
        self.assertEqual(kb.context_for("spaceship quantum banana"), "")

    def test_missing_root_and_nonpositive_limit_are_safe(self):
        kb = KnowledgeBase([self.root / "does-not-exist"])
        self.assertEqual(kb.search("self healing"), [])
        self.assertEqual(kb.search("self healing", limit=0), [])

    def test_secret_and_data_directories_are_excluded(self):
        kb = KnowledgeBase([self.root])
        hits = kb.search("self healing api key secret")
        self.assertFalse(any("secrets" in hit.source for hit in hits))


if __name__ == "__main__":
    unittest.main()
