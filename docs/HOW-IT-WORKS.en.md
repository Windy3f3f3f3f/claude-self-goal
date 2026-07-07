# How it works

[简体中文](./HOW-IT-WORKS.md) · English

## The goal

Claude Code's `/goal <condition>` (v2.1.139+) records a completion condition. Whenever the session tries to end a turn, an independent evaluator checks whether the condition holds; if not, it sends the model back to keep working, until it's met. A `◎ /goal active` chip shows it's engaged. The goal lives in the session's own transcript, so it is naturally per-session.

We want an autonomous session to set this on itself, with no human typing.

## Why you can't just "call" it

There is no programmatic entry point to the native goal. Hooks can't — every hook input/output field is documented as not interpreted as slash commands. No settings, environment variable, CLI flag, or API sets it either. And `claude -p "/goal ..."` deadlocks on v2.1.202, even with a real task attached.

So the only way to engage the native machinery is to put the text `/goal <condition>` into the session's input, exactly as a human would. The catch: different sessions receive "input" through different channels.

## Three session types, three input channels

**Plain interactive session (including tmux):** the `claude` process reads input from its **controlling terminal** (a pts); stdin and stdout both point at it. Putting bytes into that pts's input queue is read as if typed. A tmux session is this type too — the pts is just the tmux pane's pty.

**Daemon-managed background session** (`claude --bg`, or phone remote): different shape. A supervisor (Claude Code's own pty-host) allocates a pty pair; the session's **output** goes to the pts (the pty-host relays it to viewers), but its **input does not come from the pts** — it arrives over a listening unix socket `rv/<session-id>.sock`, which clients like `claude attach` and phone remote connect to. Key tell: this process has **no controlling terminal** (tty_nr is 0 in `/proc/<pid>/stat`); the pts is just an open fd, not its controlling terminal.

**Headless `claude -p`:** stdin is a pipe or `/dev/null` — no interactive input channel at all.

The delivery methods mirror this:

- interactive in tmux → `tmux send-keys` to the pane's pty (no root);
- interactive, not in tmux → `TIOCSTI` bytes into that pts's input queue (needs root);
- daemon background session → `claude attach <id>` connects to `rv/<id>.sock` and speaks the daemon protocol for us;
- headless → nothing to do; refused.

## Why pts injection is inert for daemon sessions

Because their input isn't read from the pts at all. `TIOCSTI`-ing bytes into the pts "succeeds" at the syscall level, but nothing reads that buffer as input — the bytes go into a dead letterbox. An early pts-only version therefore **falsely reported success** on daemon sessions while doing nothing. The way to tell the two apart is whether that pts is the process's controlling terminal: if it is, that's live interactive input; if not, it's a daemon shell.

## TIOCSTI and attach

`TIOCSTI` ("terminal I/O control: simulate terminal input") is an ioctl that pushes a byte into a tty's input queue as if typed. With `CAP_SYS_ADMIN` (root) you can open a pts by path and do this. Modern kernels disable the legacy unprivileged `TIOCSTI` (`dev.tty.legacy_tiocsti=0`, often compiled out) precisely because it's a keystroke-injection primitive; root can still use it, but a seccomp filter, user namespace, or container policy can block it even for root.

The daemon path doesn't touch that primitive — it uses the official client `claude attach <id>`, which already connects to `rv/<id>.sock` and forwards keystrokes. So we don't reverse-engineer the protocol: we run it in a headless pty, type `/goal <condition>` into it, then detach (the session keeps running).

## Finding the right target (fail-closed, and only the nearest)

Injecting into the wrong terminal would be bad, so discovery is strict — with one easily-missed but critical rule: **classify only the nearest Claude ancestor in the process tree, never reach past it.**

Picture a background session spawned from an interactive foreground Claude: the nearest Claude is the background session (no controlling terminal), but further up there's a foreground Claude (with a real controlling pts). If discovery scanned upward for "any Claude with a controlling terminal," it would find that foreground parent and inject `/goal` into **someone else's session**. So the tool takes only the nearest Claude ancestor and classifies just that one:

- its stdin and stdout are the same pts AND that pts is its controlling terminal → interactive, use the pts;
- otherwise, read the session id from its own single listening `rv/<id>.sock` → daemon, use attach;
- neither → headless or unrecognized, refuse.

Reading the session id: map the Claude process's socket fd inodes to paths via `/proc/net/unix`, pick the listening `rv/<id>.sock`, and pull out `<id>`. Only a listening socket counts, and exactly one is required — zero or more than one fails closed, so we never pick the wrong session.

## Sanitization and a safety valve

The injected text is `/goal <condition>`, sanitized first: any control character is rejected, so it can't carry a second carriage return that would submit a following command. There is also a hard backstop: setting `CLAUDE_SELF_GOAL_DRY_RUN=1` forces dry-run — nothing is ever injected. Test suites always set it, so even a buggy test can never fire a real `/goal` into the live session running the tests.

## Verifying it end to end

Two integration tests (`test/test_integration.py` and `test/test_integration_daemon.py`) cover the two real injection paths: one starts a real interactive `claude` on a private pty and has it TIOCSTI a goal into itself; the other starts a throwaway `claude --bg` (a real daemon session) and injects via the tool's `--session` over attach. Both measure success by a side effect — the native goal must drive the session to create a proof file — and neither touches the session running the tests.
