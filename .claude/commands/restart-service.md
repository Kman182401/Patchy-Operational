---
description: Restart Patchy Bot service, verify health, surface new errors
allowed-tools: Bash
---

Restart `telegram-qbt-bot.service` and verify it came back healthy. Do NOT auto-recover on failure — report and stop.

Steps:

1. Capture the last log timestamp BEFORE restart so we can detect new errors:
   !`journalctl -u telegram-qbt-bot.service -n 1 --no-pager -o short-iso 2>/dev/null | awk '{print $1}'`

2. Restart the service:
   !`sudo systemctl restart telegram-qbt-bot.service`

3. Wait 3 seconds for startup:
   !`sleep 3`

4. Check active state:
   !`systemctl is-active telegram-qbt-bot.service`

5. Tail the last 30 journal lines since restart:
   !`journalctl -u telegram-qbt-bot.service -n 30 --no-pager -o short-iso`

6. Categorize the tailed lines into:
   - 🔴 errors (lines with `ERROR`, `CRITICAL`, `Traceback`, `Exception`)
   - ⚠️ warnings (lines with `WARN`, `WARNING`)
   - ✅ normal startup (everything else)

7. Surface every error or new exception verbatim with its timestamp.

8. Final one-line verdict using exactly one of:
   - ✅ healthy — service active, no errors in last 30 lines
   - ⚠️ degraded — service active but warnings/errors present
   - 🔴 failed — service inactive OR critical errors

If 🔴 failed: STOP. Do not loop, do not retry, do not "fix". Print the verdict and the error block. The user will decide next action.
