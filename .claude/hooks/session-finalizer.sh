#!/bin/bash
# Stop hook: Auto-records session end to sessions.md from event buffer
# Safety net — fires if Claude Code didn't write a manual session entry
# Rotates the event buffer and keeps last 5 archives

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

[ -z "$CWD" ] && exit 0

MEMORY_DIR="$CWD/.claude/memory"
BUFFER="$MEMORY_DIR/.event-buffer.jsonl"
SESSIONS_FILE="$MEMORY_DIR/sessions.md"

[ -d "$MEMORY_DIR" ] || exit 0

DATE_DISPLAY=$(date +"%Y-%m-%d %H:%M")
DATE_STAMP=$(date +"%Y%m%d-%H%M%S")

if [ -f "$BUFFER" ] && [ -s "$BUFFER" ]; then
  EVENT_COUNT=$(wc -l < "$BUFFER" | tr -d ' ')

  # Extract unique file paths touched (non-empty, deduplicated, limit 10)
  TOUCHED=$(jq -r '.path // empty' "$BUFFER" 2>/dev/null \
    | grep -v '^$' \
    | sort -u \
    | head -10 \
    | sed 's/^/  - /' \
    | head -c 800)

  # Extract bash commands run (limit 5)
  BASH_CMD_LIST=$(jq -r 'select(.tool=="bash") | .cmd // empty' "$BUFFER" 2>/dev/null \
    | grep -v '^$' \
    | head -5 \
    | sed 's/^/  - /' \
    | head -c 500)

  # Write auto-generated session entry to TOP of sessions.md (after header block)
  ENTRY="
## [$DATE_DISPLAY] Auto-recorded session end
- **Events captured:** $EVENT_COUNT tool operations
- **Files touched:**
${TOUCHED:-  (none recorded)}
- **Bash commands run (sample):**
${BASH_CMD_LIST:-  (none recorded)}
- **Note:** If Claude Code wrote a manual session entry above, this is a backup — the manual entry is authoritative.

---
"

  # Prepend entry after header — only if sessions.md still exists.
  # (File was retired 2026-04-13; auto-memory is canonical now.)
  if [ -f "$SESSIONS_FILE" ]; then
    TEMP=$(mktemp)
    awk -v entry="$ENTRY" '
      /^---$/ && !done { print; print entry; done=1; next }
      { print }
    ' "$SESSIONS_FILE" > "$TEMP" 2>/dev/null && mv "$TEMP" "$SESSIONS_FILE"
  fi

  # Rotate buffer
  ARCHIVE="${BUFFER%.jsonl}-${DATE_STAMP}.jsonl"
  mv "$BUFFER" "$ARCHIVE" 2>/dev/null

  # Keep only last 5 archives
  find "$(dirname "$BUFFER")" -maxdepth 1 -name ".event-buffer-*.jsonl" -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | tail -n +6 | cut -d' ' -f2- | xargs -r rm -f 2>/dev/null
fi

exit 0
