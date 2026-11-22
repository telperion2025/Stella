# WSX v1.0 spec coverage map

Where each requirement from the *WSX Specification v1.0* and the *Software
Requirements Specification v1.0* is implemented in Stella.

| Spec section | Requirement | Implementation |
|---|---|---|
| §3 / SRS 3.1-3.2 | Python 3, curses/os/sys/pathlib/subprocess/tempfile/shutil only | whole package; stdlib only, `pyproject.toml` has no dependencies |
| §12 / SRS 3.3 | Gap buffer storage, efficient insert/delete, multi-MB files | `stella/buffer.py` (`GapBuffer`, two-string gap + incremental line index); `tests/test_buffer.py` incl. 20k-line file |
| §5 / SRS 4 | Status line: filename, modified `*`, Ln, Col, INS/OVR, mode | `Screen.render` in `stella/screen.py` |
| §6 / SRS 4.3-4.4 | WordStar Classic theme; monochrome fallback (reverse/bold/underline) | `stella/themes/__init__.py`, colour pairs built in `Screen._init_terminal` |
| §6 / SRS 4.5 | Terminal restoration on exit | `curses.wrapper` in `stella/main.py` + `Screen.leave()` (mouse off, cursor on); IXON/ISIG disabled so `^S`/`^Q`/`^C` reach the editor |
| §7 / SRS 5 | Two modes, default WordStar, switchable, configurable default | `Editor.mode`, `F2` toggle, `^K M`, `default_mode` in `config.py` |
| §8 / SRS 6 | WordStar key map (diamond, word nav, screen, `^Q`, `^K`, `^B`, `^L`) | `Editor.ws_key` / `ws_prefix` in `stella/commands.py` |
| §9 / SRS 7 | vi key map (hjkl, w/b/e, 0/^/$, pages, dd/yy/p/u/Ctrl-R, /, n/N, i/I/a/A/o/O, v/V, :w :q :wq :q!) | `Editor.vi_normal/vi_insert/vi_visual/vi_command_line` |
| §10 / SRS 8 | Unified selection, highlight black-on-cyan, single/multi-line, drag | `stella/blocks.py` `Selection`, render-time highlight in `screen.py`, mouse in `Editor.on_mouse` |
| §11 / SRS 9 | Internal clipboard + system clipboard (xclip/xsel/wl-copy/pbcopy), configurable `^C`/`^W`/`^V` | `stella/clipboard.py`, `copy_key`/`cut_key`/`paste_key` in `config.py` |
| §14 / SRS 10 | Find, find next, replace, replace all (no regex in v1) | `stella/search.py`, `^Q F`, `^L`, `^Q A`, `/` in vi |
| §15 / SRS (blocks) | Block mark/copy/move/duplicate/delete/clear | `^B B/E/C/M/D/U`, `duplicate_block` in `commands.py` |
| §16 / SRS 11 | Multi-level undo/redo, command history stack | `stella/undo.py` (`UndoHistory`), `^U`/`^Y` in WS mode, `u`/`Ctrl-R` in vi |
| §17 / SRS 14 | Help via F1 and `^K H`, 7 topic groups, arrows/PgUp/PgDn/Esc | `stella/help.py` + `stella/help/*.txt` |
| §18 / SRS 12 | Mouse: position, selection, drag, wheel; fully usable without | `curses.mousemask` in `screen.py`, `Editor.on_mouse`; `mouse=false` config |
| §19-20 / SRS 15-16 | PostScript output, `lpr`, PDF via `ps2pdf` | `stella/printing.py`, `^K P` menu |
| §13 / SRS 13 | .txt/.asc/.text, UTF-8/ASCII | `main.py` reads UTF-8 with `errors=replace`, saves UTF-8 |
| §22 / SRS 17 | `~/.wsxrc`-style config: default mode, tab width, mouse, theme, key remapping | `stella/config.py` (`~/.stellarc`, fallback `~/.wsxrc`) |
| §24 / SRS 18 | v1 non-goals respected (no GUI/rich text/macros/...) | — |
| SRS 19.1 | Start < 2 s, multi-MB files, responsive cursor | gap buffer + windowed rendering; only visible lines are drawn |
| SRS 19.2 | No data corruption, unsaved-changes confirmation | `^K Q`/`:q` prompt when `modified`; save errors reported |
| SRS 20 | Acceptance criteria | `tests/pty_smoke.py` (21 PTY checks) + 49 unit tests |

## Verification

```sh
python -m unittest discover -s tests -v   # 49 unit tests
python3 tests/pty_smoke.py                # 21 end-to-end PTY checks
```
