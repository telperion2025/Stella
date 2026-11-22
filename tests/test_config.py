import tempfile
import unittest
from pathlib import Path

from stella.config import load_config


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = load_config("/nonexistent/path/rc")
        self.assertEqual(cfg["default_mode"], "wordstar")
        self.assertEqual(cfg["tab_width"], 4)
        self.assertTrue(cfg["mouse"])
        self.assertEqual(cfg["theme"], "wordstar")
        self.assertEqual(cfg["copy_key"], "^C")

    def test_parse_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".rc", delete=False) as fh:
            fh.write("# comment\ndefault_mode=vi\ntab_width=8\nmouse=false\ntheme=wordstar\n")
            fh.write("copy_key=^y\n")
            path = fh.name
        cfg = load_config(path)
        self.assertEqual(cfg["default_mode"], "vi")
        self.assertEqual(cfg["tab_width"], 8)
        self.assertFalse(cfg["mouse"])
        self.assertEqual(cfg["copy_key"], "^Y")
        Path(path).unlink()

    def test_bad_tab_width_falls_back(self):
        with tempfile.NamedTemporaryFile("w", suffix=".rc", delete=False) as fh:
            fh.write("tab_width=banana\n")
            path = fh.name
        cfg = load_config(path)
        self.assertEqual(cfg["tab_width"], 4)
        Path(path).unlink()

    def test_bad_mode_falls_back(self):
        with tempfile.NamedTemporaryFile("w", suffix=".rc", delete=False) as fh:
            fh.write("default_mode=emacs\n")
            path = fh.name
        cfg = load_config(path)
        self.assertEqual(cfg["default_mode"], "wordstar")
        Path(path).unlink()


if __name__ == "__main__":
    unittest.main()
