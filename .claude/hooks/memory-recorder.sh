#!/bin/bash
# PostToolUse hook: cheap event logging for writes/edits/bash only.

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

[ -n "$TOOL_NAME" ] || exit 0
[ -n "$CWD" ] || exit 0

case "$TOOL_NAME" in
  bash|write_file|create_file|str_replace_based_edit|edit_file|patch) ;;
  *) exit 0 ;;
esac

MEMORY_DIR="$CWD/.claude/memory"
BUFFER="$MEMORY_DIR/.event-buffer.jsonl"
[ -d "$MEMORY_DIR" ] || exit 0

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ "$TOOL_NAME" = "bash" ]; then
  CMD_RAW=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null | head -c 180)
  printf '{"ts":"%s","tool":"bash","cmd":%s}\n' \
    "$TIMESTAMP" \
    "$(printf '%s' "$CMD_RAW" | jq -Rcs . 2>/dev/null || echo '""')" \
    >> "$BUFFER"
  exit 0
fi

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // empty' 2>/dev/null)
printf '{"ts":"%s","tool":"%s","path":%s}\n' \
  "$TIMESTAMP" \
  "$TOOL_NAME" \
  "$(printf '%s' "$FILE_PATH" | jq -Rcs . 2>/dev/null || echo '""')" \
  >> "$BUFFER"

exit 0
