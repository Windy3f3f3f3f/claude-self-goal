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

# --- find_claude_pts / find_claude_ancestor branch coverage with a fake tree ---
def in_fake_tree(tree, fn, start):
    """tree: {pid: {comm, cmdline, fd0, fd1, ctty, ppid}}. Runs fn(start) with the
    /proc helpers mocked from the tree."""
    orig = (csg._proc_comm, csg._proc_cmdline, csg._proc_ppid, csg._fd_target, csg._controlling_pts)
    csg._proc_comm = lambda p: tree.get(p, {}).get("comm", "")
    csg._proc_cmdline = lambda p: tree.get(p, {}).get("cmdline", "")
    csg._proc_ppid = lambda p: tree.get(p, {}).get("ppid", None)
    csg._fd_target = lambda p, fd: tree.get(p, {}).get("fd%d" % fd, "")
    csg._controlling_pts = lambda p: tree.get(p, {}).get("ctty", "")
    try:
        return fn(start)
    finally:
        csg._proc_comm, csg._proc_cmdline, csg._proc_ppid, csg._fd_target, csg._controlling_pts = orig

def with_fake_tree(tree, start):
    return in_fake_tree(tree, lambda s: csg.find_claude_pts(start_pid=s), start)

CLA = {"comm": "claude.exe", "cmdline": "/x/@anthropic-ai/claude-code/bin/claude.exe"}
# positive: claude ancestor whose fd0==fd1==pts AND that pts is its controlling tty
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe:[1]", "fd1": "pipe:[2]", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/5", fd1="/dev/pts/5", ctty="/dev/pts/5", ppid=1)}
pts, pid = with_fake_tree(t, 10)
check("fake: claude, pts is controlling tty -> found", pts == "/dev/pts/5" and pid == 20)

# negative: DAEMON BG — fd0==fd1==pts but pts is NOT the controlling tty (ctty empty)
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/0", fd1="/dev/pts/0", ctty="", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude bg (pts not controlling tty) -> refuse", pts is None)

# negative: has pts (and controlling) but NOT claude
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: {"comm": "sshd", "cmdline": "sshd", "fd0": "/dev/pts/5", "fd1": "/dev/pts/5", "ctty": "/dev/pts/5", "ppid": 1}}
pts, _ = with_fake_tree(t, 10)
check("fake: pts but not claude -> refuse", pts is None)

# negative: claude ancestor but fd0 != fd1
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/5", fd1="/dev/pts/6", ctty="/dev/pts/5", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude fd0!=fd1 -> refuse", pts is None)

# negative: claude ancestor, fd0 pts but fd1 not a pts
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/5", fd1="/dev/null", ctty="/dev/pts/5", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude fd1 not pts -> refuse", pts is None)

# negative: claude ancestor with piped stdin (headless -p) -> refuse
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="pipe:[99]", fd1="pipe:[99]", ctty="", ppid=1)}
pts, _ = with_fake_tree(t, 10)
check("fake: claude piped stdin -> refuse", pts is None)

# P0 REGRESSION: nearest Claude is a daemon (no ctty); a GRANDPARENT Claude has a
# real controlling pts. Classify ONLY the nearest one and refuse — never reach
# past it and inject into the foreground parent session's pts.
t = {10: {"comm": "bash", "cmdline": "bash", "fd0": "pipe", "fd1": "pipe", "ppid": 20},
     20: dict(CLA, fd0="/dev/pts/0", fd1="/dev/pts/0", ctty="", ppid=30),   # nearest: daemon, no ctty
     30: dict(CLA, fd0="/dev/pts/9", fd1="/dev/pts/9", ctty="/dev/pts/9", ppid=1)}  # grandparent: interactive
pts, _ = with_fake_tree(t, 10)
check("fake: never reaches past nearest Claude to parent's pts", pts is None)
check("find_claude_ancestor returns the NEAREST claude (20, not 30)",
      in_fake_tree(t, lambda s: csg.find_claude_ancestor(start_pid=s), 10) == 20)

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

# --- _rv_session_id: pull the daemon session id off the rv socket ---
# /proc/net/unix columns: Num RefCount Protocol Flags Type St Inode Path
def unixline(inode, path, listening=False):
    flags = "00010000" if listening else "00000000"
    return "0000: 00000002 0 %s 0001 01 %s %s" % (flags, inode, path)

RVDIR = "/tmp/cc-daemon-0/abc/rv"
# exactly one owned LISTENING rv socket -> that's the session id
lines = [unixline("111", "%s/994f658d.sock" % RVDIR, listening=True),
         unixline("222", "/tmp/other.sock")]
check("rv id: single listening rv socket -> id", csg._rv_session_id({"111"}, lines) == "994f658d")
# only listening counts; a connected rv fd is ignored, listening wins
lines = [unixline("111", "%s/aaaaaaaa.sock" % RVDIR, listening=False),
         unixline("222", "%s/bbbbbbbb.sock" % RVDIR, listening=True)]
check("rv id: connected rv ignored, listening wins", csg._rv_session_id({"111", "222"}, lines) == "bbbbbbbb")
# inode we don't own -> ignored
check("rv id: foreign inode ignored", csg._rv_session_id({"999"}, lines) is None)
# non-rv sockets -> None
check("rv id: no rv socket -> None",
      csg._rv_session_id({"111"}, [unixline("111", "/tmp/cc-daemon-0/abc/control.sock", listening=True)]) is None)
# fail closed: a connected-only rv socket does NOT resolve (no fallback)
check("rv id: connected-only rv -> None",
      csg._rv_session_id({"111"}, [unixline("111", "%s/deadbeef.sock" % RVDIR)]) is None)
# fail closed: two DIFFERENT owned listening rv sockets -> ambiguous -> None
check("rv id: two listening rv -> None (ambiguous)",
      csg._rv_session_id({"111", "222"},
                         [unixline("111", "%s/aaaaaaaa.sock" % RVDIR, listening=True),
                          unixline("222", "%s/bbbbbbbb.sock" % RVDIR, listening=True)]) is None)
# same socket listed twice (dup inode line) is still a single id
check("rv id: duplicate lines, single id",
      csg._rv_session_id({"111"},
                         [unixline("111", "%s/994f658d.sock" % RVDIR, listening=True),
                          unixline("111", "%s/994f658d.sock" % RVDIR, listening=True)]) == "994f658d")

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
