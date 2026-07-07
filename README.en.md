# claude-self-goal

[简体中文](./README.md) · English

Let a running Claude Code session set its own native `/goal` — with no human typing. Works for interactive, tmux, and background sessions.

> Claude Code's `/goal <condition>` (v2.1.139+) makes a session keep working until a condition holds; every time it tries to stop, an independent evaluator checks whether the condition is met. Normally only a human can type that command. claude-self-goal delivers the same line into the session programmatically, so an autonomous agent can give *itself* a goal.

Verified on Claude Code v2.1.202, Linux.

## The problem

There is no programmatic way to set the native `/goal` — no hook field, no `settings.json` key, no environment variable, no CLI flag, no API. Hooks are explicitly designed not to trigger slash commands, and `claude -p "/goal ..."` deadlocks on v2.1.202. The only way to engage the real goal machinery is to put the text `/goal <condition>` into the session's input, exactly as a human would type it.

The catch is that different session types receive input through different channels. claude-self-goal figures out which kind of session you are, then uses the right channel.

## How it works

It walks up the process tree to the **nearest** Claude Code process — only that one, never reaching past it to a parent session — and picks a delivery method from its type:

- session runs inside **tmux**: `tmux send-keys` to your pane, no root needed;
- **plain interactive** session (its pts is its controlling terminal): `TIOCSTI` the line into the pts, needs root;
- **daemon-managed background** session (`claude --bg`, phone remote): its input arrives over a unix socket `rv/<session-id>.sock`, not a pts, so it uses the official client `claude attach <id>` to inject;
- **headless `claude -p`** (stdin is a pipe): no interactive input channel — refused.

Once the channel is chosen, the session receives `/goal <condition>` as ordinary input, so the real `/goal` engages: the `◎ /goal active` chip, the independent completion evaluator, keep-working-until-met.

## Quickstart

```bash
# from inside a Claude Code session's Bash tool (or a skill). Always quote the condition:
claude-self-goal "all tests pass and the build is green"

# clear it early if the plan changes:
claude-self-goal --clear

# see which channel it would use without injecting anything:
claude-self-goal --dry-run "the migration is complete"

# set a goal on another background session (an orchestrator tasking a worker):
claude-self-goal --session 994f658d "the PR's CI is green"
```

## Install

```bash
git clone https://github.com/Windy3f3f3f3f/claude-self-goal.git
cd claude-self-goal
sudo ln -s "$PWD/claude-self-goal" /usr/local/bin/claude-self-goal
```

Needs Python 3.6+ and Linux. The tmux path needs `tmux`; the TIOCSTI path needs root; the attach path needs `claude` on PATH.

## Use as a Claude Code skill

Copy `skill/SKILL.md` into `~/.claude/skills/self-goal/SKILL.md` (fix the path to the executable). Once installed, the model can call it in one step to give itself a goal. See [`skill/SKILL.md`](skill/SKILL.md).

## Usage

| Command | Effect |
|---|---|
| `claude-self-goal "<condition>"` | set a native `/goal` on the current session (auto channel) |
| `claude-self-goal --clear` | clear the current goal (`/goal clear`) |
| `claude-self-goal --dry-run "<condition>"` | print the chosen channel and target; inject nothing |
| `claude-self-goal --session <id> "<condition>"` | set a goal on a specific daemon background session (cross-session) |
| `claude-self-goal --method tmux\|tiocsti\|attach\|auto` | force a channel (default `auto`) |
| `claude-self-goal --unsafe-pts /dev/pts/N ... --i-understand-this-can-inject-keystrokes` | inject into an explicit pts (dangerous; skips discovery, forces tiocsti) |

Exit codes: `0` ok · `2` usage · `3` no injectable target · `4` not root (tiocsti) · `5` injection failed · `6` bad condition (control characters).

The condition is sanitized: any control character (CR, LF, ESC, …) is rejected, so the line can't smuggle a second command in. Also **quote the condition** on the command line — an unquoted multi-word condition splits into several args under bash, and behaves differently under zsh.

Setting `CLAUDE_SELF_GOAL_DRY_RUN=1` forces dry-run — nothing is ever injected. Test suites and CI use it as a hard backstop.

## Requirements and limits

Linux only — discovery uses `/proc`, tiocsti uses the Linux `TIOCSTI` ioctl. The TIOCSTI path needs root (or `CAP_SYS_ADMIN`, and a kernel/container that permits it); the tmux and attach paths need no root. A headless `claude -p` session (piped stdin) has no interactive input channel and can't be done. It is also coupled to Claude Code's current input handling and daemon layout (verified on v2.1.202); a future change there could break it.

## Security

The tiocsti path uses `TIOCSTI`, a privileged keystroke-injection primitive the kernel restricts by default; the attach path uses the official client. Both inject input into a session, and both are for automating your own Claude Code sessions on a machine you control — not for shared or multi-user hosts, and `--session` should only point at your own background sessions. Please read [`SECURITY.md`](SECURITY.md) first.

## How it works, in depth

The terminal/socket topology of the three session types, why pts injection is inert for daemon sessions, how attach gets around it, and why "classify only the nearest ancestor" matters are written up in [`docs/HOW-IT-WORKS.md`](docs/HOW-IT-WORKS.md).

## Testing

```bash
./run-tests.sh                            # discovery + negative (plus primitive if root); runs under bash/zsh/sh
RUN_CLAUDE_INTEGRATION=1 ./run-tests.sh   # also two end-to-end tests (tiocsti and attach paths; needs claude + quota)
```

## License

MIT — see [`LICENSE`](LICENSE).
