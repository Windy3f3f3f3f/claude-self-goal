#!/usr/bin/env python3
"""Unit tests for target discovery + condition sanitation. No claude, no root."""
import os
import pty
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _util import load_module  # noqa: E402

csg = load_module()
fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# --- is_claude across install shapes ---
check("is_claude native comm", csg.is_claude("claude.exe", "/x/claude.exe --bg-spare"))
check("is_claude short comm", csg.is_claude("claude", "claude"))
check("is_claude node cmdline", csg.is_claude("node", "node /x/@anthropic-ai/claude-code/cli.js"))
check("is_claude rejects bash", not csg.is_claude("bash", "bash -c ls"))
check("is_claude rejects random", not csg.is_claude("vim", "vim README.md"))

# --- fail-closed: walking from init (pid 1) finds no claude ancestor ---
pts, pid = csg.find_claude_pts(start_pid=1)
check("find_claude_pts fail-closed from init", pts is None and pid is None)

# --- find_claude_pts branch coverage with a fake /proc process tree ---
def with_fake_tree(tree, start):
    """tree: {pid: {comm, cmdline, fd0, fd1, ppid}}. Returns find_claude_pts result."""
    orig = (csg._proc_comm, csg._proc_cmdline, csg._proc_ppid, csg._fd_target)
    csg._proc_comm = lambda p: tree.get(p, {}).get("comm", "")
    csg._proc_cmdline = lambda p: tree.get(p, {}).get("cmdline", "")
    csg._proc_ppid = lambda p: tree.get(p, {}).get("ppid", None)
    csg._fd_target = lambda p, fd: tree.get(p, {}).get("fd%d" % fd, "")
    try:
        return csg.find_claude_pts(start_pid=start)
    finally:
        csg._proc_comm, csg._proc_cmdline, csg._proc_ppid, csg._fd_target = orig

CLA = {"comm": "claude.exe", "cmdline": "/x/@anthropic-ai/claude-code/bin/claude.exe"}
# positive: claude ancestor whose fd0==fd1==pts
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe:[1]", "fd1": "pipe:[2]", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/5", fd1="/dev/pts/5", ppid=1)}
pts, pid = with_fake_tree(t, 10)
check("fake: claude+fd0==fd1 pts -> found", pts == "/dev/pts/5" and pid == 20)

# negative: has pts fd0==fd1 but NOT claude
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: {"comm": "sshd", "cmdline": "sshd", "fd0": "/dev/pts/5", "fd1": "/dev/pts/5", "ppid": 1}}
pts, _ = with_fake_tree(t, 10)
check("fake: pts but not claude -> refuse", pts is None)

# negative: claude ancestor but fd0 != fd1
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/5", fd1="/dev/pts/6", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude fd0!=fd1 -> refuse", pts is None)

# negative: claude ancestor, fd0 pts but fd1 not a pts
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/5", fd1="/dev/null", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude fd1 not pts -> refuse", pts is None)

# negative: claude ancestor with piped stdin (headless -p) -> refuse
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="pipe:[99]", fd1="pipe:[99]", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude piped stdin -> refuse", pts is None)

# --- _fd_target reads a real pts from a spawned pty child ---
child, master = pty.fork()
if child == 0:
    # child: just sleep so the parent can inspect its fds
    time.sleep(3)
    os._exit(0)
else:
    time.sleep(0.3)
    fd0 = csg._fd_target(child, 0)
    check("_fd_target sees child's pts", fd0.startswith("/dev/pts/"))
    ppid = csg._proc_ppid(child)
    check("_proc_ppid returns an int", isinstance(ppid, int) and ppid > 0)
    os.close(master)

# --- sanitize_condition rejects control chars, accepts printable/unicode ---
for bad in ["a\rb", "a\nb", "a\x1b[31m", "x\ty", "a\x00b", ""]:
    try:
        csg.sanitize_condition(bad)
        check("sanitize rejects %r" % bad, False)
    except ValueError:
        check("sanitize rejects %r" % bad, True)
for good in ["a file named x.txt exists", "测试：文件存在", "tests pass && build green"]:
    try:
        check("sanitize accepts %r" % good, csg.sanitize_condition(good) == good)
    except ValueError:
        check("sanitize accepts %r" % good, False)

print()
if fails:
    print("DISCOVERY TESTS FAILED: %d" % len(fails))
    sys.exit(1)
print("discovery tests passed")
