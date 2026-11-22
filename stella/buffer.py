"""Gap buffer text storage for Stella.

The buffer keeps the document as two contiguous strings, ``_left`` and
``_right``, with the "gap" between them.  The cursor/edit position lives at
the gap, so insertions and deletions at the edit point are amortised O(1);
moving the gap rebalances by copying the smaller side.  A sorted index of
line-start offsets is maintained incrementally so line/column conversions
stay O(log n).
"""

from bisect import bisect_right


class GapBuffer:
    """A text buffer using the gap-buffer architecture."""

    def __init__(self, text=""):
        self._left = ""
        self._right = ""
        self._line_starts = [0]
        if text:
            self.insert(0, text)

    # ------------------------------------------------------------------
    # basic accessors
    # ------------------------------------------------------------------
    def __len__(self):
        return len(self._left) + len(self._right)

    @property
    def gap(self):
        """Offset of the gap (i.e. length of the left part)."""
        return len(self._left)

    @property
    def text(self):
        """The full document text."""
        return self._left + self._right

    def slice(self, start, end):
        """Return ``text[start:end]`` without materialising the full text."""
        start = max(0, min(start, len(self)))
        end = max(start, min(end, len(self)))
        gap = len(self._left)
        if end <= gap:
            return self._left[start:end]
        if start >= gap:
            return self._right[start - gap:end - gap]
        return self._left[start:] + self._right[:end - gap]

    def char_at(self, pos):
        gap = len(self._left)
        if pos < gap:
            return self._left[pos]
        return self._right[pos - gap]

    # ------------------------------------------------------------------
    # gap movement and edits
    # ------------------------------------------------------------------
    def move_gap(self, pos):
        """Move the gap to absolute offset *pos*."""
        pos = max(0, min(pos, len(self)))
        gap = len(self._left)
        if pos == gap:
            return
        if pos < gap:
            moved = self._left[pos:gap]
            self._left = self._left[:pos]
            self._right = moved + self._right
        else:
            moved = self._right[:pos - gap]
            self._right = self._right[pos - gap:]
            self._left = self._left + moved

    def insert(self, pos, text):
        """Insert *text* at absolute offset *pos*."""
        if not text:
            return
        self.move_gap(pos)
        self._left += text
        self._update_line_starts_on_insert(pos, text)

    def delete(self, pos, length):
        """Delete *length* characters starting at absolute offset *pos*."""
        if length <= 0:
            return 0
        length = min(length, len(self) - pos)
        if length <= 0:
            return 0
        removed = self.slice(pos, pos + length)
        self.move_gap(pos)
        self._right = self._right[length:]
        self._update_line_starts_on_delete(pos, removed)
        return length

    def replace(self, pos, length, text):
        """Replace *length* chars at *pos* with *text*; returns removed text."""
        removed = self.slice(pos, pos + length)
        self.move_gap(pos)
        self._right = self._right[length:]
        self._left += text
        self._update_line_starts_on_delete(pos, removed)
        self._update_line_starts_on_insert(pos, text)
        return removed

    # ------------------------------------------------------------------
    # line index
    # ------------------------------------------------------------------
    def _update_line_starts_on_insert(self, pos, text):
        shift = len(text)
        starts = self._line_starts
        idx = bisect_right(starts, pos)
        starts[idx:] = [s + shift for s in starts[idx:]]
        new_starts = [pos + i + 1 for i, ch in enumerate(text) if ch == "\n"]
        if new_starts:
            starts[idx:idx] = new_starts

    def _update_line_starts_on_delete(self, pos, removed):
        end = pos + len(removed)
        starts = self._line_starts
        # A line start s (s > 0) exists iff text[s-1] == '\n'.  Deleting
        # [pos, end) removes the newline feeding any start with
        # pos < s <= end, so those starts disappear.
        lo = bisect_right(starts, pos)
        hi = bisect_right(starts, end)
        del starts[lo:hi]
        # starts beyond the removed range shift down
        idx = bisect_right(starts, end)
        starts[idx:] = [s - len(removed) for s in starts[idx:]]

    @property
    def line_count(self):
        return len(self._line_starts)

    def line_start(self, line):
        """Absolute offset at which *line* (0-based) starts."""
        return self._line_starts[max(0, min(line, len(self._line_starts) - 1))]

    def line(self, line_no):
        """Return the text of *line_no* (0-based) without its newline."""
        start = self.line_start(line_no)
        if line_no + 1 < len(self._line_starts):
            end = self._line_starts[line_no + 1] - 1  # drop the newline
        else:
            end = len(self)
        return self.slice(start, end)

    def line_length(self, line_no):
        start = self.line_start(line_no)
        if line_no + 1 < len(self._line_starts):
            end = self._line_starts[line_no + 1] - 1
        else:
            end = len(self)
        return max(0, end - start)

    def offset_to_line_col(self, offset):
        """Convert absolute *offset* to a 0-based ``(line, col)`` pair."""
        offset = max(0, min(offset, len(self)))
        line = bisect_right(self._line_starts, offset) - 1
        return line, offset - self._line_starts[line]

    def line_col_to_offset(self, line, col):
        """Convert 0-based ``(line, col)`` to an absolute offset.

        The result is clamped to the end of *line* so vertical movement
        never spills onto the following line.
        """
        line = max(0, min(line, len(self._line_starts) - 1))
        start = self._line_starts[line]
        return min(start + max(0, col), start + self.line_length(line))
