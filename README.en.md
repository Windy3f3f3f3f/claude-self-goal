# claude-self-goal

[简体中文](./README.md) · English

Let a running Claude Code session set its own native `/goal` — with no human typing, no tmux pane, and no `claude -p`. Background sessions work too.

> Claude Code's `/goal <condition>` (v2.1.139+) makes a session keep working until a condition holds; every time it tries to stop, an independent evaluator checks whether the condition is met. Normally only a human can type that command. claude-self-goal delivers the same line into the session programmatically, so an autonomous agent can give *itself* a goal.

Verified on Claude Code v2.1.202, Linux, as root.

## The problem

There is no programmatic way to set the native `/goal` — no hook field, no `settings.json` key, no environment variable, no CLI flag, no API. Hooks are explicitly designed not to trigger slash commands, and `claude -p "/goal ..."` deadlocks on v2.1.202. The only way to engage the real goal machinery is to put the text `/goal <condition>` into the session's input, exactly as a human would type it.

If the session runs inside tmux, `tmux send-keys` can do that. The hard case is a background, non-tmux session — it has no pane to type into. claude-self-goal covers both.

## How it works

Two steps. First it walks up the process tree to find the Claude Code process you are running inside, requiring that its stdin and stdout point at the same pts. This step is fail-closed: if no such Claude ancestor is found, it refuses rather than guessing at some nearby terminal. Then it picks a delivery method automatically — inside tmux it uses `tmux send-keys` to your pane, which needs no root; otherwise it uses `TIOCSTI` to push the line into that pts, which needs root.

The session receives it as ordinary input, so the real `/goal` engages: the `◎ /goal active` chip, the independent completion evaluator, and keep-working-until-met. If you set it while the session is busy, the line queues and takes effect at the next turn boundary.

## Quickstart

```bash
# from inside a Claude Code session's Bash tool (or a skill):
claude-self-goal "all tests pass and the build is green"

# clear it early if the plan changes:
claude-self-goal --clear

# see what it would do without injecting anything:
claude-self-goal --dry-run "the migration is complete"
```

## Install

```bash
git clone https://github.com/Windy3f3f3f3f/claude-self-goal.git
cd claude-self-goal
# put it on PATH (a symlink keeps it updatable):
sudo ln -s "$PWD/claude-self-goal" /usr/local/bin/claude-self-goal
```

Needs Python 3.6+ and Linux. The tmux path needs `tmux`; the non-tmux path needs root (see Security).

## Use as a Claude Code skill

Copy `skill/SKILL.md` into `~/.claude/skills/self-goal/SKILL.md` (fix the path to the executable). Once installed, the model can call it in one step to give itself a goal. See [`skill/SKILL.md`](skill/SKILL.md).

## Usage

| Command | Effect |
|---|---|
| `claude-self-goal "<condition>"` | set a native `/goal` on the current session |
| `claude-self-goal --clear` | clear the current goal (`/goal clear`) |
| `claude-self-goal --dry-run "<condition>"` | print the chosen method and target; inject nothing |
| `claude-self-goal --method tmux\|tiocsti\|auto` | force a delivery method (default `auto`) |
| `claude-self-goal --unsafe-pts /dev/pts/N ... --i-understand-this-can-inject-keystrokes` | inject into an explicit pts (dangerous; discovery bypassed) |

Exit codes: `0` ok · `2` usage · `3` no Claude target found · `4` not root (tiocsti) · `5` injection failed · `6` bad condition (control characters).

The condition is sanitized first: any control character (CR, LF, ESC, …) is rejected, so the line can't smuggle a second command into the session.

## Requirements and limits

Linux only — discovery uses `/proc`, injection uses the Linux `TIOCSTI` ioctl. The non-tmux path needs root (or `CAP_SYS_ADMIN`); the tmux path does not. It won't work on a headless `claude -p` session whose stdin is a pipe or `/dev/null` — there is no pts to inject into, and such a session can't run interactive `/goal` anyway. It is also coupled to Claude Code's current input handling (verified on v2.1.202); a future UI or input change could break it.

## Security

This tool uses `TIOCSTI`, a privileged keystroke-injection primitive the kernel restricts by default. It is meant for automating your own Claude Code sessions on a machine you control — not for shared or multi-user hosts, and not for sessions you do not own. Please read [`SECURITY.md`](SECURITY.md) before using it.

## How it works, in depth

The terminal topology of interactive vs. background sessions, why every non-injection approach fails, and how the mechanism holds together are written up in [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md).

## Roadmap

A rootless path for *newly launched* sessions: start the session under a small pty-proxy or Unix-socket wrapper that writes the pty master directly, avoiding `TIOCSTI`. It wouldn't cover already-running sessions (that's what this version is for), but it's safer and more portable.

## Testing

```bash
./run-tests.sh                            # discovery + negative (plus primitive if root)
RUN_CLAUDE_INTEGRATION=1 ./run-tests.sh   # also the full end-to-end test (needs claude + root + quota)
```

## License

MIT — see [`LICENSE`](LICENSE).
