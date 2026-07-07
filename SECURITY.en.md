# Security & threat model

[简体中文](./SECURITY.md) · English

claude-self-goal injects input into a running Claude Code session. Understand what that means before you use it.

## What this is

A local automation wrapper. It delivers the text `/goal <condition>` to a Claude Code session you are already running, over one of three channels by session type: `tmux send-keys` for tmux sessions, `TIOCSTI` for plain interactive sessions, `claude attach` for daemon background sessions. Its purpose is letting an autonomous agent set a goal on its own session (or on another of your own background sessions), on a machine you control.

## What this is not

It is not exploiting a Claude Code bug or a kernel vulnerability — it uses documented, intended interfaces. But it does inject input into a session, and that capability is inherently dual-use; the two channels carry different weight.

`TIOCSTI` pushes bytes into a terminal's input queue as if typed. With root (`CAP_SYS_ADMIN`), and unless the kernel/container policy blocks it, a process can do this to any pts it can open, not just its own. The same primitive has historically been used to escape restricted shells and inject commands into other users' terminals.

The `claude attach` channel doesn't touch that privileged primitive — it uses the official client and is comparatively mild. But it still delivers input into a session, and `--session <id>` explicitly targets another session — so it too is only for your own machine and your own sessions.

Auto-discovery deliberately classifies only the nearest Claude session in the process ancestry, and refuses when it can't find one. That is a usage-level restraint, not a kernel-enforced boundary — root can always bypass it (`--session` and `--unsafe-pts` make that explicit).

## Rules

Don't run it on a shared or multi-user host. There, a root-capable keystroke injector is a privilege-escalation and session-hijacking tool no matter how restrained this wrapper is.

Don't target a session you don't own. Discovery only points at the nearest Claude you descend from; don't use `--session` or `--unsafe-pts` to defeat that against someone else's terminal or session.

Don't enable `dev.tty.legacy_tiocsti=1`. Modern kernels disable the legacy `TIOCSTI` on purpose. This tool works via `CAP_SYS_ADMIN` (root) without turning it back on; we neither document nor recommend re-enabling it, because that would expose the injection primitive to unprivileged processes.

## Hardening in this tool

**Nearest Claude ancestor only.** Discovery classifies the first Claude it finds walking up the tree and never reaches past it — otherwise a background session spawned from an interactive foreground session could be misclassified and have a goal injected into the foreground parent.

**Controlling terminal separates a live pts from a daemon shell.** Only a session whose stdin/stdout is the same pts and whose controlling terminal is that pts uses pts injection; daemon sessions (no controlling terminal) use attach.

**The daemon session id is read from the process's own single listening rv socket** — zero or more than one fails closed, so it never picks the wrong session.

**Condition sanitization.** Any control character (CR/LF/ESC/…) in the goal text is rejected, so the injected line can't carry a second keystroke or slash command.

**A hard dry-run backstop.** `CLAUDE_SELF_GOAL_DRY_RUN=1` forces dry-run — nothing is injected. Test suites always set it, so no test can ever fire a real goal into the live session.

**The escape hatches are explicit and self-documenting.** Bypassing discovery means either `--session <id>` (cross-session) or `--unsafe-pts` plus `--i-understand-this-can-inject-keystrokes`.

## Reporting

Found a way to misuse this beyond its stated model, or a bug in the safeguards? Please open an issue. This is a small, single-purpose tool with no separate embargoed channel.
