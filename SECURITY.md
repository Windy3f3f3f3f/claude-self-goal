# Security & threat model

`claude-self-goal` injects input into a running Claude Code session. Please understand what that means before you use it.

## What this is

A local automation wrapper. It delivers the text `/goal <condition>` to a Claude Code session you are already running, either through `tmux send-keys` (when in tmux) or through the Linux `TIOCSTI` ioctl (otherwise). Its intended use is letting an autonomous agent set a goal on **its own** session on a machine **you control**.

## What this is not

It is **not** an exploit of a Claude Code bug or a kernel vulnerability — it uses documented, intended interfaces. But it **is** a privileged keystroke-injection wrapper, and that capability is inherently dual-use:

- `TIOCSTI` pushes bytes into a terminal's input queue *as if typed*. With root / `CAP_SYS_ADMIN`, a process can do this to **any** pts on the host, not just its own. The same primitive has historically been used to escape restricted shells and inject commands into other users' terminals.
- This tool deliberately constrains itself to the Claude session in its own process ancestry (fail-closed discovery). That is a **usage** safeguard, not a kernel-enforced boundary. Root can always bypass it (that's what `--unsafe-pts` makes explicit).

## Rules

- **Do not run this on a shared or multi-user host.** On such a machine, a root-capable keystroke injector is a privilege-escalation and session-hijacking tool regardless of this wrapper's own restraint.
- **Do not target a session you do not own.** Discovery only ever targets a Claude process you descend from; do not defeat that with `--unsafe-pts` against someone else's terminal.
- **Do not enable `dev.tty.legacy_tiocsti=1`.** Modern kernels disable the legacy `TIOCSTI` path on purpose. This tool works via `CAP_SYS_ADMIN` (root) *without* re-enabling it; we do not document or recommend turning it back on, because that would expose the injection primitive to unprivileged processes.

## Hardening in this tool

- **Fail-closed discovery.** If no Claude Code ancestor with a pts is found, it refuses — no "inject into whatever tty is nearby" fallback.
- **Both fd0 and fd1 must be the same pts.** This targets the interactive TUI process, not an unrelated helper that merely has a pts on one descriptor.
- **Condition sanitization.** Any control character (CR/LF/ESC/…) in the goal text is rejected, so the injected line cannot smuggle a second keystroke or slash command.
- **Explicit, self-documenting escape hatch.** Overriding discovery requires both `--unsafe-pts` and `--i-understand-this-can-inject-keystrokes`.

## Reporting

Found a way this tool can be misused beyond its stated model, or a bug in the safeguards? Please open an issue. There is no separate embargoed channel — this is a small single-purpose tool.
