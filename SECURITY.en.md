# Security & threat model

[简体中文](./SECURITY.md) · English

claude-self-goal injects input into a running Claude Code session. Understand what that means before you use it.

## What this is

A local automation wrapper. It delivers the text `/goal <condition>` to a Claude Code session you are already running — through `tmux send-keys` when in tmux, or the Linux `TIOCSTI` ioctl otherwise. Its intended use is letting an autonomous agent set a goal on its own session, on a machine you control.

## What this is not

It is not exploiting a Claude Code bug or a kernel vulnerability — it uses documented, intended interfaces. But it is a privileged keystroke-injection wrapper, and that capability is inherently dual-use. `TIOCSTI` pushes bytes into a terminal's input queue as if typed. With root (`CAP_SYS_ADMIN`), and unless the kernel or container policy blocks it, a process can do this to any pts it can open, not just its own. The same primitive has historically been used to escape restricted shells and inject commands into other users' terminals.

This tool deliberately constrains itself to the Claude session in its own process ancestry, and refuses when it can't find one. But be clear: that is a usage-level restraint, not a kernel-enforced boundary — root can always bypass it, which is exactly what `--unsafe-pts` makes explicit.

## Rules

Don't run it on a shared or multi-user host. There, a root-capable keystroke injector is a privilege-escalation and session-hijacking tool no matter how restrained this wrapper is.

Don't target a session you don't own. Discovery only ever points at the Claude process you descend from; don't use `--unsafe-pts` to defeat that against someone else's terminal.

Don't enable `dev.tty.legacy_tiocsti=1`. Modern kernels disable the legacy `TIOCSTI` on purpose. This tool works via `CAP_SYS_ADMIN` (root) without turning it back on; we neither document nor recommend re-enabling it, because that would expose the injection primitive to unprivileged processes.

## Hardening in this tool

Discovery is fail-closed: if no Claude ancestor with a pts is found, it refuses — there is no "inject into the nearest terminal" fallback.

Both stdin and stdout must be the same pts, which pins the interactive TUI process rather than some helper that merely has a pts on one descriptor.

The condition is sanitized: any control character (CR/LF/ESC/…) in the goal text is rejected, so the injected line can't carry a second keystroke or slash command.

The escape hatch is explicit and self-documenting: overriding discovery requires both `--unsafe-pts` and `--i-understand-this-can-inject-keystrokes`.

## Reporting

Found a way to misuse this beyond its stated model, or a bug in the safeguards? Please open an issue. This is a small, single-purpose tool with no separate embargoed channel.
