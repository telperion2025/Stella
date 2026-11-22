import unittest

from stella.clipboard import Clipboard


class TestClipboard(unittest.TestCase):
    def test_internal_roundtrip(self):
        clip = Clipboard(use_system=False)
        clip.copy("hello")
        self.assertEqual(clip.paste(), "hello")
        self.assertEqual(clip._source, "internal")

    def test_paste_falls_back_to_internal_when_no_system_tool(self):
        clip = Clipboard(use_system=True)
        clip._tool = None  # simulate no xclip/xsel/wl-copy/pbcopy
        clip._source = "system"
        clip.internal = "local"
        self.assertEqual(clip.paste(), "local")

    def test_copy_marks_internal_when_system_unavailable(self):
        clip = Clipboard(use_system=True)
        clip._tool = None
        clip.copy("data")
        self.assertEqual(clip._source, "internal")
        self.assertEqual(clip.paste(), "data")


if __name__ == "__main__":
    unittest.main()
