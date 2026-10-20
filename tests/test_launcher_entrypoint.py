import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsLauncherTests(unittest.TestCase):
    def test_double_click_defaults_to_start_not_menu(self):
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        self.assertIn('if /i "%~1"=="--menu" goto menu', launcher)
        self.assertIn("goto start\n\n:menu", launcher)

    def test_start_path_bootstraps_venv_and_runs_gui(self):
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        start_block = launcher.split(":start", 1)[1].split(":update", 1)[0]
        self.assertIn('".venv\\Scripts\\python.exe"', start_block)
        self.assertIn(" -m venv .venv", start_block)
        self.assertIn('start "" ".venv\\Scripts\\pythonw.exe" "Start_JARVIS.pyw"', start_block)

    def test_maintenance_menu_remains_available(self):
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        self.assertIn("First-time setup / repair environment", launcher)
        self.assertIn("Update JARVIS safely", launcher)
        self.assertIn("Run diagnostics", launcher)


if __name__ == "__main__":
    unittest.main()
