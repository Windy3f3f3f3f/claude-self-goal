# How it works

## The goal

Claude Code's `/goal <condition>` (v2.1.139+) records a completion condition. Whenever the session tries to end a turn, an **independent evaluator** checks whether the condition holds; if not, it sends the model back to keep working, until the condition is met. A `◎ /goal active` chip shows it's engaged. The goal lives in the session's own transcript, so it is naturally per-session — one session's goal never leaks into another.

We want an autonomous session to set this on **itself**, with no human typing.

## Why you can't just "call" it

There is no programmatic entry point to the native goal:

- **Hooks can't.** Every hook input/output field is documented as *not* interpreted as slash commands. A `Stop` hook can *emulate* a goal loop (block stopping until your own check passes), but that reimplements the feature — you lose the built-in evaluator and the UI, and you have to solve per-session isolation yourself.
- **No settings / env / CLI / API** sets the goal.
- **`claude -p "/goal ..."` deadlocks** on v2.1.202 (hangs with no output), even with a real task attached.

So the only way to engage the *native* machinery is to put the text `/goal <condition>` into the session's **input**, exactly as a human would.

## How input reaches a running session

A `claude` process reads user input from a **pts** (pseudo-terminal slave):

- **Interactive session in a terminal** — the pts is its controlling terminal. Both stdin and stdout point at it.
- **Background / supervised session** — a supervisor (Claude Code's own pty-host) allocates a pty pair per session, holds the master, and the session reads the slave. On the machine this was built on, a backgrounded session's `claude` process had `stdin = stdout = /dev/pts/0`, with a separate `--bg-pty-host` process holding the master.

Either way, the session reads a pts. Anything that lands in that pts's input queue is read as if typed.

### tmux is one way to write that input

If the session runs inside tmux, `tmux send-keys -t <pane>` writes into the pane's pty — the clean, unprivileged path. But it requires the session to have been started in tmux, and you can't retrofit tmux around an already-running process.

### TIOCSTI is the universal way

`TIOCSTI` ("terminal I/O control: simulate terminal input") is an ioctl that pushes a byte into a tty's input queue as if typed. As root / `CAP_SYS_ADMIN` you can do this to a pts by opening it by path — no tmux, no master handle. This is what makes **background / non-tmux** self-set possible.

Modern kernels disable the *legacy* unprivileged `TIOCSTI` (`dev.tty.legacy_tiocsti=0`, often compiled out), precisely because it's a keystroke-injection primitive. Root still has it via `CAP_SYS_ADMIN`. See [SECURITY.md](../SECURITY.md).

## Finding the right pts (fail-closed)

Injecting into the *wrong* tty would be bad, so discovery is strict:

1. Walk up the process tree from the tool's own parent.
2. Identify a **Claude Code** ancestor (by `comm` and by `/proc/<pid>/cmdline`, covering both the native `claude.exe` binary and node `cli.js` installs).
3. Require that ancestor's **stdin and stdout to be the same `/dev/pts/N`** — that distinguishes the interactive TUI process (which reads keystrokes there) from helper processes.
4. The first ancestor that satisfies all of this is the target. If none does, **refuse** — there is no "nearest tty" fallback.

Because we only ever target a pts belonging to a Claude process we descend from, "self-set" stays literally self.

## Delivering the line

We inject `"/goal " + condition + "\r"` — the trailing carriage return submits it. The condition is sanitized first: any control character is rejected, so it can't contain a second `\r` that would submit a following, attacker-chosen command.

If injected mid-turn (the session is busy running the very Bash call that injects), the line queues in the input and is applied at the next turn boundary — the goal then engages and drives the work.

## Verifying it end to end

The test harness (`test/test_integration.py`) starts a real, non-tmux `claude` on a private pty, then — via an ordinary user prompt — asks it to run `claude-self-goal` on itself. Success is measured by a side effect: the native goal must drive the session to create a proof file. Nothing is injected by the harness; the child injects into its own pts. This is the exact flow that was proven during development.
