#!/usr/bin/env python3
"""End-to-end: start a real (non-tmux) Claude Code session on a private pty, ask
it — via a normal user prompt — to run claude-self-goal on ITSELF, and assert
the native goal drives it to create a proof file. Nothing is injected by this
harness; the child injects into its own pts.

Opt-in only: needs `claude` on PATH, root (TIOCSTI), and consumes quota. Enable
with RUN_CLAUDE_INTEGRATION=1. Uses --permission-mode bypassPermissions in a
throwaway temp dir; do not treat that flag as a normal-usage recommendation."""
import os
import pty
import re
import select
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import TOOL  # noqa: E402

if os.environ.get("RUN_CLAUDE_INTEGRATION") != "1":
    print("SKIP test_integration (set RUN_CLAUDE_INTEGRATION=1 to run; needs claude+root+quota)")
    sys.exit(0)
if shutil.which("claude") is None:
    print("SKIP test_integration (claude not on PATH)")
    sys.exit(0)
if os.geteuid() != 0:
    print("SKIP test_integration (needs root)")
    sys.exit(0)

ANSI = re.compile(rb'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*(\x07|\x1b\\)|\x1b[>=()][A-Za-z0-9]?|\r')
clean = lambda b: ANSI.sub(b'', b).decode('utf-8', 'replace')
nospace = lambda s: re.sub(r'\s+', '', s)

workdir = tempfile.mkdtemp(prefix="csg_integ_")
proof = os.path.join(workdir, "PROOF.txt")

pid, master = pty.fork()
if pid == 0:
    os.chdir(workdir)
    os.environ["TERM"] = "xterm-256color"
    os.execvp("claude", ["claude", "--permission-mode", "bypassPermissions"])
    os._exit(127)


def pump(t=0.4):
    buf = b""
    while True:
        r, _, _ = select.select([master], [], [], t)
        if not r:
            break
        try:
            c = os.read(master, 65536)
        except OSError:
            break
        if not c:
            break
        buf += c
        t = 0.15
    return buf


screen = b""
ready = trust = False
t0 = time.time()
while time.time() - t0 < 75:
    screen += pump(0.5)
    ns = nospace(clean(screen))
    if ("trustthisfolder" in ns or "Yes,Itrust" in ns) and not trust:
        os.write(master, b"\r")
        trust = True
        time.sleep(1.2)
        continue
    if "bypasspermissions" in ns or "forshortcuts" in ns:
        ready = True
        break

prompt = ("Run exactly this with your Bash tool: %s 'a file named PROOF.txt exists in this directory'. "
          "It sets you a goal; then do what the goal needs." % TOOL)
for ch in prompt:
    os.write(master, ch.encode())
    time.sleep(0.002)
time.sleep(0.4)
os.write(master, b"\r")

created = False
t0 = time.time()
while time.time() - t0 < 200:
    screen += pump(0.5)
    if os.path.exists(proof):
        created = True
        break
try:
    os.write(master, b"\x03")
    os.close(master)
except OSError:
    pass
shutil.rmtree(workdir, ignore_errors=True)

print("TUI_READY=%s  PROOF_CREATED=%s" % (ready, created))
if created:
    print("integration test passed")
    sys.exit(0)
print("FAIL integration: goal did not drive proof-file creation")
print(clean(screen)[-800:])
sys.exit(1)
