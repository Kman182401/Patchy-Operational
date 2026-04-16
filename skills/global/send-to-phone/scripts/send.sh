#!/usr/bin/env bash
# LocalSend file sender — sends files to Karson's phone (Energetic Papaya)
# Usage: send.sh <file1> [file2] ...
#
# Uses the LocalSend v2 HTTP API directly via curl instead of the buggy
# `localsend` Go CLI dev build (which returns "Fail to get device info: Not
# Found" even when the phone is reachable).
#
# Protocol (https://github.com/localsend/protocol):
#   1. POST /api/localsend/v2/prepare-upload  — registers files, returns sessionId + per-file tokens
#   2. POST /api/localsend/v2/upload?sessionId=X&fileId=Y&token=Z  — uploads each file body
#
# Phone must have Quick Save = On for auto-accept (otherwise prepare-upload returns 204).
# prepare-upload + upload must happen quickly (session expires in a few seconds of idle).
# Directories are auto-tarred to a single .tar.gz before sending.
#
# Retry budget: 150 seconds (2.5 minutes) total for discovery + prepare-upload.

set -euo pipefail

# --- Phone details -----------------------------------------------------------
PRIMARY_IP="192.168.50.204"
FALLBACK_IPS=("10.217.8.228" "100.83.176.127")
PORT="53317"
RETRY_BUDGET_SECONDS=150

# --- Sender identity (shown on phone) ----------------------------------------
SENDER_ALIAS="Patchy Server"
SENDER_FINGERPRINT="patchy-server-001"

# --- Arg validation ----------------------------------------------------------
if [[ $# -eq 0 ]]; then
    echo "ERROR: No files specified." >&2
    exit 1
fi

for f in "$@"; do
    if [[ ! -e "$f" ]]; then
        echo "ERROR: File not found: $f" >&2
        exit 1
    fi
done

# --- Auto-tar directories ----------------------------------------------------
PROCESSED_FILES=()
CLEANUP_FILES=()
for f in "$@"; do
    if [[ -d "$f" ]]; then
        base=$(basename "$(realpath "$f")")
        archive="/tmp/${base}-$(date +%s).tar.gz"
        echo "Archiving directory '$f' -> $archive ..."
        tar czf "$archive" -C "$(dirname "$(realpath "$f")")" "$base"
        PROCESSED_FILES+=("$archive")
        CLEANUP_FILES+=("$archive")
    else
        PROCESSED_FILES+=("$f")
    fi
done

cleanup() {
    for f in "${CLEANUP_FILES[@]+"${CLEANUP_FILES[@]}"}"; do
        rm -f "$f" 2>/dev/null || true
    done
    rm -f "${PREPARE_BODY_FILE:-}" /tmp/localsend-upload-resp.txt 2>/dev/null || true
}
trap cleanup EXIT

# --- Deadline helpers --------------------------------------------------------
DEADLINE=$(( $(date +%s) + RETRY_BUDGET_SECONDS ))
seconds_left() { echo $(( DEADLINE - $(date +%s) )); }

# --- Pick a reachable IP -----------------------------------------------------
# Loops through candidates until one responds or the overall retry budget is
# exhausted. Per-attempt timeout alternates 6s/12s so we burn ~18s per full
# pass — giving us ~8 passes before the 150s budget runs out.
pick_ip() {
    local candidates=("$PRIMARY_IP" "${FALLBACK_IPS[@]}")
    local pass=0
    while (( $(seconds_left) > 0 )); do
        pass=$(( pass + 1 ))
        local max_time=6
        (( pass % 2 == 0 )) && max_time=12
        for ip in "${candidates[@]}"; do
            (( $(seconds_left) > 0 )) || return 1
            if curl -sk --max-time "$max_time" \
                "https://${ip}:${PORT}/api/localsend/v2/info" \
                -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "^200$"; then
                echo "$ip"
                return 0
            fi
        done
        echo "  IP discovery pass $pass — no phone yet ($(seconds_left)s left)..." >&2
        sleep 1
    done
    return 1
}

echo ""
echo "📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱"
echo "   >>> LOCALSEND TRANSFER IN PROGRESS <<<"
echo "📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱"
echo "  Destination : Energetic Papaya (iPhone)"
echo "  Retry budget: ${RETRY_BUDGET_SECONDS}s (2.5 min grace)"
echo "  Files       :"
for f in "${PROCESSED_FILES[@]}"; do
    size=$(du -sh "$f" 2>/dev/null | cut -f1 || echo '?')
    echo "    - $(basename "$f")  ($size)"
done
echo "📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱"
echo ""
echo "Scanning for phone (will retry up to ${RETRY_BUDGET_SECONDS}s)..."

PHONE_IP=$(pick_ip) || {
    echo "ERROR: Phone not reachable on any known IP within ${RETRY_BUDGET_SECONDS}s." >&2
    echo "Tried: $PRIMARY_IP ${FALLBACK_IPS[*]}" >&2
    echo "Make sure LocalSend is open on the phone and on the same network." >&2
    exit 2
}
echo "  ✓ Reachable at: $PHONE_IP  ($(seconds_left)s of budget remaining)"
echo ""

# --- Build prepare-upload JSON -----------------------------------------------
build_prepare_json() {
    python3 - "$@" <<'PYEOF'
import json, sys, os, mimetypes
sender = {
    "alias": "Patchy Server",
    "version": "2.1",
    "deviceModel": "Linux",
    "deviceType": "desktop",
    "fingerprint": "patchy-server-001",
    "download": False,
}
# LocalSend v2 fileType is a CATEGORY enum, not a MIME type.
# Allowed: image, video, audio, pdf, text, apk, other.
# We deliberately avoid "text" because the iOS client treats it as an
# in-app message snippet (shows "sent you a message" popup with empty body)
# instead of a downloadable file. Markdown/logs/etc go as "other".
def ls_category(mime: str, name: str) -> str:
    # iOS Photos app only accepts a narrow set of video containers
    # (mp4/mov/m4v-h264). Sending .mkv/.avi/.webm as "video" makes iOS
    # LocalSend route them to Photos, which rejects them with "unsupported
    # file format". Routing as "other" lands them in the Files app, which
    # accepts any container.
    lower = name.lower()
    ios_photo_ok_video = lower.endswith((".mp4", ".mov"))
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/") and ios_photo_ok_video:
        return "video"
    if mime.startswith("video/"):
        return "other"  # .mkv, .avi, .webm, .m4v, etc — Files app
    if mime.startswith("audio/"):
        return "audio"
    if mime == "application/pdf":
        return "pdf"
    if mime == "application/vnd.android.package-archive" or lower.endswith(".apk"):
        return "apk"
    return "other"

files = {}
for i, path in enumerate(sys.argv[1:], start=1):
    fid = f"file{i}"
    name = os.path.basename(path)
    size = os.path.getsize(path)
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    files[fid] = {
        "id": fid,
        "fileName": name,
        "size": size,
        "fileType": ls_category(mime, name),
        "preview": "",
    }
print(json.dumps({"info": sender, "files": files}))
PYEOF
}

PREPARE_JSON=$(build_prepare_json "${PROCESSED_FILES[@]}")

# --- prepare-upload ----------------------------------------------------------
# Retry until 200 or the retry budget is exhausted. 204 means Quick Save is
# off and the user needs to tap Accept — we keep retrying to give them grace.
echo "Preparing upload..."
PREPARE_BODY_FILE=$(mktemp)

prepare_once() {
    curl -sk --max-time 15 -X POST \
        "https://${PHONE_IP}:${PORT}/api/localsend/v2/prepare-upload" \
        -H "Content-Type: application/json" \
        -d "$PREPARE_JSON" \
        -o "$PREPARE_BODY_FILE" \
        -w "%{http_code}" 2>/dev/null
}

HTTP_CODE=""
prepare_attempt=0
while (( $(seconds_left) > 0 )); do
    prepare_attempt=$(( prepare_attempt + 1 ))
    HTTP_CODE=$(prepare_once || echo "000")
    if [[ "$HTTP_CODE" == "200" ]] && [[ -s "$PREPARE_BODY_FILE" ]]; then
        break
    fi
    if [[ "$HTTP_CODE" == "204" ]]; then
        if (( prepare_attempt == 1 )); then
            echo "  Phone returned 204 — Quick Save is off. TAP ACCEPT on the phone."
        fi
        echo "  Waiting for Accept... ($(seconds_left)s of budget remaining)"
        sleep 5
        continue
    fi
    if [[ "$HTTP_CODE" == "403" ]]; then
        echo "ERROR: Phone declined the transfer (HTTP 403)." >&2
        exit 4
    fi
    echo "  prepare-upload attempt $prepare_attempt -> HTTP $HTTP_CODE; retrying ($(seconds_left)s left)..." >&2
    sleep 3
done

if [[ "$HTTP_CODE" != "200" ]] || [[ ! -s "$PREPARE_BODY_FILE" ]]; then
    echo "ERROR: prepare-upload failed within ${RETRY_BUDGET_SECONDS}s (last HTTP ${HTTP_CODE:-timeout})." >&2
    echo "  Body: $(cat "$PREPARE_BODY_FILE" 2>/dev/null)" >&2
    echo "  Fix: open LocalSend on phone, set Quick Save = On, stay on Receive tab." >&2
    exit 3
fi

PREPARE_RESPONSE=$(cat "$PREPARE_BODY_FILE")

if ! echo "$PREPARE_RESPONSE" | python3 -c "import sys,json; json.loads(sys.stdin.read())['sessionId']" >/dev/null 2>&1; then
    echo "ERROR: prepare-upload returned invalid JSON:" >&2
    echo "  $PREPARE_RESPONSE" >&2
    exit 4
fi

SESSION_ID=$(echo "$PREPARE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['sessionId'])")
echo "  ✓ Session: $SESSION_ID"
echo ""

# --- upload each file --------------------------------------------------------
SUCCESS_COUNT=0
TOTAL=${#PROCESSED_FILES[@]}
for i in "${!PROCESSED_FILES[@]}"; do
    idx=$((i + 1))
    fpath="${PROCESSED_FILES[$i]}"
    fid="file${idx}"
    token=$(echo "$PREPARE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['files']['$fid'])")

    echo "📤 Uploading [$idx/$TOTAL]: $(basename "$fpath") ..."
    HTTP_CODE=$(curl -sk --max-time 600 -X POST \
        "https://${PHONE_IP}:${PORT}/api/localsend/v2/upload?sessionId=${SESSION_ID}&fileId=${fid}&token=${token}" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@${fpath}" \
        -o /tmp/localsend-upload-resp.txt \
        -w "%{http_code}" 2>&1)

    if [[ "$HTTP_CODE" == "200" ]]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "  ✓ OK"
    else
        echo "  ✗ FAILED (HTTP $HTTP_CODE): $(cat /tmp/localsend-upload-resp.txt 2>/dev/null)" >&2
    fi
done

echo ""
if [[ $SUCCESS_COUNT -eq $TOTAL ]]; then
    echo "✅ DONE: All $TOTAL file(s) sent successfully to Energetic Papaya."
    exit 0
else
    echo "⚠️  PARTIAL: $SUCCESS_COUNT/$TOTAL file(s) sent." >&2
    exit 5
fi
