"""Bounded public-source research for explicit research requests.

Only fixed public APIs are contacted; arbitrary URLs, credentials, and page
instructions are never executed. Network access is explicit and source URLs
are preserved with fetched snippets.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


@dataclass(frozen=True)
class ResearchSource:
    title: str
    url: str
    snippet: str
    source_type: str


@dataclass(frozen=True)
class ResearchReport:
    query: str
    sources: tuple[ResearchSource, ...]
    warnings: tuple[str, ...] = ()


class ResearchError(RuntimeError):
    """Raised when bounded public research cannot return usable evidence."""


def _query_text(value: str) -> str:
    value = " ".join(value.split())
    if not value or len(value) > 240:
        raise ValueError("Research query must contain 1–240 characters.")
    if re.search(r"(?i)(api[_ -]?key|password|secret|token)\s*[:=]", value):
        raise ValueError("Do not include credentials or secrets in a research query.")
    return value


def _get_json(url: str, *, timeout_seconds: float = 8.0) -> object:
    request = Request(
        url,
        headers={"User-Agent": "JARVIS-V3-Research/0.1 (public-source lookup)", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=max(1.0, min(timeout_seconds, 10.0))) as response:
            if response.status != 200:
                raise ResearchError(f"Public source returned HTTP {response.status}.")
            body = response.read(512_001)
            if len(body) > 512_000:
                raise ResearchError("Public source response exceeded the size limit.")
            return json.loads(body.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResearchError("Public research source is unavailable or returned invalid data.") from exc


class PublicResearch:
    """Search Wikipedia and GitHub public metadata using fixed HTTPS endpoints."""

    def __init__(self, *, timeout_seconds: float = 8.0, max_results: int = 5) -> None:
        if timeout_seconds <= 0 or max_results < 1 or max_results > 5:
            raise ValueError("Timeout must be positive and result limit must be 1–5.")
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results

    def wikipedia(self, query: str) -> ResearchReport:
        query = _query_text(query)
        params = urlencode({
            "action": "opensearch", "search": query, "limit": self.max_results,
            "namespace": 0, "format": "json",
        })
        data = _get_json("https://en.wikipedia.org/w/api.php?" + params, timeout_seconds=self.timeout_seconds)
        if not isinstance(data, list) or len(data) < 4:
            raise ResearchError("Wikipedia returned an unexpected response.")
        titles, descriptions, urls = data[1], data[2], data[3]
        sources = tuple(
            ResearchSource(
                title=str(title)[:300],
                url=str(url)[:1000],
                snippet=str(descriptions[i] if i < len(descriptions) else "")[:800],
                source_type="Wikipedia search result",
            )
            for i, (title, url) in enumerate(zip(titles, urls))
            if isinstance(title, str) and isinstance(url, str) and url.startswith("https://en.wikipedia.org/")
        )
        return ResearchReport(query, sources, ("Search snippets are leads, not independently verified facts.",))

    def github_repositories(self, query: str) -> ResearchReport:
        query = _query_text(query)
        params = urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": self.max_results})
        data = _get_json("https://api.github.com/search/repositories?" + params, timeout_seconds=self.timeout_seconds)
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ResearchError("GitHub returned an unexpected response.")
        sources = []
        for item in data["items"][:self.max_results]:
            if not isinstance(item, dict):
                continue
            url = item.get("html_url")
            name = item.get("full_name")
            if not isinstance(url, str) or not url.startswith("https://github.com/") or not isinstance(name, str):
                continue
            description = item.get("description")
            stars = item.get("stargazers_count")
            language = item.get("language")
            snippet = str(description or "No description provided.")[:600]
            metadata = []
            if isinstance(language, str) and language:
                metadata.append("language: " + language[:60])
            if isinstance(stars, int):
                metadata.append(f"stars: {stars}")
            if metadata:
                snippet += " (" + ", ".join(metadata) + ")"
            sources.append(ResearchSource(name[:300], url[:1000], snippet, "GitHub repository metadata"))
        return ResearchReport(query, tuple(sources), (
            "Repository metadata is not a code audit; inspect licenses, security, maintenance and code before reuse.",
        ))

    def search(self, source: str, query: str) -> ResearchReport:
        source = source.strip().casefold()
        if source in {"wikipedia", "wiki"}:
            return self.wikipedia(query)
        if source in {"github", "git hub"}:
            return self.github_repositories(query)
        raise ValueError("Research source must be Wikipedia or GitHub.")
