"""Scrollable, in-session help system (F1 or Ctrl-K H)."""

from pathlib import Path

HELP_DIR = Path(__file__).resolve().parent / "help"

TOPICS = [
    ("wordstar", "WordStar commands"),
    ("vi", "vi commands"),
    ("selection", "Selection operations"),
    ("clipboard", "Clipboard commands"),
    ("search", "Search commands"),
    ("printing", "Printing commands"),
    ("config", "Configuration guide"),
]


def _nav(key):
    """Translate a key to a help-navigation action.

    Supports arrow keys, PgUp/PgDn, the WordStar diamond (^E ^X ^S ^D),
    ^R/^C and ^W/^Z, vi-style h j k l, and ^F/^B/^D/^U — so help works even
    on terminals without cursor keys.
    """
    kind, val = key
    if kind == "ctrl":
        return {"E": "up", "X": "down", "S": "left", "D": "right",
                "R": "pageup", "C": "pagedown", "W": "up", "Z": "down",
                "F": "pagedown", "B": "pageup", "D": "down", "U": "up"}.get(val)
    if kind == "key":
        return {"UP": "up", "DOWN": "down", "LEFT": "left", "RIGHT": "right",
                "PPAGE": "pageup", "NPAGE": "pagedown"}.get(val)
    if kind == "char":
        return {"k": "up", "j": "down", "h": "left", "l": "right"}.get(val)
    return None


def load_topics():
    """Return a list of ``(title, body)`` help topics."""
    topics = []
    for key, title in TOPICS:
        path = HELP_DIR / (key + ".txt")
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            body = "(help topic unavailable)"
        topics.append((title, body.rstrip("\n").splitlines()))
    return topics


class HelpViewer:
    """Full-screen help overlay with a topic menu and scrollable pages."""

    def __init__(self, screen, topics=None):
        self.screen = screen
        self.topics = topics if topics is not None else load_topics()
        self.menu_index = 0
        self.doc = None       # list of lines when viewing a topic
        self.doc_top = 0

    def run(self):
        while True:
            if self.doc is None:
                if not self._menu_loop():
                    return
            else:
                if not self._doc_loop():
                    return

    # ------------------------------------------------------------------
    def _menu_loop(self):
        h, w = self.screen.height, self.screen.width
        while True:
            self.screen.stdscr.erase()
            self.screen._addstr(0, 0, " STELLA HELP - select a topic".ljust(w), self.screen.attrs["status"])
            for i, (title, _body) in enumerate(self.topics):
                marker = ">" if i == self.menu_index else " "
                self.screen._addstr(2 + i, 2, ("%s %d. %s" % (marker, i + 1, title)).ljust(w - 4),
                                    self.screen.attrs["edit"] if i != self.menu_index else self.screen.attrs["selection"])
            self.screen._addstr(h - 1, 0, " Up/Down, ^E/^X, h/j select  Enter open  F1/Esc quit".ljust(w), self.screen.attrs["help"])
            self.screen.stdscr.refresh()
            kind, val = self.screen.read_key()
            if kind == "key" and val in ("ESC", "F1"):
                return False
            nav = _nav((kind, val))
            if nav == "up":
                self.menu_index = (self.menu_index - 1) % len(self.topics)
            elif nav == "down":
                self.menu_index = (self.menu_index + 1) % len(self.topics)
            elif kind == "key" and val == "ENTER":
                self.doc = self.topics[self.menu_index][1]
                self.doc_top = 0
                return True
            elif kind == "char" and val.isdigit() and 1 <= int(val) <= len(self.topics):
                self.doc = self.topics[int(val) - 1][1]
                self.doc_top = 0
                return True
            elif kind == "key" and val == "RESIZE":
                self.screen.resize()

    def _doc_loop(self):
        h, w = self.screen.height, self.screen.width
        rows = max(1, h - 2)
        while True:
            self.screen.stdscr.erase()
            title = self.topics[self.menu_index][0]
            self.screen._addstr(0, 0, (" %s" % title).ljust(w), self.screen.attrs["status"])
            lines = self.doc
            for i in range(rows):
                idx = self.doc_top + i
                if idx < len(lines):
                    self.screen._addstr(1 + i, 0, lines[idx][: w - 1], self.screen.attrs["edit"])
            self.screen._addstr(h - 1, 0, " Arrows/PgUp/PgDn, ^E/^X/^S/^D, ^R/^C, hjkl scroll  Esc menu  F1 quit".ljust(w), self.screen.attrs["help"])
            self.screen.stdscr.refresh()
            kind, val = self.screen.read_key()
            if kind == "key" and val in ("ESC",):
                self.doc = None
                return True
            if kind == "key" and val == "F1":
                self.doc = None
                return False
            if kind == "key" and val == "RESIZE":
                self.screen.resize()
                h, w = self.screen.height, self.screen.width
                rows = max(1, h - 2)
            nav = _nav((kind, val))
            if nav == "up":
                self.doc_top = max(0, self.doc_top - 1)
            elif nav == "down":
                self.doc_top = min(max(0, len(lines) - rows), self.doc_top + 1)
            elif nav == "pageup":
                self.doc_top = max(0, self.doc_top - rows)
            elif nav == "pagedown":
                self.doc_top = min(max(0, len(lines) - rows), self.doc_top + rows)
