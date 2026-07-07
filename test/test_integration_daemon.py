#!/usr/bin/env python3
"""End-to-end for the daemon/attach path: start a throwaway `claude --bg`
session (input arrives over its rv socket, not a pts), then use the tool's
--session mode to inject a /goal, and assert the native goal drives it to create
a proof file. Cross-session on purpose (safer than self-attach) — one process
setting a goal on another daemon session.

Opt-in: needs `claude` on PATH, and consumes quota. Enable with
RUN_CLAUDE_INTEGRATION=1. Uses --permission-mode bypassPermissions in a
throwaway temp dir."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import TOOL  # noqa: E402

if os.environ.get("RUN_CLAUDE_INTEGRATION") != "1":
    print("SKIP test_integration_daemon (set RUN_CLAUDE_INTEGRATION=1; needs claude + quota)")
    sys.exit(0)
if shutil.which("claude") is None:
    print("SKIP test_integration_daemon (claude not on PATH)")
    sys.exit(0)

workdir = tempfile.mkdtemp(prefix="csg_daemon_")
proof = os.path.join(workdir, "PROOF.txt")
sid = None
created = False


def agents():
    try:
        out = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=30)
        return json.loads(out.stdout)
    except Exception:
        return []


try:
    # start a throwaway daemon-managed background session that idles after READY
    subprocess.run(
        ["claude", "--bg", "--permission-mode", "bypassPermissions",
         "Reply with exactly READY, then wait. Do nothing else until told."],
        cwd=workdir, capture_output=True, text=True, timeout=60)
    # find its id by cwd
    for _ in range(15):
        for a in agents():
            if isinstance(a, dict) and a.get("cwd") == workdir:
                sid = a.get("id")
                break
        if sid:
            break
        time.sleep(2)
    if not sid:
        print("FAIL: could not find the throwaway session's id")
        sys.exit(1)
    print("throwaway daemon session id =", sid)

    # inject a goal into it via the tool's --session (attach) path
    r = subprocess.run([sys.executable, TOOL, "--session", sid,
                        "a file named PROOF.txt exists in this directory"],
                       cwd=workdir, capture_output=True, text=True, timeout=90)
    print("tool rc=%d out=%s" % (r.returncode, (r.stdout + r.stderr).strip()[:200]))

    created = False
    for _ in range(90):
        if os.path.exists(proof):
            created = True
            break
        time.sleep(2)
    print("PROOF_CREATED=%s" % created)
finally:
    if sid:
        subprocess.run(["claude", "stop", sid], capture_output=True, text=True, timeout=30)
    shutil.rmtree(workdir, ignore_errors=True)

if not created:
    print("FAIL: injected goal did not drive proof-file creation")
    sys.exit(1)
print("daemon integration test passed")
sys.exit(0)
