"""Stella entry point."""

import argparse
import curses
import locale
import sys
from pathlib import Path

from .commands import Editor
from .config import load_config
from .screen import disable_tty_flow_control


def main(argv=None):
    locale.setlocale(locale.LC_ALL, "")
    parser = argparse.ArgumentParser(
        prog="stella",
        description="Stella - a WordStar-inspired console text editor (WSX v1.0)")
    parser.add_argument("file", nargs="?", help="text file to open (.txt/.asc/.text, UTF-8)")
    parser.add_argument("--mode", choices=["wordstar", "vi"],
                        help="startup editing mode (overrides the config file)")
    parser.add_argument("--config", help="path to a configuration file (default: ~/.stellarc, ~/.wsxrc)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if args.mode:
        config["default_mode"] = args.mode

    text = ""
    if args.file:
        try:
            text = Path(args.file).read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            text = ""  # new file: vi-style, created on first save
        except OSError as exc:
            print("stella: cannot open %s: %s" % (args.file, exc), file=sys.stderr)
            return 1

    # Disable tty flow control before curses starts so ^S/^Q/^C are never
    # consumed by the line discipline, even during startup.
    disable_tty_flow_control()

    def _run(stdscr):
        editor = Editor(stdscr, filename=args.file, text=text, config=config)
        editor.run()

    try:
        curses.wrapper(_run)
    except curses.error as exc:
        print("stella: cannot start the full-screen editor on this terminal: %s" % exc,
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
