"""Multi-level undo/redo history based on a command history stack.

Each entry records one edit as ``(pos, deleted, inserted)``: applying the
inverse deletes ``inserted`` and re-inserts ``deleted`` at ``pos``.
Consecutive single-character insertions at a contiguous position are merged
into one entry so typing a word is a single undo step.
"""


class UndoEntry:
    __slots__ = ("pos", "deleted", "inserted")

    def __init__(self, pos, deleted, inserted):
        self.pos = pos
        self.deleted = deleted
        self.inserted = inserted


class UndoHistory:
    """Stack of edits with multi-level undo and redo."""

    def __init__(self, limit=1000):
        self._undo = []
        self._redo = []
        self.limit = limit

    def push(self, pos, deleted, inserted):
        if not deleted and not inserted:
            return
        entry = UndoEntry(pos, deleted, inserted)
        if (
            inserted
            and not deleted
            and len(inserted) == 1
            and self._undo
            and self._undo[-1].deleted == ""
            and self._undo[-1].pos + len(self._undo[-1].inserted) == pos
        ):
            prev = self._undo[-1]
            prev.inserted += inserted
            return
        self._undo.append(entry)
        if len(self._undo) > self.limit:
            del self._undo[0]
        self._redo.clear()

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo(self, buffer):
        """Reverse the last edit on *buffer*; returns cursor position or None."""
        if not self._undo:
            return None
        entry = self._undo.pop()
        if entry.inserted:
            buffer.delete(entry.pos, len(entry.inserted))
        if entry.deleted:
            buffer.insert(entry.pos, entry.deleted)
        self._redo.append(entry)
        return entry.pos

    def redo(self, buffer):
        """Re-apply the last undone edit on *buffer*; returns cursor or None."""
        if not self._redo:
            return None
        entry = self._redo.pop()
        if entry.deleted:
            buffer.delete(entry.pos, len(entry.deleted))
        if entry.inserted:
            buffer.insert(entry.pos, entry.inserted)
        self._undo.append(entry)
        return entry.pos + len(entry.inserted)

    def clear(self):
        self._undo.clear()
        self._redo.clear()
