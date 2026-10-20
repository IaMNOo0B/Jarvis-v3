import tempfile
import unittest
from pathlib import Path

from jarvis.research import ResearchReport, ResearchSource
from jarvis.research_archive import ResearchArchive


class ResearchArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.archive = ResearchArchive(Path(self.temp.name) / "research.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_saves_source_provenance_and_returns_recent_runs(self):
        report = ResearchReport(
            "agent framework",
            (ResearchSource("Project", "https://github.com/org/project", "Example", "GitHub metadata"),),
            ("Not a code audit.",),
        )
        run_id = self.archive.save(report)
        saved = self.archive.recent()[0]
        self.assertEqual(saved["id"], run_id)
        self.assertEqual(saved["query"], "agent framework")
        self.assertEqual(saved["sources"][0]["url"], "https://github.com/org/project")
        self.assertIn("Not a code audit.", saved["warnings"])

    def test_limits_are_bounded(self):
        with self.assertRaises(ValueError):
            self.archive.recent(101)
        with self.assertRaises(ValueError):
            self.archive.save(ResearchReport("", ()))

    def test_rejects_non_https_sources(self):
        report = ResearchReport(
            "test", (ResearchSource("Bad", "file:///secret", "no", "bad"),)
        )
        self.archive.save(report)
        self.assertEqual(self.archive.recent()[0]["sources"], [])


if __name__ == "__main__":
    unittest.main()
