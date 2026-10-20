import sqlite3
import tempfile
import unittest
from pathlib import Path

from jarvis.sqlite_utils import sqlite_connection


class SQLiteConnectionScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "scope.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_connection_is_closed_after_successful_transaction(self):
        with sqlite_connection(self.database) as db:
            db.execute("CREATE TABLE sample (value TEXT NOT NULL)")
            db.execute("INSERT INTO sample(value) VALUES (?)", ("saved",))
            connection = db

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

        with sqlite_connection(self.database) as db:
            self.assertEqual(db.execute("SELECT value FROM sample").fetchone()[0], "saved")

    def test_connection_is_closed_and_transaction_rolled_back_after_error(self):
        with sqlite_connection(self.database) as db:
            db.execute("CREATE TABLE sample (value TEXT NOT NULL)")

        with self.assertRaisesRegex(RuntimeError, "rollback test"):
            with sqlite_connection(self.database) as db:
                db.execute("INSERT INTO sample(value) VALUES (?)", ("should not persist",))
                connection = db
                raise RuntimeError("rollback test")

        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

        with sqlite_connection(self.database) as db:
            count = db.execute("SELECT COUNT(*) FROM sample").fetchone()[0]
        self.assertEqual(count, 0)

    def test_foreign_keys_can_be_enabled_for_connection_scope(self):
        with sqlite_connection(self.database, foreign_keys=True) as db:
            enabled = db.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(enabled, 1)


if __name__ == "__main__":
    unittest.main()
