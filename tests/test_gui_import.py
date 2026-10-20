import unittest


class GuiImportTests(unittest.TestCase):
    def test_gui_module_imports_without_starting_window(self):
        from jarvis.gui import JarvisWindow
        self.assertTrue(callable(JarvisWindow))


if __name__ == "__main__":
    unittest.main()
