"""Drive stella in a pseudo-terminal and verify end-to-end behaviour."""
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[1])


def run_editor(args, key_sequences, timeout=15):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    env = dict(os.environ)
    env.update(TERM="xterm-256color", LC_ALL="C.UTF-8", LANG="C.UTF-8")
    env["HOME"] = tempfile.mkdtemp(prefix="stella-home-")  # isolate ~/.stellarc
    proc = subprocess.Popen(
        [sys.executable, "-m", "stella"] + args,
        stdin=slave, stdout=slave, stderr=slave, env=env, cwd=REPO, close_fds=True)
    os.close(slave)
    out = b""
    try:
        # wait for the first rendered frame before sending keys, so slow
        # machines never race the tty/curses initialisation
        deadline = time.time() + 15
        while time.time() < deadline and proc.poll() is None:
            r, _, _ = select.select([master], [], [], 0.2)
            if not r:
                continue
            try:
                data = os.read(master, 65536)
            except OSError:
                break
            if not data:
                break
            out += data
            if b"Ln:" in out or b"WORDSTAR" in out or b"NORMAL" in out:
                break
        for keys in key_sequences:
            time.sleep(0.35)
            try:
                os.write(master, keys)
            except OSError:
                break
        deadline = time.time() + timeout
        while time.time() < deadline:
            r, _, _ = select.select([master], [], [], 0.2)
            if r:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                out += data
            if proc.poll() is not None:
                # drain what's left
                while True:
                    r, _, _ = select.select([master], [], [], 0.2)
                    if not r:
                        break
                    try:
                        data = os.read(master, 65536)
                    except OSError:
                        break
                    if not data:
                        break
                    out += data
                break
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        os.close(master)
    return proc.returncode, out


failures = []


def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if not cond:
        failures.append(name)


# --- Test 1: WordStar mode typing + save-and-exit (^K X) -------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("")
    path1 = fh.name
rc, out = run_editor([path1], [b"Hello Stella!\nSecond line.", b"\x0bX"])  # ^K X
content = open(path1, encoding="utf-8").read()
check("ws: save-and-exit returns 0", rc == 0, f"rc={rc}")
check("ws: file content saved", content == "Hello Stella!\nSecond line.", repr(content))
check("ws: no traceback", b"Traceback" not in out)
check("ws: status line rendered", b"Ln:" in out and b"WORDSTAR" in out)

# --- Test 2: vi mode insert + :wq -------------------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("")
    path2 = fh.name
rc, out = run_editor(["--mode", "vi", path2],
                     [b"ihello from vi", b"\x1b", b":wq\r"])
content = open(path2, encoding="utf-8").read()
check("vi: :wq saves and exits", rc == 0 and content == "hello from vi",
      f"rc={rc} content={content!r}")
check("vi: NORMAL mode shown", b"NORMAL" in out)

# --- Test 3: quit with unsaved changes asks, 'n' cancels, 'y' quits ----------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("original\n")
    path3 = fh.name
rc, out = run_editor([path3], [b"x", b"\x0bQ", b"n", b"\x0bQ", b"y"])  # ^K Q n ^K Q y
content = open(path3, encoding="utf-8").read()
check("ws: quit prompt shown", b"Discard" in out)
check("ws: 'y' quits with rc 0", rc == 0, f"rc={rc}")
check("ws: file unchanged after discard", content == "original\n", repr(content))

# --- Test 4: search highlights and reports matches ---------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("foo bar foo\n")
    path4 = fh.name
rc, out = run_editor([path4], [b"\x11F", b"foo\r", b"\x0bQ", b"y"])  # ^Q F foo Enter, ^K Q y
check("ws: find reports matches", b"matches)" in out and b"(2 " in out, "")
check("ws: search exit clean", rc == 0 and b"Traceback" not in out, f"rc={rc}")

# --- Test 5: help system opens with F1 and closes with Esc -------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("hi\n")
    path5 = fh.name
rc, out = run_editor([path5], [b"\x1bOP", b"\x1b", b"\x0bQ", b"y"])  # F1, Esc, ^K Q y
check("help: menu shown on F1", b"STELLA HELP" in out)
check("help: topics listed", b"WordStar commands" in out and b"vi commands" in out)
check("help: exits clean", rc == 0 and b"Traceback" not in out, f"rc={rc}")

# --- Test 6: undo in WordStar mode (^U) --------------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("")
    path6 = fh.name
rc, out = run_editor([path6], [b"abc", b"\x15", b"\x0bX"])  # type abc, ^U, ^K X
content = open(path6, encoding="utf-8").read()
check("ws: ^U undoes typing", content == "", repr(content))

# --- Test 7: block copy/paste ^B B ... ^B E, ^B C, ^V ------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("abcdef")
    path7 = fh.name
# ^Q C (end of file), ^B B, ^Q R (begin of file), ^B E, ^B C, ^Q C, ^V, ^K X
rc, out = run_editor([path7], [b"\x11C", b"\x02B", b"\x11R", b"\x02E", b"\x02C",
                               b"\x11C", b"\x16", b"\x0bX"])
content = open(path7, encoding="utf-8").read()
check("ws: block copy/paste duplicates text", content == "abcdefabcdef", repr(content))

# --- Test 8: vi visual select + yank + paste ---------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("line one\nline two\n")
    path8 = fh.name
# gg? not implemented; use ^Q? in vi: 'G' not implemented. Go to start: 'k' from line0 no-op.
# v, ll (select 'lin'), y, then G? -> use '$' 'o'? simpler: select first 4 chars, y, move to end 'A'? 
# do: v l l l y  then j $ p  -> paste after end of line 2
rc, out = run_editor(["--mode", "vi", path8],
                     [b"v", b"lll", b"y", b"j", b"$", b"p", b"\x1b", b":wq\r"])
content = open(path8, encoding="utf-8").read()
check("vi: visual yank/paste", content == "line one\nline twoline\n", repr(content))
check("vi: clean exit", rc == 0 and b"Traceback" not in out, f"rc={rc}")

# --- Test 9: search and replace (^Q A), replace one -------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("foo bar foo\n")
    path9 = fh.name
# ^Q A, find "foo", replace "baz", answer "n" (replace one), then ^K X
rc, out = run_editor([path9], [b"\x11A", b"foo\r", b"baz\r", b"n\r", b"\x0bX"])
content = open(path9, encoding="utf-8").read()
check("ws: replace one occurrence", content == "baz bar foo\n", repr(content))
check("ws: replace exits clean", rc == 0 and b"Traceback" not in out, f"rc={rc}")

# --- Test 10: replace all ----------------------------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("foo bar foo\n")
    path10 = fh.name
rc, out = run_editor([path10], [b"\x11A", b"foo\r", b"baz\r", b"y\r", b"\x0bX"])
content = open(path10, encoding="utf-8").read()
check("ws: replace all occurrences", content == "baz bar baz\n", repr(content))

# --- Test 11: print menu degrades gracefully without lpr/ps2pdf ---------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("print me\n")
    path11 = fh.name
rc, out = run_editor([path11], [b"\x0bP", b"d\r", b"/tmp/stella-out.pdf\r", b"\x0bQ", b"y"])
check("print: graceful error when ps2pdf missing",
      rc == 0 and (b"ps2pdf" in out) and b"Traceback" not in out, f"rc={rc}")

# --- Test 12: overwrite mode (Ins toggles OVR) --------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("abc\n")
    path12 = fh.name
# Ins (xterm: \x1b[2~), type X at col 1 -> overwrites 'a'
rc, out = run_editor([path12], [b"\x1b[2~", b"X", b"\x0bX"])
content = open(path12, encoding="utf-8").read()
check("ws: overwrite mode", content == "Xbc\n", repr(content))
check("ws: OVR shown in status", b"OVR" in out)

# --- Test 13: nonexistent file opens as a new empty buffer (vi-style) --------
new_path = os.path.join(tempfile.mkdtemp(prefix="stella-new-"), "fresh.txt")
assert not os.path.exists(new_path)
rc, out = run_editor([new_path], [b"brand new file", b"\x0bX"])  # ^K X saves+exits
check("new file: created on save", os.path.exists(new_path)
      and open(new_path, encoding="utf-8").read() == "brand new file")
check("new file: clean exit", rc == 0 and b"Traceback" not in out, f"rc={rc}")

# --- Test 14: ^B V pastes the block (WordStar-style paste) -------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("abcdef")
    path14 = fh.name
# ^Q C, ^B B, ^Q R, ^B E, ^B C (copy), ^Q C, ^B V (paste), ^K X
rc, out = run_editor([path14], [b"\x11C", b"\x02B", b"\x11R", b"\x02E", b"\x02C",
                                b"\x11C", b"\x02V", b"\x0bX"])
content = open(path14, encoding="utf-8").read()
check("ws: ^B V pastes block", content == "abcdefabcdef", repr(content))

# --- Test 15: ^W cuts when a block is marked ----------------------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("abcdef")
    path15 = fh.name
# ^Q C, ^B B, ^Q R, ^B E, ^W (cut block), ^K X
rc, out = run_editor([path15], [b"\x11C", b"\x02B", b"\x11R", b"\x02E", b"\x17", b"\x0bX"])
content = open(path15, encoding="utf-8").read()
check("ws: ^W cuts marked block", content == "", repr(content))
check("ws: cut exits clean", rc == 0 and b"Traceback" not in out, f"rc={rc}")

# --- Test 16: Ins key enters insert mode in vi normal, toggles OVR in insert --
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("ab\n")
    path16 = fh.name
# vi mode: Ins (\x1b[2~) -> insert, type X, Esc, :wq
rc, out = run_editor(["--mode", "vi", path16],
                     [b"\x1b[2~", b"X", b"\x1b", b":wq\r"])
content = open(path16, encoding="utf-8").read()
check("vi: Ins enters insert mode", content == "Xab\n", repr(content))

with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("ab\n")
    path17 = fh.name
# vi: i, Ins (toggle OVR), type X (overwrites 'a'), Esc, :wq
rc, out = run_editor(["--mode", "vi", path17],
                     [b"i", b"\x1b[2~", b"X", b"\x1b", b":wq\r"])
content = open(path17, encoding="utf-8").read()
check("vi: Ins in insert toggles overwrite", content == "Xb\n", repr(content))

# --- Test 17: help navigable with WordStar diamond keys -----------------------
with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
    fh.write("hi\n")
    path18 = fh.name
# F1, ^X (down in menu), Enter (open topic 2), ^X/^E scroll doc, Esc, F1... quit
rc, out = run_editor([path18], [b"\x1bOP", b"\x18", b"\r", b"\x18", b"\x05", b"\x1b", b"\x1bOP", b"\x0bQ", b"y"])
check("help: diamond keys navigate", b"vi commands" in out and rc == 0 and b"Traceback" not in out, f"rc={rc}")

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("ALL PTY SMOKE TESTS PASSED")
