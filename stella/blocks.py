"""Unified selection model used by WordStar blocks, vi visual mode,
keyboard selection and mouse selection.

A selection is an anchor offset plus the cursor offset; ``start``/``end``
are the normalised bounds.  Block operations (copy/move/delete/duplicate)
are implemented here against a buffer and a clipboard.
"""


class Selection:
    __slots__ = ("anchor", "cursor", "inclusive")

    def __init__(self, anchor, cursor=None, inclusive=False):
        self.anchor = anchor
        self.cursor = anchor if cursor is None else cursor
        self.inclusive = inclusive

    @property
    def start(self):
        return min(self.anchor, self.cursor)

    @property
    def end(self):
        end = max(self.anchor, self.cursor)
        if self.inclusive:
            end += 1
        return end

    def __len__(self):
        return self.end - self.start

    def contains(self, offset):
        return self.start <= offset < self.end


def selected_text(buffer, selection):
    if selection is None or len(selection) == 0:
        return ""
    return buffer.slice(selection.start, selection.end)


def delete_selection(buffer, selection):
    """Remove the selected range; returns the removed text."""
    if selection is None or len(selection) == 0:
        return ""
    removed = buffer.slice(selection.start, selection.end)
    buffer.delete(selection.start, len(selection))
    return removed


def copy_selection(buffer, selection, clipboard):
    """Copy the selected range to the clipboard; returns copied text."""
    text = selected_text(buffer, selection)
    if text:
        clipboard.copy(text)
    return text


def cut_selection(buffer, selection, clipboard):
    """Copy then delete the selected range; returns cut text."""
    text = selected_text(buffer, selection)
    if text:
        clipboard.copy(text)
        buffer.delete(selection.start, len(selection))
    return text


def duplicate_selection(buffer, selection):
    """Insert a copy of the selected text right after the selection."""
    if selection is None or len(selection) == 0:
        return ""
    text = buffer.slice(selection.start, selection.end)
    buffer.insert(selection.end, text)
    return text


def move_selection(buffer, selection, dest):
    """Move the selected range to absolute offset *dest*.

    A destination inside the selection itself is a no-op.
    """
    if selection is None or len(selection) == 0:
        return 0
    if selection.start <= dest <= selection.end:
        return selection.start
    text = buffer.slice(selection.start, selection.end)
    start, end = selection.start, selection.end
    buffer.delete(start, end - start)
    if dest > start:
        dest -= end - start
    buffer.insert(dest, text)
    return dest
