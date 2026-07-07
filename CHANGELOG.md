# Changelog

## 0.1.0

Initial release.

- `claude-self-goal "<condition>"` sets a native Claude Code `/goal` on the current session from inside its own Bash tool.
- Auto method selection: `tmux send-keys` when in tmux (no root), `TIOCSTI` otherwise (needs root).
- Fail-closed pts discovery (must descend from a Claude Code process whose stdin and stdout are the same pts).
- Condition sanitization rejects control characters.
- `--clear`, `--dry-run`, `--method`, and a gated `--unsafe-pts` escape hatch.
- Test suite: discovery + negative (no deps), primitive TIOCSTI (root), and an opt-in end-to-end integration test.
- Verified on Claude Code v2.1.202, Linux, as root.
