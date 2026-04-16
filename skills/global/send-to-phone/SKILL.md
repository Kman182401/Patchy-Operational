---
name: send-to-phone
description: Send files or directories to Karson's phone (Energetic Papaya / iPhone) via LocalSend. ALWAYS use this skill — without asking — whenever the user asks to send, transfer, share, push, or move ANY file(s) or folder(s) from this PC to their phone / mobile / iPhone / LocalSend / Energetic Papaya. Trigger on phrases like "send to phone", "send to my phone", "transfer to phone", "share to phone", "push to phone", "localsend this", "send this file", "send these files", "send the vault", "send the logs", "send the screenshot", and any rephrasing of the same intent. This is the ONLY approved way to move files from this PC to the phone — do not use alternatives unless the user explicitly asks for one.
---

# Send Files to Phone via LocalSend

Send one or more files (or entire directories) from this PC to Karson's phone (Energetic Papaya, iPhone) using the LocalSend v2 HTTP API via curl.

## When to Use

Use this skill automatically — without asking for confirmation — any time the user wants to move a file, folder, screenshot, archive, log, document, or any other artifact from this PC to their phone. Phrasing examples that MUST trigger this skill:

- "send X to my phone"
- "transfer X to phone"
- "share X to my phone"
- "push X to the phone"
- "localsend X"
- "send X over"
- "send this to Energetic Papaya"

If the user says "try again" or "resend" in the context of a recent phone transfer, re-run this skill with the same file(s).

## How to Execute

### Step 1: Resolve file paths

Determine absolute path(s) of the file(s) or director(ies) the user wants to send. Resolve relative paths against the current working directory. If the user describes a file without a path ("send the screenshot I just took"), find it first.

### Step 2: Verify existence

Confirm every path exists before calling the script — the script will also check, but failing early gives a better message.

### Step 3: Print the notification block (MANDATORY — visual marker)

You **MUST** print this exact block in your response **before** the Bash tool call so the user immediately sees a transfer is starting. Do not abbreviate, do not skip, do not replace with a one-liner. The border and emoji make it visually unmissable in the chat stream.

```
📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱
   >>> LOCALSEND TRANSFER STARTING <<<
📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱
  Destination : Energetic Papaya (iPhone)
  Protocol    : LocalSend v2 over HTTPS
  Retry budget: 150 seconds (2.5 min grace)
  Files       :
    - <file 1 basename>  (<size>)
    - <file 2 basename>  (<size>)
    ...
  Total       : <count> file(s), <total size>
📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱📱
```

Fill in the `<...>` placeholders with real values. Always print it — even for a single small file.

### Step 4: Run the send script

```bash
bash ~/.claude/skills/send-to-phone/scripts/send.sh <path1> [path2] ...
```

**Required Bash tool parameters:**
- `timeout: 200000` (200 seconds — the script itself caps retries at 150s plus upload time)
- Do NOT use `run_in_background` — the user needs to see progress synchronously

Pass paths as separate arguments. Directories are auto-archived to `.tar.gz` before sending.

### Step 5: Report result

- On success: confirm what was sent and where it will appear on the phone. If you sent a directory, remind the user it arrives as a `.tar.gz` archive that needs extraction (Files app on iOS, or iZip).
- On failure: report the exit code and suggest the fix (see Troubleshooting).

## Retry Behavior (2.5-minute grace window)

The script keeps trying to reach the phone and complete `prepare-upload` for a full **150 seconds** before giving up. This gives the user a grace period to unlock the phone, open LocalSend, or tap Accept if Quick Save is temporarily off. Specifically:

1. **IP discovery** loops through the primary + fallback IPs repeatedly with increasing per-attempt timeouts (6s → 12s) until one responds or the 150s budget is exhausted.
2. **prepare-upload** retries on 204 (Quick Save off) and transient network errors, sleeping ~5s between attempts, until 200 or the budget is exhausted.
3. **Upload** phase runs after a successful prepare with its own 120s per-file timeout (session can't be retried once started — it expires in seconds of idle).

Do not shorten these timeouts. They are deliberate — large files over slow Wi-Fi and locked-screen handshakes both need the headroom.

## How It Works (Why This Is Different From The CLI)

The `localsend` Go CLI dev build installed at `/usr/local/bin/localsend` is **broken** — it returns `Fail to get device info error="Not Found"` even when the phone is reachable and the HTTPS API is responding correctly. Do **not** use the CLI. Our script bypasses it and uses the LocalSend v2 HTTP API directly via curl:

1. `GET /api/localsend/v2/info` on each known IP to pick a reachable one
2. `POST /api/localsend/v2/prepare-upload` with sender info + file manifest (phone auto-accepts when Quick Save is On)
3. `POST /api/localsend/v2/upload?sessionId=X&fileId=Y&token=Z` for each file body

The session from step 2 expires within seconds of idle, so the script does prepare + upload back-to-back.

## LocalSend Protocol Gotchas (read before editing `send.sh`)

- **`fileType` is a category enum, NOT a MIME type.** The `prepare-upload` manifest's `fileType` field must be one of: `image`, `video`, `audio`, `pdf`, `apk`, `text`, `other`. Passing a raw MIME string (`text/markdown`, `application/json`, etc.) causes iOS LocalSend to misroute the payload into its in-app **message viewer** — the phone shows a "Patchy Server sent you a message" popup with an empty body, and the server returns HTTP 204 which looks like "Quick Save is off." The `ls_category()` helper in `scripts/send.sh` does the MIME → category mapping; do not bypass it.
- **Avoid `"text"` for document files.** Even though `text` is a valid enum value, iOS LocalSend routes it to the message viewer (same blank-popup symptom). Send `.md`, `.log`, `.txt`, `.json`, `.yaml`, etc. as `"other"` so they arrive as downloadable files. `ls_category()` already does this — keep it that way.
- **Only send `.mp4`/`.mov` as `"video"`.** iOS LocalSend routes `"video"` payloads to the Photos app, which rejects any container other than mp4/mov-h264 with "unsupported file format". `.mkv`, `.avi`, `.webm`, `.m4v`, and other video containers MUST be sent as `"other"` so they land in the Files app (which accepts any format). `ls_category()` enforces this — do not weaken the check.
- **Session expiry is seconds, not minutes.** Do not insert long sleeps or interactive prompts between `prepare-upload` and the first `upload` call.
- **Quick Save = On bypasses the accept dialog.** With Quick Save off, `prepare-upload` returns 204 and the phone shows a system accept prompt; the retry loop will keep retrying within the 150s budget.

## Phone Details

- **Device name:** Energetic Papaya (iPhone)
- **Port:** 53317
- **Primary IP:** 192.168.50.204 (home Wi-Fi, DaWiFi_2.0)
- **Fallback IPs:** 10.217.8.228 (VPN / other LAN), 100.83.176.127 (Tailscale)
- **Quick Save:** must be **On** for the phone to auto-accept without tapping
- **Encryption:** On (HTTPS, self-signed — `curl -k` required)

The script tries the primary IP first and falls back automatically if it can't reach the API.

## Troubleshooting

| Script exit code | Meaning | Fix |
|---|---|---|
| 1 | No files / file not found | Check the path you passed |
| 2 | Phone not reachable on any IP within 150s | Confirm LocalSend is open on phone, same Wi-Fi, and ping the phone |
| 3 | prepare-upload never returned 200 within 150s | Ensure Quick Save = On on the phone; check manifest validity |
| 4 | Phone declined the transfer (403) | Check LocalSend permissions; retry |
| 5 | Some files uploaded, some failed | Rerun; check per-file HTTP codes in stderr |

### Symptom-based troubleshooting

| Symptom on phone | Likely cause | Fix |
|---|---|---|
| "Patchy Server sent you a message" popup with blank/empty body | `fileType` was sent as a raw MIME (e.g. `text/markdown`) or as `"text"` — iOS routed it into the message viewer instead of the file receiver | Confirm `ls_category()` in `scripts/send.sh` is mapping MIME → category enum (`image`/`video`/`audio`/`pdf`/`apk`/`other`) and that `.md`/`.log`/`.txt`/etc. files resolve to `"other"`. Never put raw `mime` into `files[fid]["fileType"]`. |
| Script prints "Phone returned 204 No Content — Quick Save is off" but Quick Save IS on | Could be the fileType-enum bug above (server 204's when it can't parse/accept the manifest), not actually a Quick Save issue | Check the `fileType` values in `build_prepare_json` before blaming Quick Save. |
| Script exits 0 but file never appears on phone | Uploaded to a stale session, or phone dismissed the message-viewer popup | Rerun; verify fileType enum mapping; check LocalSend history on phone |

If all IPs fail, have the user open LocalSend → Settings → Server info to read the current IPs. Update `PRIMARY_IP` / `FALLBACK_IPS` in `scripts/send.sh` if they've changed permanently.

## Do NOT

- Do not use the `localsend` Go CLI (`localsend send ...`) — it's a broken dev build.
- Do not ask the user for confirmation before sending when they've clearly asked to send something.
- Do not try to send via email, scp, HTTP upload, or any other channel unless the user explicitly asks for an alternative.
- Do not skip the notification block in Step 3 — the visual marker is mandatory every time.
- Do not shorten the 150s retry budget in `send.sh`.
