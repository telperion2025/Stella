"""Editor command processing: WordStar mode, vi modes, and the main loop."""

import curses
import os
from pathlib import Path

from . import blocks, printing
from .buffer import GapBuffer
from .clipboard import Clipboard
from .config import DEFAULTS
from .help import HelpViewer
from .screen import Screen, display_col
from .search import SearchState, replace_all, replace_one
from .undo import UndoHistory

WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _is_word(ch):
    return ch in WORD_CHARS


class Editor:
    def __init__(self, stdscr, filename=None, text="", config=None):
        self.config = dict(DEFAULTS, **(config or {}))
        self.screen = Screen(stdscr, self.config)
        self.buffer = GapBuffer(text)
        self.filename = filename
        self.modified = False
        self.cursor = 0
        self.top_line = 0
        self.left_col = 0
        self.insert_mode = True
        self.mode = "wordstar" if self.config.get("default_mode", "wordstar") == "wordstar" else "normal"
        self.selection = None
        self.clipboard = Clipboard(use_system=True)
        self.history = UndoHistory()
        self.search = SearchState()
        self.message = ""
        self.message_is_error = False
        self.running = False
        self.pending = None      # WordStar prefix: 'K', 'Q' or 'B'
        self.vi_pending = None   # pending vi operator: 'd' or 'y'
        self.prompt = None       # (label, text) while prompting
        self.dragging = False
        self.block_active = False   # a WordStar block mark survives cursor moves
        self.block_end_set = False  # whether ^B E was pressed after ^B B

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @property
    def tab_width(self):
        return self.config.get("tab_width", 4)

    def mode_label(self):
        return {"wordstar": "WORDSTAR", "normal": "NORMAL", "insert": "INSERT",
                "visual": "VISUAL"}.get(self.mode, self.mode.upper())

    def set_message(self, text, error=False):
        self.message = text
        self.message_is_error = error

    def clamp_cursor(self):
        self.cursor = max(0, min(self.cursor, len(self.buffer)))

    def line_col(self):
        return self.buffer.offset_to_line_col(self.cursor)

    def ensure_visible(self):
        h, w = self.screen.height, self.screen.width
        text_rows = max(1, h - 2)
        line, col = self.line_col()
        if line < self.top_line:
            self.top_line = line
        elif line >= self.top_line + text_rows:
            self.top_line = line - text_rows + 1
        self.top_line = max(0, min(self.top_line, max(0, self.buffer.line_count - text_rows)))
        x = display_col(self.buffer.line(line), col, self.tab_width)
        if x < self.left_col:
            self.left_col = x
        elif x >= self.left_col + (w - 1):
            self.left_col = x - (w - 1) + 1
        self.left_col = max(0, self.left_col)

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------
    def run(self):
        self.running = True
        try:
            while self.running:
                self.ensure_visible()
                self.screen.render(self)
                kind, val = self.screen.read_key()
                if kind == "none":
                    continue
                if kind == "key" and val == "RESIZE":
                    self.screen.resize()
                    continue
                self.handle(kind, val)
        finally:
            self.screen.leave()

    def handle(self, kind, val):
        if kind == "mouse":
            self.on_mouse(val)
            return
        if kind == "key" and val == "F1":
            self.show_help()
            return
        if kind == "key" and val == "F2":
            self.toggle_mode()
            return
        if self.mode == "wordstar":
            self.ws_key(kind, val)
        elif self.mode == "normal":
            self.vi_normal(kind, val)
        elif self.mode == "insert":
            self.vi_insert(kind, val)
        elif self.mode == "visual":
            self.vi_visual(kind, val)

    # ------------------------------------------------------------------
    # movement
    # ------------------------------------------------------------------
    def set_cursor(self, offset, extend=False):
        self.clamp_cursor()
        offset = max(0, min(offset, len(self.buffer)))
        if extend:
            if self.selection is None:
                self.selection = blocks.Selection(self.cursor, offset)
            else:
                self.selection.cursor = offset
        else:
            if not self.dragging and not self.block_active:
                self.selection = None
        self.cursor = offset
        self.clamp_cursor()

    def move_lines(self, delta, extend=False):
        line, col = self.line_col()
        self.set_cursor(self.buffer.line_col_to_offset(line + delta, col), extend=extend)

    def move_cols(self, delta, extend=False):
        self.set_cursor(self.cursor + delta, extend=extend)

    def page(self, direction, extend=False):
        rows = max(1, self.screen.height - 2)
        self.move_lines(direction * rows, extend=extend)

    def half_page(self, direction, extend=False):
        rows = max(1, (self.screen.height - 2) // 2)
        self.move_lines(direction * rows, extend=extend)

    def scroll(self, delta):
        self.top_line = max(0, min(self.top_line + delta,
                                   max(0, self.buffer.line_count - max(1, self.screen.height - 2))))

    def beginning_of_line(self, extend=False):
        line, _col = self.line_col()
        self.set_cursor(self.buffer.line_start(line), extend=extend)

    def end_of_line(self, extend=False):
        line, _col = self.line_col()
        self.set_cursor(self.buffer.line_start(line) + self.buffer.line_length(line), extend=extend)

    def first_non_blank(self, extend=False):
        line, _col = self.line_col()
        text = self.buffer.line(line)
        col = 0
        while col < len(text) and text[col] in " \t":
            col += 1
        self.set_cursor(self.buffer.line_col_to_offset(line, col), extend=extend)

    def beginning_of_file(self, extend=False):
        self.set_cursor(0, extend=extend)

    def end_of_file(self, extend=False):
        self.set_cursor(len(self.buffer), extend=extend)

    def next_word(self, extend=False):
        n = len(self.buffer)
        i = self.cursor
        while i < n and _is_word(self.buffer.char_at(i)):
            i += 1
        while i < n and not _is_word(self.buffer.char_at(i)):
            i += 1
        self.set_cursor(i, extend=extend)

    def prev_word(self, extend=False):
        i = self.cursor
        while i > 0 and not _is_word(self.buffer.char_at(i - 1)):
            i -= 1
        while i > 0 and _is_word(self.buffer.char_at(i - 1)):
            i -= 1
        self.set_cursor(i, extend=extend)

    def end_of_word(self, extend=False):
        n = len(self.buffer)
        i = self.cursor
        if i < n and not _is_word(self.buffer.char_at(i)):
            while i < n and not _is_word(self.buffer.char_at(i)):
                i += 1
        while i < n and _is_word(self.buffer.char_at(i)):
            i += 1
        self.set_cursor(max(i - 1, 0) if i < n else n, extend=extend)

    # ------------------------------------------------------------------
    # editing primitives (all go through the undo history)
    # ------------------------------------------------------------------
    def apply_edit(self, pos, delete_len, insert_text, cursor=None):
        deleted = self.buffer.slice(pos, pos + delete_len) if delete_len else ""
        if delete_len:
            self.buffer.delete(pos, delete_len)
        if insert_text:
            self.buffer.insert(pos, insert_text)
        self.history.push(pos, deleted, insert_text)
        self.modified = True
        self.cursor = pos + len(insert_text) if cursor is None else cursor
        self.clamp_cursor()
        if not self.block_active:
            self.selection = None
        self.search.matches = []  # match offsets are stale after an edit
        self.search.index = -1

    def insert_text(self, s):
        if self.insert_mode or self.cursor >= len(self.buffer):
            self.apply_edit(self.cursor, 0, s)
        else:
            ch = self.buffer.char_at(self.cursor)
            if ch == "\n":
                self.apply_edit(self.cursor, 0, s)
            else:
                self.apply_edit(self.cursor, 1, s)

    def backspace(self):
        if self.selection is not None and len(self.selection) > 0 and self.mode == "wordstar":
            self.cut_selection()
            return
        if self.cursor > 0:
            self.apply_edit(self.cursor - 1, 1, "", cursor=self.cursor - 1)

    def delete_char(self):
        if self.selection is not None and len(self.selection) > 0 and self.mode == "wordstar":
            self.delete_selection()
            return
        if self.cursor < len(self.buffer):
            self.apply_edit(self.cursor, 1, "")

    def delete_line(self):
        line, _col = self.line_col()
        start = self.buffer.line_start(line)
        end = start + self.buffer.line_length(line)
        if line + 1 < self.buffer.line_count:
            end += 1  # include the newline
            yank = self.buffer.line(line) + "\n"
        elif line > 0:
            start -= 1  # no next line: remove the preceding newline instead
            yank = self.buffer.line(line) + "\n"
        else:
            yank = self.buffer.line(line)
        if end > start:
            self.apply_edit(start, end - start, "", cursor=start)
            self.clipboard.copy(yank)

    def open_line(self, below=True):
        line, _col = self.line_col()
        if below:
            pos = self.buffer.line_start(line) + self.buffer.line_length(line)
            self.apply_edit(pos, 0, "\n", cursor=pos + 1)
        else:
            pos = self.buffer.line_start(line)
            self.apply_edit(pos, 0, "\n", cursor=pos)

    def undo(self):
        pos = self.history.undo(self.buffer)
        self.search.matches = []
        self.search.index = -1
        if pos is None:
            self.set_message("Nothing to undo", error=True)
        else:
            self.modified = True
            self.cursor = pos
            self.selection = None
            self.set_message("Undo")

    def redo(self):
        pos = self.history.redo(self.buffer)
        self.search.matches = []
        self.search.index = -1
        if pos is None:
            self.set_message("Nothing to redo", error=True)
        else:
            self.modified = True
            self.cursor = pos
            self.selection = None
            self.set_message("Redo")

    # ------------------------------------------------------------------
    # selection / clipboard / block operations
    # ------------------------------------------------------------------
    def copy_selection(self):
        if self.selection is None or len(self.selection) == 0:
            self.set_message("No block marked", error=True)
            return
        blocks.copy_selection(self.buffer, self.selection, self.clipboard)
        self.set_message("Copied %d characters" % len(self.selection))

    def cut_selection(self):
        if self.selection is None or len(self.selection) == 0:
            self.set_message("No block marked", error=True)
            return
        text = blocks.selected_text(self.buffer, self.selection)
        start = self.selection.start
        self.clipboard.copy(text)
        self.apply_edit(start, len(self.selection), "", cursor=start)
        self.selection = None
        self.block_active = False
        self.set_message("Cut %d characters" % len(text))

    def delete_selection(self):
        if self.selection is None or len(self.selection) == 0:
            self.set_message("No block marked", error=True)
            return
        start = self.selection.start
        self.apply_edit(start, len(self.selection), "", cursor=start)
        self.selection = None
        self.block_active = False
        self.set_message("Block deleted")

    def paste(self, after=False):
        text = self.clipboard.paste()
        if not text:
            self.set_message("Clipboard empty", error=True)
            return
        if self.selection is not None and len(self.selection) > 0 and not after:
            start = self.selection.start
            self.apply_edit(start, len(self.selection), text, cursor=start + len(text))
            self.selection = None
            self.block_active = False
        else:
            pos = self.cursor
            if after:
                if text.endswith("\n"):
                    line, _col = self.line_col()
                    eol = self.buffer.line_start(line) + self.buffer.line_length(line)
                    pos = eol + 1 if eol < len(self.buffer) else len(self.buffer)
                elif self.cursor < len(self.buffer) and self.buffer.char_at(self.cursor) != "\n":
                    pos = self.cursor + 1
            self.apply_edit(pos, 0, text)
        self.set_message("Pasted %d characters" % len(text))

    def move_block(self):
        if self.selection is None or len(self.selection) == 0:
            self.set_message("No block marked", error=True)
            return
        dest = self.cursor
        sel = self.selection
        if sel.start <= dest <= sel.end:
            self.set_message("Destination is inside the block", error=True)
            return
        text = blocks.selected_text(self.buffer, sel)
        start, end = sel.start, sel.end
        self.apply_edit(start, end - start, "", cursor=start)
        if dest > start:
            dest -= end - start
        self.apply_edit(dest, 0, text, cursor=dest + len(text))
        self.selection = None
        self.set_message("Block moved")

    def duplicate_block(self):
        if self.selection is None or len(self.selection) == 0:
            self.set_message("No block marked", error=True)
            return
        sel = self.selection
        text = blocks.duplicate_selection(self.buffer, sel)
        self.history.push(sel.end, "", text)
        self.modified = True
        self.selection = blocks.Selection(sel.end, sel.end + len(text))
        self.set_message("Block duplicated")

    # ------------------------------------------------------------------
    # search / replace
    # ------------------------------------------------------------------
    def prompt_find(self, vi_style=False):
        label = "/" if vi_style else "Find: "
        q = self.screen.read_line(label, default=self.search.query,
                                  render=lambda l, t: self.screen.render_prompt(self, l, t))
        if q is None or q == "":
            return
        self.search.set_query(q, self.buffer.text)
        start = self.cursor + 1 if (self.selection is not None and len(self.selection) > 0) else self.cursor
        match = self.search.next(self.buffer.text, start)
        if match is None:
            self.set_message("Not found: %s" % q, error=True)
        else:
            self.cursor = match[0]
            self.selection = blocks.Selection(match[0], match[1])
            self.set_message("Found (%d match%s)" % (len(self.search.matches),
                                                     "es" if len(self.search.matches) != 1 else ""))

    def repeat_search(self, backwards=False):
        if not self.search.query:
            self.set_message("No previous search", error=True)
            return
        if backwards:
            match = self.search.prev(self.buffer.text, self.cursor)
        else:
            start = self.cursor + 1 if (self.selection is not None and len(self.selection) > 0) else self.cursor
            match = self.search.next(self.buffer.text, start)
        if match is None:
            self.set_message("Not found: %s" % self.search.query, error=True)
        else:
            self.cursor = match[0]
            self.selection = blocks.Selection(match[0], match[1])

    def prompt_replace(self):
        q = self.screen.read_line("Find: ", default=self.search.query,
                                  render=lambda l, t: self.screen.render_prompt(self, l, t))
        if q is None or q == "":
            return
        r = self.screen.read_line("Replace with: ", default=self.search.replacement,
                                  render=lambda l, t: self.screen.render_prompt(self, l, t))
        if r is None:
            return
        self.search.replacement = r
        all_answer = self.screen.read_line("Replace all occurrences? (y/n): ",
                                           render=lambda l, t: self.screen.render_prompt(self, l, t))
        if all_answer is None:
            return
        if all_answer.strip().lower().startswith("y"):
            new_text, count = replace_all(self.buffer.text, q, r, self.search.case_sensitive)
            if count:
                self.apply_edit(0, len(self.buffer), new_text, cursor=0)
                self.set_message("Replaced %d occurrence%s" % (count, "s" if count != 1 else ""))
            else:
                self.set_message("Not found: %s" % q, error=True)
        else:
            new_text, s, e, count = replace_one(self.buffer.text, q, r, self.cursor, self.search.case_sensitive)
            if count:
                self.apply_edit(s, len(q), r, cursor=e)
                self.search.set_query(q, self.buffer.text)
                self.set_message("Replaced 1 occurrence")
            else:
                self.set_message("Not found: %s" % q, error=True)

    # ------------------------------------------------------------------
    # file commands
    # ------------------------------------------------------------------
    def save(self):
        if not self.filename:
            return self.save_as()
        try:
            Path(self.filename).write_text(self.buffer.text, encoding="utf-8")
        except OSError as exc:
            self.set_message("Save failed: %s" % exc, error=True)
            return False
        self.modified = False
        self.set_message("Saved %s" % self.filename)
        return True

    def save_as(self):
        name = self.screen.read_line("Save as: ", default=self.filename or "",
                                     render=lambda l, t: self.screen.render_prompt(self, l, t))
        if name is None or name.strip() == "":
            return False
        self.filename = os.path.expanduser(name.strip())
        return self.save()

    def quit(self, force=False):
        if self.modified and not force:
            ans = self.screen.read_yes_no(
                "Discard unsaved changes and quit? (y/n) ",
                render=lambda l, t: self.screen.render_prompt(self, l, t))
            if not ans:
                self.set_message("Quit cancelled")
                return
        self.running = False

    def save_and_exit(self):
        if self.save():
            self.running = False

    def print_menu(self):
        choice = self.screen.read_line(
            "Output: [P]rint via lpr, P[D]F via ps2pdf: ",
            render=lambda l, t: self.screen.render_prompt(self, l, t))
        if choice is None:
            return
        choice = choice.strip().lower()
        title = os.path.basename(self.filename) if self.filename else "document"
        ps_path = printing.make_temp_postscript(self.buffer.text, title=title)
        try:
            if choice.startswith("d"):
                default = (os.path.splitext(title)[0] or "document") + ".pdf"
                out = self.screen.read_line("PDF file: ", default=default,
                                            render=lambda l, t: self.screen.render_prompt(self, l, t))
                if out is None or out.strip() == "":
                    self.set_message("PDF cancelled")
                    return
                ok, msg = printing.postscript_to_pdf(ps_path, os.path.expanduser(out.strip()))
            else:
                ok, msg = printing.print_postscript(ps_path)
        finally:
            try:
                os.unlink(ps_path)
            except OSError:
                pass
        self.set_message(msg, error=not ok)

    # ------------------------------------------------------------------
    # help / mode switching
    # ------------------------------------------------------------------
    def show_help(self):
        HelpViewer(self.screen).run()

    def toggle_mode(self):
        if self.mode == "wordstar":
            self.mode = "normal"
            self.selection = None
            self.set_message("vi mode: NORMAL")
        else:
            self.mode = "wordstar"
            self.selection = None
            self.insert_mode = True
            self.set_message("WordStar mode")

    # ------------------------------------------------------------------
    # mouse
    # ------------------------------------------------------------------
    def on_mouse(self, ev):
        x, y, bstate = ev
        b1 = curses.BUTTON1_PRESSED | getattr(curses, "BUTTON1_CLICKED", 0)
        b1_release = getattr(curses, "BUTTON1_RELEASED", 0)
        motion = curses.REPORT_MOUSE_POSITION
        wheel_up = curses.BUTTON4_PRESSED
        wheel_down = getattr(curses, "BUTTON5_PRESSED", wheel_up << 1)
        if bstate & wheel_up:
            self.scroll(-3)
            return
        if bstate & wheel_down:
            self.scroll(3)
            return
        if bstate & b1:
            off = self.screen.offset_at(self, x, y)
            if off is None:
                return
            self.dragging = True
            self.cursor = off
            self.selection = blocks.Selection(off)
            self.clamp_cursor()
            return
        if (bstate & motion) and self.dragging:
            off = self.screen.offset_at(self, x, y)
            if off is not None:
                self.selection.cursor = off
                self.cursor = off
            return
        if bstate & b1_release:
            self.dragging = False
            off = self.screen.offset_at(self, x, y)
            if off is not None and self.selection is not None:
                if self.selection.start == self.selection.end:
                    self.selection = None
                self.cursor = off

    # ------------------------------------------------------------------
    # WordStar mode
    # ------------------------------------------------------------------
    def ws_key(self, kind, val):
        copy_key = self.config.get("copy_key", "^C")
        cut_key = self.config.get("cut_key", "^W")
        paste_key = self.config.get("paste_key", "^V")
        if self.pending is not None:
            prefix, self.pending = self.pending, None
            self.ws_prefix(prefix, kind, val)
            return
        if kind == "ctrl":
            token = "^" + val
            has_sel = self.selection is not None and len(self.selection) > 0
            # Clipboard shortcuts win over navigation when a block/selection
            # is active (^C and ^W are also page/scroll keys per the spec,
            # so without a selection they keep their navigation meaning).
            if token == paste_key:
                self.paste()
            elif has_sel and token == copy_key:
                self.copy_selection()
            elif has_sel and token == cut_key:
                self.cut_selection()
            elif val in ("E", "X", "S", "D"):
                self.move_lines({"E": -1, "X": 1}.get(val, 0) or 0)
                if val in ("S", "D"):
                    self.move_cols(-1 if val == "S" else 1)
            elif val == "A":
                self.prev_word()
            elif val == "F":
                self.next_word()
            elif val == "R":
                self.page(-1)
            elif val == "C":
                self.page(1)
            elif val == "W":
                self.scroll(-1)
            elif val == "Z":
                self.scroll(1)
            elif val == "Q":
                self.pending = "Q"
            elif val == "K":
                self.pending = "K"
            elif val == "B":
                self.pending = "B"
            elif val == "L":
                self.repeat_search()
            elif val == "U":
                self.undo()
            elif val == "Y":
                self.redo()
        elif kind == "key":
            if val == "UP":
                self.move_lines(-1)
            elif val == "DOWN":
                self.move_lines(1)
            elif val == "LEFT":
                self.move_cols(-1)
            elif val == "RIGHT":
                self.move_cols(1)
            elif val == "PPAGE":
                self.page(-1)
            elif val == "NPAGE":
                self.page(1)
            elif val == "HOME":
                self.beginning_of_line()
            elif val == "END":
                self.end_of_line()
            elif val == "INS":
                self.insert_mode = not self.insert_mode
            elif val == "BS":
                self.backspace()
            elif val == "DEL":
                self.delete_char()
            elif val == "ENTER":
                self.insert_text("\n")
            elif val == "TAB":
                self.insert_text("\t")
        elif kind == "char":
            self.insert_text(val)

    def ws_prefix(self, prefix, kind, val):
        if kind == "char":
            ch = val.upper()
        elif kind == "ctrl":
            ch = "^" + val
        else:
            ch = val
        if prefix == "K":
            if ch == "S":
                self.save()
            elif ch == "D":
                self.save_as()
            elif ch == "X":
                self.save_and_exit()
            elif ch == "Q":
                self.quit()
            elif ch == "P":
                self.print_menu()
            elif ch == "H":
                self.show_help()
            elif ch == "M":
                self.toggle_mode()
            else:
                self.set_message("Unknown ^K command: %s" % ch, error=True)
        elif prefix == "Q":
            if ch == "S":
                self.beginning_of_line()
            elif ch == "D":
                self.end_of_line()
            elif ch == "R":
                self.beginning_of_file()
            elif ch == "C":
                self.end_of_file()
            elif ch == "F":
                self.prompt_find()
            elif ch == "A":
                self.prompt_replace()
            else:
                self.set_message("Unknown ^Q command: %s" % ch, error=True)
        elif prefix == "B":
            if ch == "B":
                self.block_active = True
                self.block_end_set = False
                self.selection = blocks.Selection(self.cursor)
                self.set_message("Block begin marked")
            elif ch == "E":
                if self.selection is None:
                    self.selection = blocks.Selection(self.cursor)
                self.block_active = True
                self.block_end_set = True
                self.selection.cursor = self.cursor
                self.set_message("Block end marked (%d chars)" % len(self.selection))
            elif ch in ("C", "M", "D"):
                # with only ^B B marked, the cursor is the implicit block end
                if self.selection is not None and not self.block_end_set:
                    self.selection.cursor = self.cursor
                if ch == "C":
                    self.copy_selection()
                elif ch == "M":
                    self.move_block()
                else:
                    self.delete_selection()
                self.block_active = False
                self.block_end_set = False
            elif ch == "V":
                self.paste()
                self.selection = None
                self.block_active = False
                self.block_end_set = False
            elif ch == "U":
                self.selection = None
                self.block_active = False
                self.block_end_set = False
                self.set_message("Block unmarked")
            else:
                self.set_message("Unknown ^B command: %s" % ch, error=True)

    # ------------------------------------------------------------------
    # vi modes
    # ------------------------------------------------------------------
    def vi_motion(self, kind, val, extend=False):
        if kind == "char":
            c = val
            if c == "h":
                self.move_cols(-1, extend=extend)
            elif c == "l":
                self.move_cols(1, extend=extend)
            elif c == "j":
                self.move_lines(1, extend=extend)
            elif c == "k":
                self.move_lines(-1, extend=extend)
            elif c == "w":
                self.next_word(extend=extend)
            elif c == "b":
                self.prev_word(extend=extend)
            elif c == "e":
                self.end_of_word(extend=extend)
            elif c == "0":
                self.beginning_of_line(extend=extend)
            elif c == "^":
                self.first_non_blank(extend=extend)
            elif c == "$":
                self.end_of_line(extend=extend)
            else:
                return False
            return True
        if kind == "key":
            if val == "LEFT":
                self.move_cols(-1, extend=extend)
            elif val == "RIGHT":
                self.move_cols(1, extend=extend)
            elif val == "DOWN":
                self.move_lines(1, extend=extend)
            elif val == "UP":
                self.move_lines(-1, extend=extend)
            elif val == "PPAGE":
                self.page(-1, extend=extend)
            elif val == "NPAGE":
                self.page(1, extend=extend)
            elif val == "HOME":
                self.beginning_of_line(extend=extend)
            elif val == "END":
                self.end_of_line(extend=extend)
            else:
                return False
            return True
        return False

    def vi_normal(self, kind, val):
        copy_key = "^" + "C"
        if kind == "char" and val == ":":
            self.vi_command_line()
            return
        if kind == "char" and val == "/":
            self.prompt_find(vi_style=True)
            return
        if self.vi_pending is not None:
            op, self.vi_pending = self.vi_pending, None
            if kind == "char" and val == op:
                if op == "d":
                    self.delete_line()
                elif op == "y":
                    line, _col = self.line_col()
                    text = self.buffer.line(line) + "\n"
                    self.clipboard.copy(text)
                    self.set_message("Yanked line")
            return
        if self.vi_motion(kind, val):
            return
        if kind == "ctrl":
            if val == "F":
                self.page(1)
            elif val == "B":
                self.page(-1)
            elif val == "D":
                self.half_page(1)
            elif val == "U":
                self.half_page(-1)
            elif val == "R":
                self.redo()
            elif "^" + val == self.config.get("copy_key", copy_key):
                self.copy_selection()
            elif "^" + val == self.config.get("cut_key", "^W"):
                self.cut_selection()
            elif "^" + val == self.config.get("paste_key", "^V"):
                self.paste()
            return
        if kind == "key":
            if val == "INS":
                self.mode = "insert"
            elif val == "ENTER":
                self.move_lines(1)
            elif val == "BS":
                self.move_cols(-1)
            elif val == "DEL":
                self.delete_char()
            return
        if kind == "char":
            c = val
            if c == "x":
                self.delete_char()
            elif c == "d":
                self.vi_pending = "d"
            elif c == "y":
                self.vi_pending = "y"
            elif c == "p":
                self.paste()
            elif c == "u":
                self.undo()
            elif c == "n":
                self.repeat_search()
            elif c == "N":
                self.repeat_search(backwards=True)
            elif c == "i":
                self.mode = "insert"
            elif c == "I":
                self.beginning_of_line()
                self.first_non_blank()
                self.mode = "insert"
            elif c == "a":
                self.move_cols(1)
                self.mode = "insert"
            elif c == "A":
                self.end_of_line()
                self.mode = "insert"
            elif c == "o":
                self.open_line(below=True)
                self.mode = "insert"
            elif c == "O":
                self.open_line(below=False)
                self.mode = "insert"
            elif c == "v":
                self.mode = "visual"
                if self.selection is None:
                    self.selection = blocks.Selection(self.cursor, inclusive=True)
                else:
                    self.selection.inclusive = True
                    self.selection.cursor = self.cursor
            elif c == "V":
                self.mode = "visual"
                line, _col = self.line_col()
                start = self.buffer.line_start(line)
                end = start + self.buffer.line_length(line)
                if line + 1 < self.buffer.line_count:
                    end += 1
                self.selection = blocks.Selection(start, end)
                self.cursor = end

    def vi_insert(self, kind, val):
        if kind == "key" and val == "ESC":
            self.mode = "normal"
            self.selection = None
            if self.cursor > 0:
                self.cursor -= 1
            return
        if kind == "key":
            if val == "INS":
                self.insert_mode = not self.insert_mode  # vi overwrite toggle
            elif val == "BS":
                self.backspace()
            elif val == "DEL":
                self.delete_char()
            elif val == "ENTER":
                self.insert_text("\n")
            elif val == "TAB":
                self.insert_text("\t")
            else:
                self.vi_motion(kind, val)
            return
        if kind == "ctrl":
            if "^" + val == self.config.get("paste_key", "^V"):
                self.paste()
            return
        if kind == "char":
            self.insert_text(val)

    def vi_visual(self, kind, val):
        if kind == "key" and val == "ESC":
            self.mode = "normal"
            if self.selection is not None:
                self.selection.inclusive = False
            return
        if kind == "char" and val == "d":
            self.cut_selection()
            self.mode = "normal"
            return
        if kind == "char" and val == "y":
            self.copy_selection()
            self.mode = "normal"
            return
        if kind == "char" and val == "V":
            line, _col = self.line_col()
            self.selection.inclusive = False
            self.selection.cursor = self.buffer.line_start(line) + self.buffer.line_length(line)
            return
        self.vi_motion(kind, val, extend=True)

    def vi_command_line(self):
        line = self.screen.read_line(":", render=lambda l, t: self.screen.render_prompt(self, l, t))
        if line is None:
            return
        cmd = line.strip()
        if cmd in ("q", "q!"):
            self.quit(force=cmd.endswith("!"))
        elif cmd in ("w", "x", "wq") or cmd.startswith("w "):
            if cmd.startswith("w "):
                self.filename = os.path.expanduser(cmd[2:].strip())
            if self.save():
                if cmd in ("wq", "x"):
                    self.running = False
        elif cmd == "":
            return
        else:
            self.set_message("Unknown command: %s" % cmd, error=True)
