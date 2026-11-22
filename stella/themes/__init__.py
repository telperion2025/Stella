"""Colour themes for Stella.

Each theme maps a UI element to a ``(foreground, background)`` curses colour
pair, or to a list of curses attributes when the terminal has no colour
support (monochrome fallback using reverse video / bold / underline).
"""

import curses

WORDSTAR = {
    "edit": ("white", "blue"),
    "status": ("bright_white", "blue"),
    "help": ("yellow", "blue"),
    "selection": ("black", "cyan"),
    "search": ("black", "yellow"),
    "error": ("yellow", "red"),
    "message": ("white", "blue"),
}

MONOCHROME = {
    "edit": ["normal"],
    "status": [curses.A_REVERSE | curses.A_BOLD],
    "help": [curses.A_BOLD],
    "selection": [curses.A_REVERSE],
    "search": [curses.A_REVERSE | curses.A_BOLD],
    "error": [curses.A_REVERSE | curses.A_BOLD],
    "message": [curses.A_BOLD],
}

THEMES = {
    "wordstar": WORDSTAR,
    "classic": WORDSTAR,
    "monochrome": MONOCHROME,
}

FOREGROUNDS = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
    "bright_white": curses.COLOR_WHITE | 8,
    "bright_yellow": curses.COLOR_YELLOW | 8,
}


def get_theme(name):
    """Return the theme dict for *name*, falling back to wordstar."""
    return THEMES.get(str(name).lower(), WORDSTAR)
