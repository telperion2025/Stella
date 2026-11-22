"""Curses screen layer: colours, key/mouse input, and rendering."""

import curses
import os
import termios

from .themes import MONOCHROME, FOREGROUNDS, get_theme

_KEY_NAMES = {}
for _name in ("UP", "DOWN", "LEFT", "RIGHT", "PPAGE", "NPAGE", "HOME", "END",
              "DC", "IC", "F1", "F2", "BACKSPACE", "RESIZE"):
    _code = getattr(curses, "KEY_" + _name, None)
    if _code is not None:
        _label = {"DC": "DEL", "IC": "INS", "BACKSPACE": "BS"}.get(_name, _name)
        _KEY_NAMES[_code] = _label

HELP_LINE = "^K Files ^Q Search ^B Block F1 Help INS  ^C Copy ^W Cut ^V Paste"


def _mono_attr(element):
    attr = 0
    for a in MONOCHROME.get(element, ["normal"]):
        if a != "normal":
            attr |= a
    return attr


def display_col(text, col, tab_width):
    """Display column (tab-expanded) of character column *col* in *text*."""
    x = 0
    for ch in text[:col]:
        x += (tab_width - (x % tab_width)) if ch == "\t" else 1
    return x


def col_at_display(text, dx, tab_width):
    """Inverse of :func:`display_col`: character column at display column *dx*."""
    x = 0
    col = 0
    for ch in text:
        w = (tab_width - (x % tab_width)) if ch == "\t" else 1
        if x + w > dx:
            break
        x += w
        col += 1
    return col


class Screen:
    def __init__(self, stdscr, config):
        self.stdscr = stdscr
        self.config = config
        self.height, self.width = stdscr.getmaxyx()
        self.attrs = {}
        self.mouse_enabled = False
        self._init_terminal()

    # ------------------------------------------------------------------
    # terminal setup / teardown
    # ------------------------------------------------------------------
    def _init_terminal(self):
        stdscr = self.stdscr
        stdscr.keypad(True)
        try:
            curses.set_escdelay(25)
        except (AttributeError, curses.error):
            os.environ.setdefault("ESCDELAY", "25")
        curses.noecho()
        curses.cbreak()
        curses.curs_set(1)
        # Deliver ^S/^Q/^C etc. to the program instead of the tty driver.
        try:
            import sys
            fd = sys.stdin.fileno() if sys.stdin.isatty() else 0
            attrs = termios.tcgetattr(fd)

            def _flag(name):
                return getattr(termios, name, 0)

            iflag = _flag("IXON") | _flag("IXOFF") | _flag("ICRNL") | _flag("IBRNL")
            lflag = _flag("ISIG") | _flag("IEXTEN")
            attrs[0] &= ~iflag
            attrs[3] &= ~lflag
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
        except (termios.error, OSError, ValueError):
            pass
        if curses.has_colors():
            try:
                curses.start_color()
            except curses.error:
                pass
            ncolors = max(2, curses.COLORS)
            theme = get_theme(self.config.get("theme", "wordstar"))
            if not isinstance(theme.get("edit"), tuple):
                theme = MONOCHROME
            for i, (element, (fg, bg)) in enumerate(theme.items(), 1):
                fg_c = min(FOREGROUNDS[fg], ncolors - 1)
                bg_c = min(FOREGROUNDS[bg], ncolors - 1)
                try:
                    curses.init_pair(i, fg_c, bg_c)
                    self.attrs[element] = curses.color_pair(i)
                except (curses.error, ValueError):
                    self.attrs[element] = _mono_attr(element)
        else:
            for element, attr_list in MONOCHROME.items():
                attr = 0
                for a in attr_list:
                    if a != "normal":
                        attr |= a
                self.attrs[element] = attr
        for element in ("edit", "status", "help", "selection", "search", "error", "message"):
            self.attrs.setdefault(element, 0)
        if self.config.get("mouse", True):
            try:
                curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
                curses.mouseinterval(0)
                self.mouse_enabled = True
            except curses.error:
                self.mouse_enabled = False

    def leave(self):
        try:
            curses.mousemask(0)
        except curses.error:
            pass
        try:
            curses.curs_set(1)
        except curses.error:
            pass

    def resize(self):
        self.height, self.width = self.stdscr.getmaxyx()
        try:
            self.stdscr.erase()
        except curses.error:
            pass

    # ------------------------------------------------------------------
    # input
    # ------------------------------------------------------------------
    def read_key(self):
        """Read one key; returns a ``(kind, value)`` tuple.

        kind is one of 'char', 'ctrl', 'key', 'mouse', 'none'.
        """
        try:
            ch = self.stdscr.getch()
        except curses.error:
            return ("none", None)
        if ch == -1:
            return ("none", None)
        if ch == 27:
            return ("key", "ESC")
        if ch in (10, 13):
            return ("key", "ENTER")
        if ch in (8, 127, curses.KEY_BACKSPACE):
            return ("key", "BS")
        if ch == 9:
            return ("key", "TAB")
        if 1 <= ch <= 26:
            return ("ctrl", chr(64 + ch))
        if ch == curses.KEY_MOUSE:
            try:
                _id, x, y, _z, bstate = curses.getmouse()
            except curses.error:
                return ("none", None)
            return ("mouse", (x, y, bstate))
        if ch in _KEY_NAMES:
            return ("key", _KEY_NAMES[ch])
        if ch >= 32:
            try:
                return ("char", chr(ch))
            except (ValueError, OverflowError):
                return ("none", None)
        return ("none", None)

    def read_line(self, label, default="", render=None):
        """Prompt on the bottom line; returns the entered string or None
        when cancelled with Esc."""
        text = default
        while True:
            if render is not None:
                render(label, text)
            kind, val = self.read_key()
            if kind == "key" and val == "ENTER":
                return text
            if kind == "key" and val == "ESC":
                return None
            if kind == "key" and val == "RESIZE":
                self.resize()
            elif kind == "key" and val == "BS":
                text = text[:-1]
            elif kind == "char":
                text += val

    def read_yes_no(self, label, render=None):
        """Read a single y/n answer; returns True for yes, False otherwise."""
        while True:
            if render is not None:
                render(label, "")
            kind, val = self.read_key()
            if kind == "char" and val.lower() == "y":
                return True
            if kind == "char" and val.lower() == "n":
                return False
            if kind == "key" and val == "ESC":
                return False
            if kind == "key" and val == "RESIZE":
                self.resize()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def _addstr(self, y, x, s, attr=0):
        if y < 0 or y >= self.height or x >= self.width or not s:
            return
        s = s[: self.width - x]
        try:
            self.stdscr.addnstr(y, x, s, len(s), attr)
        except curses.error:
            pass

    def render(self, ed):
        self.stdscr.erase()
        h, w = self.height, self.width
        # status line (row 0)
        line, col = ed.buffer.offset_to_line_col(ed.cursor)
        name = os.path.basename(ed.filename) if ed.filename else "[No Name]"
        mark = " *" if ed.modified else ""
        mode = "INS" if ed.insert_mode else "OVR"
        status = " %s%s Ln:%d Col:%d %s %s" % (name, mark, line + 1, col + 1, mode, ed.mode_label())
        self._addstr(0, 0, status.ljust(w), self.attrs["status"])
        # editing area (rows 1 .. h-2)
        text_rows = max(1, h - 2)
        last_ln = min(ed.top_line + text_rows - 1, ed.buffer.line_count - 1)
        vis_start = ed.buffer.line_start(ed.top_line)
        vis_end = ed.buffer.line_start(last_ln) + ed.buffer.line_length(last_ln)
        match_offsets = set()
        matches = ed.search.matches
        if matches:
            from bisect import bisect_left
            qlen = max(1, len(ed.search.query))
            i = bisect_left(matches, (max(0, vis_start - qlen), 0))
            for s, e in matches[i:]:
                if s >= vis_end:
                    break
                if e > vis_start:
                    match_offsets.update(range(max(s, vis_start), min(e, vis_end)))
        sel = ed.selection
        for row in range(1, h - 1):
            ln = ed.top_line + (row - 1)
            if ln >= ed.buffer.line_count:
                self._addstr(row, 0, " " * w, self.attrs["edit"])
                continue
            self._render_line(ed, row, ln, sel, match_offsets)
        # bottom line (row h-1): prompt, message, or help
        bottom = h - 1
        if ed.prompt is not None:
            label, text = ed.prompt
            self._addstr(bottom, 0, (label + text).ljust(w), self.attrs["message"])
        elif ed.message:
            attr = self.attrs["error"] if ed.message_is_error else self.attrs["message"]
            self._addstr(bottom, 0, ed.message.ljust(w), attr)
        else:
            self._addstr(bottom, 0, HELP_LINE.ljust(w), self.attrs["help"])
        # place the cursor
        cx, cy = self.cursor_pos(ed)
        try:
            self.stdscr.move(cy, cx)
        except curses.error:
            pass
        self.stdscr.refresh()

    def _render_line(self, ed, row, ln, sel, match_offsets):
        w = self.width
        text = ed.buffer.line(ln)
        start_off = ed.buffer.line_start(ln)
        tab = ed.tab_width
        left = ed.left_col
        attr_edit = self.attrs["edit"]
        attr_sel = self.attrs["selection"]
        attr_search = self.attrs["search"]
        x = 0
        seg_attr = None
        seg_x = 0
        seg_chars = []

        def flush():
            if seg_chars:
                self._addstr(row, seg_x, "".join(seg_chars), seg_attr)

        for i, ch in enumerate(text):
            width = (tab - (x % tab)) if ch == "\t" else 1
            if x + width <= left or x >= left + w:
                x += width
                continue
            off = start_off + i
            if sel is not None and sel.start <= off < sel.end:
                attr = attr_sel
            elif off in match_offsets:
                attr = attr_search
            else:
                attr = attr_edit
            if attr != seg_attr:
                flush()
                seg_attr = attr
                seg_x = x - left
                seg_chars = []
            seg_chars.append(" " * width if ch == "\t" else ch)
            x += width
        flush()
        if x - left < w:
            self._addstr(row, max(0, x - left), " " * (w - max(0, x - left)), attr_edit)

    def cursor_pos(self, ed):
        line, col = ed.buffer.offset_to_line_col(ed.cursor)
        row = line - ed.top_line + 1
        text = ed.buffer.line(line)
        x = display_col(text, col, ed.tab_width) - ed.left_col
        x = max(0, min(x, self.width - 1))
        row = max(1, min(row, self.height - 2))
        return x, row

    def render_prompt(self, ed, label, text):
        ed.prompt = (label, text)
        self.render(ed)
        ed.prompt = None

    def render_message(self, ed, label, text=""):
        self.render_prompt(ed, label, text)

    # ------------------------------------------------------------------
    # mouse helpers
    # ------------------------------------------------------------------
    def offset_at(self, ed, x, y):
        """Map screen coordinates to a buffer offset (text area only)."""
        if y < 1 or y >= self.height - 1:
            return None
        ln = ed.top_line + (y - 1)
        if ln >= ed.buffer.line_count:
            return len(ed.buffer)
        text = ed.buffer.line(ln)
        dx = x + ed.left_col
        col = col_at_display(text, dx, ed.tab_width)
        return ed.buffer.line_col_to_offset(ln, col)
