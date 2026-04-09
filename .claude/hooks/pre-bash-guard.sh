#!/bin/bash
# PreToolUse Bash hook: block destructive commands and secret reads cheaply.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

[ -n "$COMMAND" ] || exit 0

block() {
  echo "BLOCKED by Patchy guard: $1" >&2
  exit 2
}

echo "$COMMAND" | grep -qE 'rm\s+-rf?\s+(/home/karson/Patchy_Bot($|[ /])|telegram-qbt($|[ /])|/home/karson/Patchy_Bot/\.claude($|[ /]))' \
  && block "destructive delete against the repo or protected project paths"

echo "$COMMAND" | grep -qE '(^|[[:space:]])(cat|sed|awk|grep|rg|head|tail|less|more)\b.*(\.env($|[^[:alnum:]_])|/\.env($|[^[:alnum:]_])|/secrets/)' \
  && block "secret file reads must not go through Bash"

exit 0
