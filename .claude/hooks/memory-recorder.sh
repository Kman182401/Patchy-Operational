#!/bin/bash
# PostToolUse hook: Lightweight event buffer for Patchy Bot memory system
# Appends a JSON line to .event-buffer.jsonl after every tool operation
# Fast by design — one jq parse + one file append

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

[ -z "$TOOL_NAME" ] && exit 0
[ -z "$CWD" ] && exit 0

MEMORY_DIR="$CWD/.claude/memory"
BUFFER="$MEMORY_DIR/.event-buffer.jsonl"

# Only operate if memory directory exists for this project
[ -d "$MEMORY_DIR" ] || exit 0

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Capture relevant fields by tool type
case "$TOOL_NAME" in
  write_file|create_file)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // .tool_input.file_path // empty' 2>/dev/null)
    printf '{"ts":"%s","tool":"%s","path":%s}\n' \
      "$TIMESTAMP" "$TOOL_NAME" \
      "$(printf '%s' "$FILE_PATH" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')" \
      >> "$BUFFER"
    ;;
  str_replace_based_edit|edit_file|patch)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // empty' 2>/dev/null)
    printf '{"ts":"%s","tool":"%s","path":%s}\n' \
      "$TIMESTAMP" "$TOOL_NAME" \
      "$(printf '%s' "$FILE_PATH" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')" \
      >> "$BUFFER"
    ;;
  bash)
    CMD_RAW=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null | head -c 250)
    CMD_JSON=$(printf '%s' "$CMD_RAW" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')
    printf '{"ts":"%s","tool":"bash","cmd":%s}\n' "$TIMESTAMP" "$CMD_JSON" >> "$BUFFER"
    ;;
  read_file|view_file)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.path // empty' 2>/dev/null)
    printf '{"ts":"%s","tool":"read","path":%s}\n' \
      "$TIMESTAMP" \
      "$(printf '%s' "$FILE_PATH" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')" \
      >> "$BUFFER"
    ;;
  *)
    printf '{"ts":"%s","tool":"%s"}\n' "$TIMESTAMP" "$TOOL_NAME" >> "$BUFFER"
    ;;
esac

exit 0
