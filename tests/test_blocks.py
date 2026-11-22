import unittest

from stella import blocks
from stella.buffer import GapBuffer
from stella.clipboard import Clipboard


class TestSelection(unittest.TestCase):
    def test_normalised_bounds(self):
        s = blocks.Selection(10, 3)
        self.assertEqual((s.start, s.end), (3, 10))
        self.assertEqual(len(s), 7)

    def test_selected_text(self):
        b = GapBuffer("hello world")
        s = blocks.Selection(6, 11)
        self.assertEqual(blocks.selected_text(b, s), "world")

    def test_copy_selection(self):
        b = GapBuffer("hello world")
        clip = Clipboard(use_system=False)
        s = blocks.Selection(0, 5)
        blocks.copy_selection(b, s, clip)
        self.assertEqual(clip.internal, "hello")
        self.assertEqual(b.text, "hello world")

    def test_cut_selection(self):
        b = GapBuffer("hello world")
        clip = Clipboard(use_system=False)
        s = blocks.Selection(0, 6)
        blocks.cut_selection(b, s, clip)
        self.assertEqual(b.text, "world")
        self.assertEqual(clip.internal, "hello ")

    def test_duplicate_selection(self):
        b = GapBuffer("abc")
        s = blocks.Selection(0, 2)
        blocks.duplicate_selection(b, s)
        self.assertEqual(b.text, "ababc")

    def test_move_selection(self):
        b = GapBuffer("abcde")
        s = blocks.Selection(0, 2)  # "ab"
        dest = blocks.move_selection(b, s, 5)
        self.assertEqual(b.text, "cdeab")
        self.assertEqual(dest, 3)

    def test_move_selection_forward(self):
        b = GapBuffer("abcde")
        s = blocks.Selection(3, 5)  # "de"
        blocks.move_selection(b, s, 0)
        self.assertEqual(b.text, "deabc")

    def test_empty_selection_ops(self):
        b = GapBuffer("abc")
        clip = Clipboard(use_system=False)
        s = blocks.Selection(1, 1)
        self.assertEqual(blocks.cut_selection(b, s, clip), "")
        self.assertEqual(b.text, "abc")


if __name__ == "__main__":
    unittest.main()
