"""SQLite connection scopes that commit/rollback and always close the handle.

The sqlite3 connection context manager handles transactions but does not close the
connection. Explicit close is important on Windows, where an open database file
cannot be removed during temporary-directory cleanup or safely replaced on update.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3


@contextmanager
def sqlite_connection(
    database_path: str | Path,
    *,
    timeout: float = 5.0,
    foreign_keys: bool = False,
) -> Iterator[sqlite3.Connection]:
    """Yield a row-aware connection with transaction handling and deterministic close."""
    connection = sqlite3.connect(str(database_path), timeout=timeout)
    connection.row_factory = sqlite3.Row
    try:
        if foreign_keys:
            connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()
