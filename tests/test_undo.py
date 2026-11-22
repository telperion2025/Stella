import unittest

from stella.buffer import GapBuffer
from stella.undo import UndoHistory


class TestUndo(unittest.TestCase):
    def test_undo_insert(self):
        b = GapBuffer()
        h = UndoHistory()
        b.insert(0, "hello")
        h.push(0, "", "hello")
        pos = h.undo(b)
        self.assertEqual(b.text, "")
        self.assertEqual(pos, 0)
        pos = h.redo(b)
        self.assertEqual(b.text, "hello")
        self.assertEqual(pos, 5)

    def test_undo_delete(self):
        b = GapBuffer("hello world")
        h = UndoHistory()
        deleted = b.slice(5, 11)
        b.delete(5, 6)
        h.push(5, deleted, "")
        h.undo(b)
        self.assertEqual(b.text, "hello world")
        h.redo(b)
        self.assertEqual(b.text, "hello")

    def test_multi_level(self):
        b = GapBuffer()
        h = UndoHistory()
        for s in ["a", "b", "c"]:
            b.insert(0, s)
            h.push(0, "", s)
        self.assertEqual(b.text, "cba")
        h.undo(b)
        self.assertEqual(b.text, "ba")
        h.undo(b)
        self.assertEqual(b.text, "a")
        h.undo(b)
        self.assertEqual(b.text, "")
        self.assertFalse(h.can_undo())
        h.redo(b)
        self.assertEqual(b.text, "a")
        h.redo(b)
        self.assertEqual(b.text, "ba")

    def test_typing_merges_into_single_entry(self):
        b = GapBuffer()
        h = UndoHistory()
        for ch in "word":
            pos = len(b)
            b.insert(pos, ch)
            h.push(pos, "", ch)
        h.undo(b)
        self.assertEqual(b.text, "")

    def test_consecutive_backspaces_merge(self):
        b = GapBuffer("abc")
        h = UndoHistory()
        for pos in (2, 1, 0):
            deleted = b.slice(pos, pos + 1)
            b.delete(pos, 1)
            h.push(pos, deleted, "")
        self.assertEqual(b.text, "")
        h.undo(b)  # one undo restores the whole run
        self.assertEqual(b.text, "abc")
        self.assertFalse(h.can_undo())

    def test_push_clears_redo(self):
        b = GapBuffer("x")
        h = UndoHistory()
        h.push(0, "", "x")
        h.undo(b)
        self.assertTrue(h.can_redo())
        h.push(1, "", "y")
        self.assertFalse(h.can_redo())


if __name__ == "__main__":
    unittest.main()
