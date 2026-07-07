# claude-self-goal

Let a running **Claude Code** session set its own native `/goal` — from inside the session's own Bash tool, with no human typing, no tmux pane required, and no `claude -p`.

> `/goal <condition>` is a built-in Claude Code command (v2.1.139+): the session keeps working across turns until an independent evaluator judges the condition met. Normally only a human can type it. `claude-self-goal` delivers that same line to the session programmatically, so an autonomous agent can give *itself* a goal.

Verified on Claude Code **v2.1.202**, Linux, as root.

## The problem

There is no official way to set the native `/goal` programmatically — no hook field, no `settings.json` key, no environment variable, no CLI flag, no API. Hooks explicitly cannot trigger slash commands, and `claude -p "/goal ..."` deadlocks (v2.1.202). The only way to fire the *native* goal machinery is to deliver the text `/goal <condition>` to the session's input, exactly as if a human typed it.

If your session runs inside **tmux**, you can already do that with `tmux send-keys`. The hard case is a **background / non-tmux** session that has no pane to type into. `claude-self-goal` handles both.

## What it does

1. Finds the Claude Code process you descend from whose stdin **and** stdout are the same pts (its interactive input terminal). Discovery is **fail-closed**: if no such Claude ancestor is found, it refuses to inject.
2. Delivers `/goal <condition>` to it, auto-selecting the method:
   - **inside tmux** → `tmux send-keys` to your pane (no root needed — preferred);
   - **otherwise** → `TIOCSTI` the line into the session's pts (needs root).

The session receives it as ordinary input, so the real `/goal` engages: the `◎ /goal active` chip, the independent completion evaluator, and keep-working-until-met. If you set the goal mid-turn, it queues and applies at the turn boundary.

## Quickstart

```bash
# from inside a Claude Code session's Bash tool (or a skill):
claude-self-goal "all tests pass and the build is green"

# clear it early:
claude-self-goal --clear

# see what would happen without injecting:
claude-self-goal --dry-run "the migration is complete"
```

## Install

```bash
git clone https://github.com/Windy3f3f3f3f/claude-self-goal.git
cd claude-self-goal
# put it on PATH (symlink keeps it updatable):
sudo ln -s "$PWD/claude-self-goal" /usr/local/bin/claude-self-goal
```

Requires Python 3.6+ and Linux. The tmux path needs `tmux`; the non-tmux path needs root (see Security).

## Use as a Claude Code skill

Copy `skill/SKILL.md` into `~/.claude/skills/self-goal/SKILL.md` (adjust the path to the executable). The skill lets the model call the tool in one step to give itself a goal. See [`skill/SKILL.md`](skill/SKILL.md).

## Usage

| Command | Effect |
|---|---|
| `claude-self-goal "<condition>"` | set a native `/goal` on the current session |
| `claude-self-goal --clear` | clear the current goal (`/goal clear`) |
| `claude-self-goal --dry-run "<condition>"` | show the chosen method + target, inject nothing |
| `claude-self-goal --method tmux\|tiocsti\|auto` | force a delivery method (default `auto`) |
| `claude-self-goal --unsafe-pts /dev/pts/N ... --i-understand-this-can-inject-keystrokes` | inject into an explicit pts (dangerous; discovery bypassed) |

Exit codes: `0` ok · `2` usage · `3` no Claude target found · `4` not root (tiocsti) · `5` injection failed · `6` bad condition (control characters).

The goal condition is sanitized: any control character (CR, LF, ESC, …) is rejected, so the text cannot smuggle a second command into the session.

## Requirements & limitations

- **Linux only.** Uses `/proc` for discovery and the Linux `TIOCSTI` ioctl.
- **The non-tmux path needs root** (or `CAP_SYS_ADMIN`). The tmux path does not.
- **Won't work on a headless `claude -p` session** whose stdin is a pipe or `/dev/null` — there is no pts to inject into. Such sessions can't run interactive `/goal` anyway.
- **Version-coupled.** It depends on Claude Code's current input handling (verified on v2.1.202). A future UI/input change could break it.

## Security

This tool uses `TIOCSTI`, a privileged keystroke-injection primitive that the kernel restricts by default. It is designed for automating **your own** Claude Code sessions on a machine you control. It is **not** for shared / multi-user hosts and **not** for sessions you do not own. Please read [`SECURITY.md`](SECURITY.md) before using it.

## How it works

The mechanism, the topology of interactive vs. background sessions, and why every non-injection approach fails are written up in [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md).

## Roadmap

- A rootless option for *newly launched* sessions: start the session under a small pty-proxy / Unix-socket wrapper that writes the pty master directly, avoiding `TIOCSTI` entirely. This would not cover already-running sessions (that's what v1 is for) but is safer and more portable.

## Testing

```bash
./run-tests.sh                       # discovery + negative (+ primitive if root)
RUN_CLAUDE_INTEGRATION=1 ./run-tests.sh   # also the full end-to-end test (needs claude + root + quota)
```

## License

MIT — see [`LICENSE`](LICENSE).
