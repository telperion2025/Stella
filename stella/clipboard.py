"""Clipboard handling: always-available internal clipboard plus optional
system clipboard integration via xclip / xsel / wl-copy (Linux) or
pbcopy / pbpaste (macOS)."""

import platform
import shutil
import subprocess

_SET_COMMANDS = {
    "xclip": ["xclip", "-selection", "clipboard"],
    "xsel": ["xsel", "--clipboard", "--input"],
    "wl-copy": ["wl-copy"],
    "pbcopy": ["pbcopy"],
}

_GET_COMMANDS = {
    "xclip": ["xclip", "-selection", "clipboard", "-o"],
    "xsel": ["xsel", "--clipboard", "--output"],
    "wl-paste": ["wl-paste", "--no-newline"],
    "pbpaste": ["pbpaste"],
}


class Clipboard:
    def __init__(self, use_system=True):
        self.internal = ""
        self.use_system = use_system
        self._tool = None
        self._source = "internal"   # which store holds the latest copy
        if use_system:
            self._tool = self._detect_tool()

    @staticmethod
    def _detect_tool():
        system = platform.system()
        candidates = ["pbcopy"] if system == "Darwin" else ["xclip", "xsel", "wl-copy"]
        for name in candidates:
            if shutil.which(name):
                return name
        return None

    @property
    def system_available(self):
        return self._tool is not None

    def copy(self, text):
        """Store *text* in the internal clipboard and, when available, the
        system clipboard.  Tracks which store holds the latest copy."""
        self.internal = text
        self._source = "internal"
        if self._tool and self.use_system:
            cmd = _SET_COMMANDS[self._tool]
            try:
                result = subprocess.run(
                    cmd, input=text.encode("utf-8"),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=5, check=False,
                )
                if result.returncode == 0:
                    self._source = "system"
            except (OSError, subprocess.SubprocessError):
                pass

    def paste(self):
        """Return the latest clipboard contents: the system clipboard when
        the last copy landed there, otherwise the internal clipboard."""
        if self._source == "system" and self._tool and self.use_system:
            get_tool = {"pbcopy": "pbpaste"}.get(self._tool, self._tool.replace("copy", "paste"))
            cmd = _GET_COMMANDS.get(get_tool)
            if cmd:
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, timeout=5, check=False,
                    )
                    if result.returncode == 0 and result.stdout:
                        return result.stdout.decode("utf-8", errors="replace")
                except (OSError, subprocess.SubprocessError):
                    pass
        return self.internal
