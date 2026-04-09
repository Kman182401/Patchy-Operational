#!/usr/bin/env bash
# PermissionRequest hook: keep zero-prompt behavior.
cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","permissionDecision":"allow","permissionDecisionReason":"Auto-approved by Patchy project hook"}}
EOF
exit 0
