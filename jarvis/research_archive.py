"""Local SQLite archive for explicit public research results and provenance."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from jarvis.research import ResearchReport


class ResearchArchive:
    """Store only explicit research results; no page content is executed."""

    def __init__(self, database_path: str | Path = "jarvis-data/research.sqlite3") -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS research_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                warnings TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS research_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                snippet TEXT NOT NULL,
                source_type TEXT NOT NULL
            )""")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database_path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def save(self, report: ResearchReport) -> int:
        if not report.query.strip() or len(report.query) > 240:
            raise ValueError("Research report query is invalid.")
        saved_at = datetime.now(timezone.utc).isoformat()
        warnings = "\n".join(report.warnings)[:3000]
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO research_runs(query, saved_at, warnings) VALUES (?, ?, ?)",
                (report.query, saved_at, warnings),
            )
            run_id = int(cursor.lastrowid)
            for source in report.sources[:5]:
                if not source.url.startswith("https://") or len(source.url) > 1000:
                    continue
                db.execute(
                    "INSERT INTO research_sources(run_id, title, url, snippet, source_type) VALUES (?, ?, ?, ?, ?)",
                    (run_id, source.title[:300], source.url, source.snippet[:800], source.source_type[:100]),
                )
        return run_id

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100.")
        with self._connect() as db:
            runs = db.execute(
                "SELECT * FROM research_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            results = []
            for run in runs:
                sources = db.execute(
                    "SELECT title, url, snippet, source_type FROM research_sources WHERE run_id=? ORDER BY id",
                    (run["id"],),
                ).fetchall()
                results.append({
                    "id": run["id"],
                    "query": run["query"],
                    "saved_at": run["saved_at"],
                    "warnings": run["warnings"],
                    "sources": [dict(source) for source in sources],
                })
        return results
