"""Configuration file handling for Stella.

Configuration is read from ``~/.stellarc`` when present, falling back to
``~/.wsxrc`` as described by the WSX specification.  The file uses simple
``key=value`` lines; blank lines and ``#`` comments are ignored.
"""

from pathlib import Path

DEFAULTS = {
    "default_mode": "wordstar",   # wordstar | vi
    "tab_width": "4",
    "mouse": "true",
    "spellcheck": "false",
    "theme": "wordstar",
    "copy_key": "^C",
    "cut_key": "^W",
    "paste_key": "^V",
}

CONFIG_PATHS = (Path.home() / ".stellarc", Path.home() / ".wsxrc")


def _parse_key_binding(value):
    """Normalise a ``^X`` style binding to the internal ``^X`` token."""
    value = value.strip()
    if len(value) == 2 and value[0] == "^" and value[1].isalpha():
        return "^" + value[1].upper()
    return value.upper()


def load_config(path=None):
    """Load configuration from *path* (or the default locations).

    Returns a dict containing every key in :data:`DEFAULTS`.
    """
    config = dict(DEFAULTS)
    if path is not None:
        candidates = [Path(path)]
    else:
        candidates = list(CONFIG_PATHS)
    for candidate in candidates:
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lower()
            value = value.strip()
            if not key:
                continue
            if key in ("copy_key", "cut_key", "paste_key"):
                value = _parse_key_binding(value)
            config[key] = value
        break
    if config["default_mode"] not in ("wordstar", "vi"):
        config["default_mode"] = "wordstar"
    try:
        config["tab_width"] = max(1, int(config["tab_width"]))
    except (TypeError, ValueError):
        config["tab_width"] = 4
    config["mouse"] = str(config["mouse"]).strip().lower() in ("1", "true", "yes", "on")
    config["spellcheck"] = str(config["spellcheck"]).strip().lower() in ("1", "true", "yes", "on")
    return config
