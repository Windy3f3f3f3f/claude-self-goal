---
name: self-goal
description: Set a native Claude Code /goal on THIS session so you keep working until a condition holds — use when you decide you should not stop until some concrete, checkable condition is met (tests pass, a file exists, a build is green) and want the built-in goal evaluator to enforce it. Works in background/non-tmux sessions. Do not use for vague intentions; the condition must be objectively checkable.
---

# self-goal

Give the current session its own native `/goal` by running the `claude-self-goal` tool from your Bash tool.

## When to use

Use this when, mid-task, you conclude you should keep going until a specific, checkable condition holds — and you want Claude Code's built-in goal evaluator (not just your own intention) to keep the session from stopping early.

Good conditions are objective: `"all tests in ./test pass"`, `"the file dist/app.js exists"`, `"the build is green"`. Avoid vague ones like `"the code is good"`.

## How

```bash
# set a goal on this session:
claude-self-goal "all tests pass and the build is green"

# clear it early if the plan changes:
claude-self-goal --clear
```

Replace `claude-self-goal` with the absolute path if it is not on PATH (e.g. `/usr/local/bin/claude-self-goal`).

## Notes

- In tmux it uses `tmux send-keys` (no root). Otherwise it uses `TIOCSTI`, which needs root.
- The condition is injected as a single line; control characters are rejected.
- If it prints "no Claude Code session pts found", the session is headless (piped stdin) and cannot take an interactive `/goal`.
- Once set, the `◎ /goal active` chip appears and the session will not stop until the condition is evaluated as met. It auto-clears on success — do not tell the user to run `/goal clear` after the goal is achieved.
