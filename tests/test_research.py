import unittest
from unittest.mock import patch

from jarvis.research import PublicResearch, ResearchError, ResearchSource, _query_text


class PublicResearchTests(unittest.TestCase):
    def test_rejects_empty_long_and_secret_queries(self):
        for query in ("", "x" * 241, "api_key=secret please search this"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                _query_text(query)

    def test_wikipedia_parses_only_wikipedia_https_urls(self):
        payload = ["cats", ["Cat", "Bad"], ["A feline", "bad"], ["https://en.wikipedia.org/wiki/Cat", "http://evil.test/"]]
        with patch("jarvis.research._get_json", return_value=payload):
            report = PublicResearch().wikipedia("cats")
        self.assertEqual(len(report.sources), 1)
        self.assertEqual(report.sources[0].title, "Cat")
        self.assertIn("not independently verified", report.warnings[0])

    def test_github_result_keeps_provenance_and_metadata(self):
        payload = {"items": [
            {"full_name": "org/project", "html_url": "https://github.com/org/project",
             "description": "Example", "stargazers_count": 42, "language": "Python"},
            {"full_name": "evil", "html_url": "https://evil.test/repo", "description": "bad"}
        ]}
        with patch("jarvis.research._get_json", return_value=payload):
            report = PublicResearch().github_repositories("agent framework")
        self.assertEqual(len(report.sources), 1)
        self.assertIn("stars: 42", report.sources[0].snippet)
        self.assertEqual(report.sources[0].url, "https://github.com/org/project")

    def test_rejects_unknown_research_source(self):
        with self.assertRaises(ValueError):
            PublicResearch().search("arbitrary-url", "anything")

    def test_api_failure_is_not_fabricated(self):
        with patch("jarvis.research._get_json", side_effect=ResearchError("offline")):
            with self.assertRaises(ResearchError):
                PublicResearch().wikipedia("jarvis")


if __name__ == "__main__":
    unittest.main()
