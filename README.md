# Stella

Stella is a classic **WordStar-inspired console text editor** written in Python 3,
implementing the WSX v1.0 specification (see the Software Requirements
Specification and WSX Specification documents). It combines WordStar's
control-key command philosophy with selected vi modal editing and modern
expectations (highlighted selection, clipboard, undo/redo, UTF-8, mouse).

## Requirements

- Python 3.8+
- A Unix-like terminal (Linux, macOS, FreeBSD, OpenBSD, NetBSD) with `curses`
- Optional, for system clipboard: `xclip` / `xsel` / `wl-copy` (Linux) or
  `pbcopy` / `pbpaste` (macOS)
- Optional, for printing/PDF: `lpr` and `ps2pdf` (ghostscript)

No third-party Python packages are required.

## Running

```sh
python -m stella document.txt      # from a source checkout
stella document.txt                # after pip install .
stella --mode vi document.txt      # start in vi mode
```

Files are read/written as UTF-8 (ASCII compatible); `.txt`, `.asc` and
`.text` are the intended formats.

## Features (Version 1 checklist)

- Full-screen editing with a **gap buffer** (efficient insert/delete, files of
  several megabytes)
- **WordStar mode** (default): cursor diamond `^E ^X ^S ^D`, `^A`/`^F` word
  movement, `^R`/`^C`/`^W`/`^Z` scrolling, `^Q S/D/R/C/F/A`, `^L`, and the
  `^K` (files) and `^B` (block) command prefixes
- **vi mode**: normal / insert / visual / command modes (`h j k l`, `w b e`,
  `0 ^ $`, `dd`, `yy`, `p`, `u`, `Ctrl-R`, `/`, `n`, `N`, `i I a A o O`,
  `v`/`V`, `:w :q :wq :q!`); switch modes at any time with `F2`
- **Unified selection** (WordStar block, vi visual, keyboard, mouse drag) with
  highlighting — black on cyan on colour terminals, reverse video on monochrome
- **Clipboard**: internal clipboard always available, system clipboard when
  possible; default shortcuts `^C` copy, `^W` cut, `^V` paste (configurable)
- **Search and replace**: find, find next (`^L`), replace, replace all
- **Multi-level undo/redo** (command history stack)
- **WordStar Classic theme**: white on dark blue, bright-white status line,
  yellow help line, black-on-cyan selection, black-on-yellow search matches,
  yellow-on-red errors; proper terminal restoration on exit
- **Help system** on `F1` or `^K H` (WordStar/vi/selection/clipboard/search/
  printing/configuration topics), navigable with arrows, PgUp/PgDn, Esc
- **Printing**: text → PostScript → `lpr`; **PDF**: text → PostScript →
  `ps2pdf` (`^K P`)
- **Mouse support**: cursor positioning, drag selection, scroll wheel
- **Configuration** via `~/.stellarc` (falling back to `~/.wsxrc`):
  `default_mode`, `tab_width`, `mouse`, `spellcheck`, `theme`, and the
  clipboard key bindings

## Layout

```
stella/
├── main.py        entry point / argument parsing
├── commands.py    editor command processing (WordStar + vi modes)
├── screen.py      curses rendering, input, mouse
├── buffer.py      gap buffer
├── blocks.py      unified selection / block operations
├── clipboard.py   internal + system clipboard
├── search.py      find / replace
├── undo.py        undo/redo history
├── help.py        help viewer
├── printing.py    PostScript / lpr / ps2pdf
├── config.py      ~/.stellarc / ~/.wsxrc
├── themes/        colour themes
└── help/          help topics
```

## Tests

```sh
python -m unittest discover -s tests -v   # unit tests (buffer, search, undo, ...)
python3 tests/pty_smoke.py                # end-to-end smoke test driving the real
                                          # curses UI through a pseudo-terminal
```
