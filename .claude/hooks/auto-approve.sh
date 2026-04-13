#!/usr/bin/env bash
# PermissionRequest hook: keep zero-prompt behavior with a lightweight log.
TOOL_NAME=$(jq -r '.tool_name // "unknown"' 2>/dev/null)
echo "[$(date -Iseconds)] auto-approved: ${TOOL_NAME}" >> /tmp/cc-auto-approve.log
cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PermissionRequest","permissionDecision":"allow","permissionDecisionReason":"Auto-approved by Patchy project hook"}}
EOF
exit 0
