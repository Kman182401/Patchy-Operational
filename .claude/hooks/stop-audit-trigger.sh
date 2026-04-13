#!/usr/bin/env bash
# Stop hook: auto-trigger post-changes-audit with right-sized mode
# Counts uncommitted changed lines to determine quick/standard/deep

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT/telegram-qbt" || exit 0

# Count lines changed (staged + unstaged) in patchy_bot/ only
CHANGED_LINES=$(git diff --numstat -- patchy_bot/ 2>/dev/null | awk '{s+=$1+$2} END {print s+0}')

if [ "$CHANGED_LINES" -eq 0 ]; then
    # No changes to audit
    exit 0
fi

if [ "$CHANGED_LINES" -lt 5 ]; then
    MODE="quick"
elif [ "$CHANGED_LINES" -lt 50 ]; then
    MODE="standard"
else
    MODE="deep"
fi

echo ""
echo "━━━ POST-CHANGES AUDIT ━━━"
echo "Changed lines detected: $CHANGED_LINES → Mode: $MODE"
echo ""
echo "Run the post-changes-audit skill now in $MODE mode."
echo "Review the changes made in this session for correctness, performance, efficiency, and security."
echo "Use /post-changes-audit $MODE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━"
