#!/usr/bin/env python3
"""Prove the TIOCSTI injection primitive delivers bytes into a pts as input.
Uses a private pty + a reader child; touches no Claude session. Needs root."""
import os
import pty
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import load_module  # noqa: E402

if os.geteuid() != 0:
    print("SKIP test_primitive (needs root for TIOCSTI)")
    sys.exit(0)

csg = load_module()
RESULT = "/tmp/csg_primitive_result.%d" % os.getpid()
if os.path.exists(RESULT):
    os.remove(RESULT)

reader = (
    "import sys\n"
    "line = sys.stdin.readline()\n"
    "open(%r, 'w').write(line)\n" % RESULT
)

child, master = pty.fork()
if child == 0:
    os.execvp(sys.executable, [sys.executable, "-c", reader])
    os._exit(127)

time.sleep(0.4)
slave = os.readlink("/proc/%d/fd/0" % child)
ok = slave.startswith("/dev/pts/")
try:
    csg.tiocsti_inject(slave, "MARKER-OK\r")
except Exception as e:
    print("FAIL tiocsti_inject raised: %s" % e)
    sys.exit(1)

# wait for the reader child to record what it received
got = ""
for _ in range(40):
    if os.path.exists(RESULT):
        got = open(RESULT).read()
        if got:
            break
    time.sleep(0.1)
try:
    os.close(master)
except OSError:
    pass
if os.path.exists(RESULT):
    os.remove(RESULT)

if ok and "MARKER-OK" in got:
    print("ok   TIOCSTI delivered %r into %s" % (got.strip(), slave))
    print("primitive test passed")
    sys.exit(0)
print("FAIL primitive: slave_ok=%s got=%r" % (ok, got))
sys.exit(1)
