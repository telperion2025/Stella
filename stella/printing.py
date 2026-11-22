"""PostScript generation, printing via lpr, and PDF generation via ps2pdf.

Pipeline (per the WSX specification)::

    Text -> PostScript -> lpr        (printing)
    Text -> PostScript -> ps2pdf     (PDF)
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

CHARS_PER_LINE = 80
LINES_PER_PAGE = 54
FONT = "Courier"
FONT_SIZE = 10
MARGIN_X = 54   # 0.75 inch at 72 dpi
MARGIN_Y = 720  # top margin, measured from bottom


def _escape(text):
    """Escape a string for a PostScript literal."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _sanitize(text):
    """Map characters outside Latin-1 to '?' for the PostScript font."""
    return "".join(ch if ord(ch) < 256 else "?" for ch in text)


def generate_postscript(text, title="document", chars_per_line=CHARS_PER_LINE,
                        lines_per_page=LINES_PER_PAGE):
    """Render *text* as a simple paginated PostScript document string."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)] or [[""]]
    out = [
        "%!PS-Adobe-3.0",
        "%%Title: " + _escape(title),
        f"%%Pages: {len(pages)}",
        "%%EndComments",
        f"/Courier findfont {FONT_SIZE} scalefont setfont",
    ]
    for page_no, page_lines in enumerate(pages, 1):
        out.append(f"%%Page: {page_no} {page_no}")
        out.append("gsave")
        y = MARGIN_Y
        for raw in page_lines:
            safe = _sanitize(_escape(raw.rstrip("\n")))[:chars_per_line]
            out.append(f"{MARGIN_X} {y} moveto ({safe}) show")
            y -= FONT_SIZE + 2
        out.append("grestore")
        out.append("showpage")
    out.append("%%EOF")
    return "\n".join(out) + "\n"


def write_postscript(text, path, title="document"):
    """Write PostScript for *text* to *path*; returns the path."""
    path = Path(path)
    path.write_text(generate_postscript(text, title=str(path.stem)), encoding="latin-1")
    return path


def make_temp_postscript(text, title="document"):
    """Write PostScript to a temporary file; returns the file path."""
    fd, name = tempfile.mkstemp(suffix=".ps", prefix="stella-")
    import os
    with os.fdopen(fd, "w", encoding="latin-1") as fh:
        fh.write(generate_postscript(text, title=title))
    return name


def print_postscript(ps_path, printer=None):
    """Send *ps_path* to the printer with lpr.  Returns (ok, message)."""
    if shutil.which("lpr") is None:
        return False, "lpr not found on this system"
    cmd = ["lpr"] + (["-P", printer] if printer else []) + [str(ps_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, "Print job sent (lpr %s)" % ps_path
    err = result.stderr.decode("utf-8", errors="replace").strip()
    return False, err or "lpr failed"


def postscript_to_pdf(ps_path, pdf_path):
    """Convert *ps_path* to *pdf_path* with ps2pdf.  Returns (ok, message)."""
    if shutil.which("ps2pdf") is None:
        return False, "ps2pdf (ghostscript) not found on this system"
    try:
        result = subprocess.run(
            ["ps2pdf", str(ps_path), str(pdf_path)],
            capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if result.returncode == 0 and Path(pdf_path).exists():
        return True, "PDF written to %s" % pdf_path
    err = result.stderr.decode("utf-8", errors="replace").strip()
    return False, err or "ps2pdf failed"
