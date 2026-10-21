import tempfile
import unittest
from pathlib import Path

from jarvis.source_inspection import inspect_source_tree, trace_symbol


class SourceInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "pkg").mkdir()
        (self.root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "pkg" / "worker.py").write_text(
            "from pathlib import Path\n"
            "class Worker:\n"
            "    def run(self):\n"
            "        return helper()\n"
            "def helper():\n"
            "    return Path('.')\n",
            encoding="utf-8",
        )
        (self.root / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_inspects_without_importing_and_records_hashes_symbols_imports_and_calls(self):
        report = inspect_source_tree(self.root)
        self.assertEqual(len(report.files), 3)
        worker = next(item for item in report.files if item.path == "pkg/worker.py")
        self.assertTrue(worker.parsed)
        self.assertEqual(len(worker.sha256), 64)
        self.assertTrue(any(item.qualified_name == "Worker.run" for item in report.symbols))
        self.assertTrue(any(item.module == "pathlib" for item in report.imports))
        self.assertTrue(any(item.callee == "helper" for item in report.calls))
        self.assertTrue(any("SyntaxError" in warning for warning in report.warnings))

    def test_trace_returns_exact_definition_and_static_callers(self):
        report = inspect_source_tree(self.root)
        traced = trace_symbol(report, "helper")
        self.assertEqual([item.name for item in traced["definitions"]], ["helper"])
        self.assertTrue(any(item.caller == "Worker.run" for item in traced["callers"]))

    def test_rejects_invalid_root_and_limits(self):
        with self.assertRaises(ValueError):
            inspect_source_tree(self.root / "missing")
        with self.assertRaises(ValueError):
            inspect_source_tree(self.root, max_files=0)
        with self.assertRaises(ValueError):
            trace_symbol(inspect_source_tree(self.root), " ")

    def test_oversized_file_is_reported_and_skipped(self):
        (self.root / "large.py").write_text("x = 1\n" * 20, encoding="utf-8")
        report = inspect_source_tree(self.root, max_file_bytes=10)
        large = next(item for item in report.files if item.path == "large.py")
        self.assertFalse(large.parsed)
        self.assertTrue(any("oversized" in warning for warning in report.warnings))


if __name__ == "__main__":
    unittest.main()
