import unittest

from stella.search import SearchState, find_all, replace_all, replace_one


class TestSearch(unittest.TestCase):
    def test_find_all(self):
        text = "foo bar foo baz foo"
        matches = find_all(text, "foo")
        self.assertEqual(matches, [(0, 3), (8, 11), (16, 19)])

    def test_find_all_case_insensitive(self):
        matches = find_all("Foo foo FOO", "foo", case_sensitive=False)
        self.assertEqual(len(matches), 3)

    def test_find_all_empty_needle(self):
        self.assertEqual(find_all("abc", ""), [])

    def test_replace_all(self):
        new, count = replace_all("a b a b a", "a", "X")
        self.assertEqual((new, count), ("X b X b X", 3))

    def test_replace_all_none(self):
        new, count = replace_all("abc", "zzz", "X")
        self.assertEqual((new, count), ("abc", 0))

    def test_replace_one(self):
        new, s, e, count = replace_one("foo foo", "foo", "bar", from_offset=1)
        self.assertEqual(new, "foo bar")
        self.assertEqual((s, e, count), (4, 7, 1))

    def test_replace_one_not_found(self):
        new, s, e, count = replace_one("foo", "x", "y")
        self.assertEqual((new, count), ("foo", 0))

    def test_state_next_wraps(self):
        st = SearchState()
        st.set_query("ab", "ab xx ab")
        m = st.next("ab xx ab", 0)
        self.assertEqual(m, (0, 2))
        m = st.next("ab xx ab", 1)
        self.assertEqual(m, (6, 8))
        m = st.next("ab xx ab", 8)  # wraps
        self.assertEqual(m, (0, 2))

    def test_state_prev(self):
        st = SearchState()
        st.set_query("ab", "ab xx ab")
        m = st.prev("ab xx ab", 8)
        self.assertEqual(m, (6, 8))
        m = st.prev("ab xx ab", 6)
        self.assertEqual(m, (0, 2))


if __name__ == "__main__":
    unittest.main()
