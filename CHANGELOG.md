# Changelog

## 0.2.0

Daemon/background session support, and a correctness fix for how sessions are targeted.

- **Daemon background sessions** (`claude --bg`, phone remote) are now supported. Their input arrives over a `rv/<id>.sock` unix socket rather than a pts, so the tool injects via `claude attach <id>` (the official client) instead of `TIOCSTI`. The session id is auto-discovered from the process's own listening rv socket.
- **`--session <id>`**: set a goal on another daemon background session (cross-session, e.g. an orchestrator tasking a worker).
- **Auto method selection** now classifies the session by type: tmux → `tmux send-keys`, interactive pts → `TIOCSTI`, daemon → `claude attach`, headless `claude -p` → refused.
- **Correctness fix (honesty):** the pts path now requires the pts to be the process's controlling terminal, so daemon sessions are handled via attach instead of a `TIOCSTI` that silently did nothing.
- **Correctness fix (targeting):** discovery now classifies only the *nearest* Claude ancestor and never reaches past it, so a background session spawned from an interactive foreground session can't have a goal injected into the foreground parent.
- **`--unsafe-pts`** is validated up front and forces the tiocsti method (never auto-routes to attach).
- **`CLAUDE_SELF_GOAL_DRY_RUN=1`** safety valve forces dry-run; test suites set it so no test can inject into a live session.
- **`run-tests.sh`** is now portable across bash, zsh, and POSIX sh.
- Tests: fail-closed discovery regressions (nearest-ancestor, rv-socket edge cases), `--session` negatives, and a second end-to-end integration test for the attach path.

## 0.1.0

Initial release.

- `claude-self-goal "<condition>"` sets a native Claude Code `/goal` on the current session from inside its own Bash tool.
- Auto method selection: `tmux send-keys` when in tmux (no root), `TIOCSTI` otherwise (needs root).
- Fail-closed pts discovery, condition sanitization, `--clear`, `--dry-run`, `--method`, and a gated `--unsafe-pts` escape hatch.
- Verified on Claude Code v2.1.202, Linux, as root.
