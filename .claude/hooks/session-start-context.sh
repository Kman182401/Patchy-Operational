#!/usr/bin/env bash
# SessionStart hook: inject task-master context
# Outputs task list so Claude has project task state at session start

cd ~/Patchy_Bot || exit 0

echo "=== CURRENT TASKS ==="
task-master list 2>/dev/null || echo "(task-master not available)"
echo "=== END TASKS ==="
