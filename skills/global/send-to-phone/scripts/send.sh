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
# Phone must have Quick Save = On for auto-accept (otherwise prepare-upload returns 403).
# prepare-upload + upload must happen quickly (session expires in a few seconds of idle).
# Directories are auto-tarred to a single .tar.gz before sending.

set -euo pipefail

# --- Phone details -----------------------------------------------------------
PRIMARY_IP="192.168.50.204"
FALLBACK_IPS=("10.65.211.242" "10.14.0.2" "100.83.176.127")
PORT="53317"

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
# LocalSend v2 sends one file per upload call. For a directory, tar it into a
# single .tar.gz in /tmp and send that. This is simpler and faster than looping
# the directory tree, and the archive extracts cleanly on the phone.
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
}
trap cleanup EXIT

# --- Pick a reachable IP -----------------------------------------------------
# Hit /api/localsend/v2/info to confirm the phone is responding before we
# commit to a session. Fall back through the known IPs if the primary is down.
pick_ip() {
    # Two passes: fast (6s) then patient (12s). Phones under screen lock can
    # take several seconds to complete the HTTPS handshake with the self-signed
    # cert before the server goroutine responds.
    local candidates=("$PRIMARY_IP" "${FALLBACK_IPS[@]}")
    for max_time in 6 12; do
        for ip in "${candidates[@]}"; do
            if curl -sk --max-time "$max_time" \
                "https://${ip}:${PORT}/api/localsend/v2/info" \
                -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "^200$"; then
                echo "$ip"
                return 0
            fi
        done
    done
    return 1
}

echo ""
echo "=============================================="
echo "  LOCALSEND: SENDING TO PHONE"
echo "=============================================="
echo ""
echo "  Device: Energetic Papaya"
echo "  Files:"
for f in "${PROCESSED_FILES[@]}"; do
    size=$(du -sh "$f" 2>/dev/null | cut -f1 || echo '?')
    echo "    - $(basename "$f")  ($size)"
done
echo ""

PHONE_IP=$(pick_ip) || {
    echo "ERROR: Phone not reachable on any known IP." >&2
    echo "Tried: $PRIMARY_IP ${FALLBACK_IPS[*]}" >&2
    echo "Make sure LocalSend is open on the phone and on the same network." >&2
    exit 2
}
echo "  Reachable at: $PHONE_IP"
echo ""
echo "=============================================="
echo ""

# --- Build prepare-upload JSON -----------------------------------------------
# One entry per file. Each gets a synthetic id "fileN" that we'll pass back in
# the upload URL. The phone maps it to a random token we must also send.
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
        "fileType": mime,
        "preview": "",
    }
print(json.dumps({"info": sender, "files": files}))
PYEOF
}

PREPARE_JSON=$(build_prepare_json "${PROCESSED_FILES[@]}")

# --- prepare-upload ----------------------------------------------------------
# Retry up to 3 times with 2-second spacing to handle the user tapping Accept
# on the phone if Quick Save is off. Each attempt captures HTTP code and body
# separately so we can distinguish rejection (403/204) from network failure.
echo "Preparing upload..."
PREPARE_BODY_FILE=$(mktemp)
trap 'rm -f "$PREPARE_BODY_FILE" /tmp/localsend-upload-resp.txt; cleanup' EXIT

prepare_once() {
    curl -sk --max-time 15 -X POST \
        "https://${PHONE_IP}:${PORT}/api/localsend/v2/prepare-upload" \
        -H "Content-Type: application/json" \
        -d "$PREPARE_JSON" \
        -o "$PREPARE_BODY_FILE" \
        -w "%{http_code}" 2>/dev/null
}

HTTP_CODE=""
for attempt in 1 2 3; do
    HTTP_CODE=$(prepare_once)
    if [[ "$HTTP_CODE" == "200" ]] && [[ -s "$PREPARE_BODY_FILE" ]]; then
        break
    fi
    if [[ "$HTTP_CODE" == "204" ]]; then
        if [[ $attempt -eq 1 ]]; then
            echo "  Phone returned 204 No Content — Quick Save is off."
            echo "  TAP ACCEPT on the phone (retrying for 30s)..."
        fi
        sleep 10
        continue
    fi
    if [[ "$HTTP_CODE" == "403" ]]; then
        echo "ERROR: Phone declined the transfer (HTTP 403)." >&2
        exit 4
    fi
    sleep 2
done

if [[ "$HTTP_CODE" != "200" ]] || [[ ! -s "$PREPARE_BODY_FILE" ]]; then
    echo "ERROR: prepare-upload failed (HTTP ${HTTP_CODE:-timeout})." >&2
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
echo "Session: $SESSION_ID"

# --- upload each file --------------------------------------------------------
SUCCESS_COUNT=0
TOTAL=${#PROCESSED_FILES[@]}
for i in "${!PROCESSED_FILES[@]}"; do
    idx=$((i + 1))
    fpath="${PROCESSED_FILES[$i]}"
    fid="file${idx}"
    token=$(echo "$PREPARE_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['files']['$fid'])")

    echo "Uploading [$idx/$TOTAL]: $(basename "$fpath") ..."
    HTTP_CODE=$(curl -sk --max-time 120 -X POST \
        "https://${PHONE_IP}:${PORT}/api/localsend/v2/upload?sessionId=${SESSION_ID}&fileId=${fid}&token=${token}" \
        -H "Content-Type: application/octet-stream" \
        --data-binary "@${fpath}" \
        -o /tmp/localsend-upload-resp.txt \
        -w "%{http_code}" 2>&1)

    if [[ "$HTTP_CODE" == "200" ]]; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "  OK"
    else
        echo "  FAILED (HTTP $HTTP_CODE): $(cat /tmp/localsend-upload-resp.txt 2>/dev/null)" >&2
    fi
done
rm -f /tmp/localsend-upload-resp.txt

echo ""
if [[ $SUCCESS_COUNT -eq $TOTAL ]]; then
    echo "DONE: All $TOTAL file(s) sent successfully to Energetic Papaya."
    exit 0
else
    echo "PARTIAL: $SUCCESS_COUNT/$TOTAL file(s) sent." >&2
    exit 5
fi
