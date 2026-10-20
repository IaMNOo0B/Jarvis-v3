import unittest
from pathlib import Path


class WindowsSmokeScriptTests(unittest.TestCase):
    def test_notepad_smoke_script_compiles_and_requires_explicit_confirmation(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test_notepad_uia.py"
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
        self.assertIn('confirmation != "RUN"', source)
        self.assertIn('action="type_text"', source)
        self.assertIn('target_name="blank document"', source)
        self.assertIn('if __name__ == "__main__":', source)
        self.assertNotIn("launch_app_with_approval", source)
        self.assertNotIn(".unlink(", source)
        self.assertNotIn(".write_text(", source)


if __name__ == "__main__":
    unittest.main()
