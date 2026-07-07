#!/usr/bin/env python3
"""CLI-level negative tests. Every case here is rejected BEFORE any injection
could happen, and the few that reach the real path use --dry-run, so running
this from inside a live Claude session never injects anything."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import TOOL  # noqa: E402

fails = []


def run(args):
    return subprocess.run([sys.executable, TOOL] + args,
                          capture_output=True, text=True)


def check(name, cond, got=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  (got %r)" % (got,)))
    if not cond:
        fails.append(name)


# control char in condition -> EX_BAD_CONDITION (6), rejected before any inject
r = run(["a file\rexists"])
check("newline/CR condition rejected", r.returncode == 6, r.returncode)

r = run(["esc\x1b[31m color"])
check("ESC condition rejected", r.returncode == 6, r.returncode)

# no args and no --clear -> usage error
r = run([])
check("no condition -> usage error", r.returncode == 2, r.returncode)

# --unsafe-pts without acknowledgement -> usage error (2), before injection
r = run(["--unsafe-pts", "/dev/pts/999", "some goal"])
check("unsafe-pts without ack rejected", r.returncode == 2, r.returncode)

# --unsafe-pts with a non-pts path -> usage error
r = run(["--unsafe-pts", "/tmp/x", "--i-understand-this-can-inject-keystrokes", "g"])
check("unsafe-pts non-pts path rejected", r.returncode == 2, r.returncode)

# dry-run never injects and reports a plan (exit 0) — forced tiocsti
r = run(["--dry-run", "--method", "tiocsti", "a goal condition"])
check("dry-run tiocsti exits 0", r.returncode == 0, r.returncode)
check("dry-run prints method+line", "method=" in r.stdout and "line=" in r.stdout, r.stdout)

# --clear dry-run
r = run(["--clear", "--dry-run", "--method", "tiocsti"])
check("clear dry-run exits 0", r.returncode == 0, r.returncode)
check("clear dry-run line is /goal clear", "/goal clear" in r.stdout, r.stdout)

print()
if fails:
    print("NEGATIVE TESTS FAILED: %d" % len(fails))
    sys.exit(1)
print("negative tests passed")
