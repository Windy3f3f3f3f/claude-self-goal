#!/usr/bin/env bash
# Run the claude-self-goal test suite. Portable across bash, zsh, and POSIX sh
# (no BASH_SOURCE, no `set -o pipefail`), so `./run-tests.sh`, `sh run-tests.sh`
# and `zsh run-tests.sh` all work.
#   discovery + negative : always (no root, no claude)
#   primitive            : runs only as root (TIOCSTI); otherwise self-skips
#   integration          : pts/tiocsti path — RUN_CLAUDE_INTEGRATION=1 (needs claude+root+quota)
#   integration_daemon   : attach path — RUN_CLAUDE_INTEGRATION=1 (needs claude+quota)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PY="${PYTHON:-python3}"
rc=0

for t in test_discovery.py test_negative.py test_primitive.py test_integration.py test_integration_daemon.py; do
  echo "==== $t ===="
  "$PY" "$HERE/test/$t" || rc=1
  echo
done

if [ "$rc" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit "$rc"
