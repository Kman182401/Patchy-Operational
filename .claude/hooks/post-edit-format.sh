#!/bin/bash
# PostToolUse hook: very light single-file formatting for Python only.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)

[ -n "$FILE_PATH" ] || exit 0
[ -f "$FILE_PATH" ] || exit 0

case "$FILE_PATH" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$FILE_PATH" >/dev/null 2>&1 || true
    fi
    ;;
esac

exit 0
