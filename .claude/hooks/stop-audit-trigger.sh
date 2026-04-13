#!/usr/bin/env bash
# Stop hook: non-instructional summary of uncommitted changes in patchy_bot/.
# Gives Claude awareness of changes without telling it to do anything specific.

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT/telegram-qbt" || exit 0

CHANGED=$(git diff --stat -- patchy_bot/ 2>/dev/null | tail -1)
if [ -n "$CHANGED" ]; then
  echo "📊 Changes detected in patchy_bot/: $CHANGED"
fi
exit 0
