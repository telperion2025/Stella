import unittest
from pathlib import Path

from stella import printing


class TestPrinting(unittest.TestCase):
    def test_postscript_header_and_pages(self):
        ps = printing.generate_postscript("hello\nworld\n", title="doc")
        self.assertTrue(ps.startswith("%!PS-Adobe-3.0"))
        self.assertIn("%%Pages: 1", ps)
        self.assertIn("(hello) show", ps)
        self.assertIn("(world) show", ps)
        self.assertTrue(ps.rstrip().endswith("%%EOF"))

    def test_postscript_escapes(self):
        ps = printing.generate_postscript("a (b) \\ c")
        self.assertIn(r"(a \(b\) \\ c) show", ps)

    def test_pagination(self):
        text = "\n".join("line %d" % i for i in range(200))
        ps = printing.generate_postscript(text, lines_per_page=54)
        self.assertIn("%%Pages: 4", ps)
        self.assertEqual(ps.count("showpage"), 4)

    def test_long_lines_truncated(self):
        ps = printing.generate_postscript("x" * 200, chars_per_line=80)
        self.assertIn("(" + "x" * 80 + ") show", ps)
        self.assertNotIn("x" * 81, ps)

    def test_non_latin1_mapped(self):
        ps = printing.generate_postscript("h€llo 中")
        self.assertIn("(h?llo ?) show", ps)

    def test_write_postscript(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.ps")
            printing.write_postscript("hi there", path, title="t")
            content = Path(path).read_text(encoding="latin-1")
            self.assertIn("(hi there) show", content)


if __name__ == "__main__":
    unittest.main()
