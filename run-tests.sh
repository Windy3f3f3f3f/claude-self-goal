#!/usr/bin/env bash
# Run the claude-self-goal test suite.
#   discovery + negative : always (no root, no claude)
#   primitive            : runs only as root (TIOCSTI); otherwise self-skips
#   integration          : runs only with RUN_CLAUDE_INTEGRATION=1 (needs claude+root+quota)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
rc=0

for t in test_discovery.py test_negative.py test_primitive.py test_integration.py; do
  echo "==== $t ===="
  "$PY" "$HERE/test/$t" || rc=1
  echo
done

if [ "$rc" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "SOME TESTS FAILED"; fi
exit "$rc"
