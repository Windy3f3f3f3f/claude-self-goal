---
name: self-goal
description: Set a native Claude Code /goal on THIS session so you keep working until a condition holds — use when you decide you should not stop until some concrete, checkable condition is met (tests pass, a file exists, a build is green) and want the built-in goal evaluator to enforce it. Works in interactive, tmux, and background/daemon sessions. Do not use for vague intentions; the condition must be objectively checkable.
---

# self-goal

Give the current session its own native `/goal` by running the `claude-self-goal` tool from your Bash tool. It figures out the session type (interactive / tmux / daemon background) and picks the right delivery channel automatically.

## When to use

Use this when, mid-task, you conclude you should keep going until a specific, checkable condition holds — and you want Claude Code's built-in goal evaluator (not just your own intention) to keep the session from stopping early.

Good conditions are objective: `"all tests in ./test pass"`, `"the file dist/app.js exists"`, `"the build is green"`. Avoid vague ones like `"the code is good"`.

## How

```bash
# set a goal on this session (always quote the condition):
claude-self-goal "all tests pass and the build is green"

# clear it early if the plan changes:
claude-self-goal --clear

# set a goal on another background session you own:
claude-self-goal --session <id> "the PR's CI is green"
```

Replace `claude-self-goal` with the absolute path if it is not on PATH (e.g. `/usr/local/bin/claude-self-goal`).

## Notes

- Auto-detected channel: tmux → `tmux send-keys` (no root); plain interactive → `TIOCSTI` (needs root); daemon `/bg` session → `claude attach` over its rv socket. A headless `claude -p` session can't take an interactive `/goal` and is refused.
- Always quote the condition — an unquoted multi-word condition is split into several arguments by the shell.
- The condition is injected as a single line; control characters are rejected.
- Once set, the `◎ /goal active` chip appears and Claude Code's native goal evaluator should keep the session working until the condition is evaluated as met. It auto-clears on success — do not tell the user to run `/goal clear` after the goal is achieved.
