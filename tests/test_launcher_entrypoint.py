import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_startup_launcher():
    """Load the .pyw helpers without launching the Tk window or changing cwd."""
    path = ROOT / "Start_JARVIS.pyw"
    loader = SourceFileLoader("jarvis_startup_launcher_for_test", str(path))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    with patch("os.chdir"):
        loader.exec_module(module)
    return module


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
        self.assertIn('if not exist "Start_JARVIS.pyw" (', start_block)
        self.assertIn('if not exist ".venv\\Scripts\\pythonw.exe" (', start_block)
        launch_index = start_block.index('start "" ".venv\\Scripts\\pythonw.exe" "Start_JARVIS.pyw"')
        self.assertLess(start_block.index('if not exist "Start_JARVIS.pyw" ('), launch_index)
        self.assertLess(start_block.index('if not exist ".venv\\Scripts\\pythonw.exe" ('), launch_index)
        self.assertIn('start "" ".venv\\Scripts\\pythonw.exe" "Start_JARVIS.pyw"', start_block)

    def test_maintenance_menu_remains_available(self):
        launcher = (ROOT / "JARVIS.bat").read_text(encoding="utf-8")
        self.assertIn("First-time setup / repair environment", launcher)
        self.assertIn("Update JARVIS safely", launcher)
        self.assertIn("Run diagnostics", launcher)

    def test_redacts_credentials_from_startup_diagnostics(self):
        launcher = load_startup_launcher()
        api_key = "AIza123456789012345678901234"
        github_token = "ghp_abcdefghijklmnopqrstuvwxyz123456"
        diagnostic = f"api_key={api_key} token={github_token} Bearer abc.def.ghi"
        redacted = launcher._redact_diagnostic(diagnostic)
        self.assertNotIn(api_key, redacted)
        self.assertNotIn(github_token, redacted)
        self.assertNotIn("abc.def.ghi", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_launcher_surfaces_errors_without_requiring_a_console(self):
        launcher = (ROOT / "Start_JARVIS.pyw").read_text(encoding="utf-8")
        self.assertIn("_report_startup_failure(exc)", launcher)
        self.assertIn("MessageBoxW", launcher)
        self.assertIn("startup-error.log", launcher)
        self.assertIn("JARVIS.bat --menu", launcher)


if __name__ == "__main__":
    unittest.main()
