"""Plain-text search and replace (Version 1: no regular expressions)."""


class SearchState:
    """Holds the last query and the current match list."""

    def __init__(self):
        self.query = ""
        self.replacement = ""
        self.matches = []       # list of (start, end) offsets
        self.index = -1         # index of the current match
        self.case_sensitive = True

    def set_query(self, query, text):
        self.query = query
        self.matches = find_all(text, query, self.case_sensitive)
        self.index = -1 if not self.matches else 0

    def next(self, text, from_offset, wrap=True):
        """Advance to the next match at/after *from_offset*; returns (s, e)."""
        if not self.query:
            return None
        self.matches = find_all(text, self.query, self.case_sensitive)
        if not self.matches:
            self.index = -1
            return None
        for i, (s, e) in enumerate(self.matches):
            if s >= from_offset:
                self.index = i
                return s, e
        if wrap and self.matches:
            self.index = 0
            return self.matches[0]
        self.index = len(self.matches) - 1
        return None

    def prev(self, text, from_offset, wrap=True):
        if not self.query:
            return None
        self.matches = find_all(text, self.query, self.case_sensitive)
        if not self.matches:
            self.index = -1
            return None
        for i in range(len(self.matches) - 1, -1, -1):
            s, e = self.matches[i]
            if e <= from_offset:
                self.index = i
                return s, e
        if wrap and self.matches:
            self.index = len(self.matches) - 1
            return self.matches[-1]
        self.index = 0
        return None


def find_all(text, needle, case_sensitive=True):
    """Return a list of ``(start, end)`` offsets of *needle* in *text*."""
    if not needle:
        return []
    hay = text if case_sensitive else text.lower()
    ndl = needle if case_sensitive else needle.lower()
    matches = []
    start = 0
    while True:
        idx = hay.find(ndl, start)
        if idx < 0:
            break
        matches.append((idx, idx + len(ndl)))
        start = idx + len(ndl)
    return matches


def replace_all(text, needle, replacement, case_sensitive=True):
    """Replace every occurrence; returns ``(new_text, count)``."""
    if not needle:
        return text, 0
    matches = find_all(text, needle, case_sensitive)
    if not matches:
        return text, 0
    out = []
    last = 0
    for s, e in matches:
        out.append(text[last:s])
        out.append(replacement)
        last = e
    out.append(text[last:])
    return "".join(out), len(matches)


def replace_one(text, needle, replacement, from_offset=0, case_sensitive=True):
    """Replace the first occurrence at/after *from_offset*.

    Returns ``(new_text, start, end, count)`` where count is 0 or 1 and
    start/end delimit the inserted replacement.
    """
    if not needle:
        return text, 0, 0, 0
    hay = text if case_sensitive else text.lower()
    ndl = needle if case_sensitive else needle.lower()
    idx = hay.find(ndl, from_offset)
    if idx < 0:
        return text, 0, 0, 0
    new_text = text[:idx] + replacement + text[idx + len(ndl):]
    return new_text, idx, idx + len(replacement), 1
