import unittest

from stella.buffer import GapBuffer


class TestGapBuffer(unittest.TestCase):
    def test_empty(self):
        b = GapBuffer()
        self.assertEqual(len(b), 0)
        self.assertEqual(b.text, "")
        self.assertEqual(b.line_count, 1)

    def test_insert_and_text(self):
        b = GapBuffer()
        b.insert(0, "hello world")
        self.assertEqual(b.text, "hello world")
        self.assertEqual(len(b), 11)

    def test_insert_middle(self):
        b = GapBuffer("heloworld")
        b.insert(4, "-")
        self.assertEqual(b.text, "helo-world")
        b.insert(0, ">>")
        self.assertEqual(b.text, ">>helo-world")

    def test_delete(self):
        b = GapBuffer("hello world")
        n = b.delete(5, 6)
        self.assertEqual(n, 6)
        self.assertEqual(b.text, "hello")

    def test_delete_clamps(self):
        b = GapBuffer("abc")
        n = b.delete(1, 100)
        self.assertEqual(n, 2)
        self.assertEqual(b.text, "a")

    def test_replace(self):
        b = GapBuffer("hello world")
        removed = b.replace(6, 5, "there")
        self.assertEqual(removed, "world")
        self.assertEqual(b.text, "hello there")

    def test_replace_middle(self):
        b = GapBuffer("abcdef")
        removed = b.replace(1, 2, "XY")
        self.assertEqual(removed, "bc")
        self.assertEqual(b.text, "aXYdef")

    def test_replace_middle_with_newline(self):
        b = GapBuffer("ab\ncd\nef")
        b.replace(1, 3, "X\nY")
        self.assertEqual(b.text, "aX\nYd\nef")
        self.assertEqual([b.line(i) for i in range(b.line_count)], ["aX", "Yd", "ef"])

    def test_line_index_basic(self):
        b = GapBuffer("ab\ncd\nef")
        self.assertEqual(b.line_count, 3)
        self.assertEqual(b.line(0), "ab")
        self.assertEqual(b.line(1), "cd")
        self.assertEqual(b.line(2), "ef")
        self.assertEqual(b.line_start(2), 6)

    def test_line_index_after_insert_newline(self):
        b = GapBuffer("abcd")
        b.insert(2, "x\ny")
        self.assertEqual(b.text, "abx\nycd")
        self.assertEqual(b.line_count, 2)
        self.assertEqual(b.line(0), "abx")
        self.assertEqual(b.line(1), "ycd")

    def test_line_index_after_delete_newline(self):
        b = GapBuffer("ab\ncd")
        b.delete(2, 1)  # remove the newline
        self.assertEqual(b.text, "abcd")
        self.assertEqual(b.line_count, 1)
        self.assertEqual(b.line(0), "abcd")

    def test_line_index_delete_range_spanning_lines(self):
        b = GapBuffer("ab\ncd\nef")
        b.delete(0, 4)  # "ab\nc"
        self.assertEqual(b.text, "d\nef")
        self.assertEqual(b.line_count, 2)
        self.assertEqual(b.line(0), "d")
        self.assertEqual(b.line(1), "ef")

    def test_line_index_insert_at_line_start(self):
        b = GapBuffer("ab\ncd")
        b.insert(3, "X\n")
        self.assertEqual(b.text, "ab\nX\ncd")
        self.assertEqual(b.line_count, 3)
        self.assertEqual([b.line(i) for i in range(3)], ["ab", "X", "cd"])

    def test_offset_line_col_roundtrip(self):
        b = GapBuffer("one\ntwo\nthree\n")
        for off in range(len(b) + 1):
            line, col = b.offset_to_line_col(off)
            self.assertEqual(b.line_col_to_offset(line, col), off)

    def test_line_col_to_offset_clamps(self):
        b = GapBuffer("ab\ncd")
        self.assertEqual(b.line_col_to_offset(0, 99), 2)
        self.assertEqual(b.line_col_to_offset(99, 0), 3)
        self.assertEqual(b.line_col_to_offset(1, 2), 5)

    def test_slice_across_gap(self):
        b = GapBuffer("hello world")
        b.move_gap(5)
        self.assertEqual(b.slice(3, 8), "lo wo")
        self.assertEqual(b.slice(0, 5), "hello")
        self.assertEqual(b.slice(5, 11), " world")

    def test_char_at(self):
        b = GapBuffer("abcdef")
        b.move_gap(2)
        self.assertEqual(b.char_at(0), "a")
        self.assertEqual(b.char_at(5), "f")

    def test_trailing_newline_line(self):
        b = GapBuffer("a\n")
        self.assertEqual(b.line_count, 2)
        self.assertEqual(b.line(1), "")

    def test_large_file(self):
        text = ("line %d of the file\n" % 0) * 1
        big = "".join("line %d\n" % i for i in range(20000))
        b = GapBuffer(big)
        self.assertEqual(len(b), len(big))
        self.assertEqual(b.line_count, 20001)
        self.assertEqual(b.line(19999), "line 19999")
        b.insert(len(big) // 2, "INSERTED\n")
        self.assertIn("INSERTED", b.text)
        self.assertEqual(b.line_count, 20002)


if __name__ == "__main__":
    unittest.main()
