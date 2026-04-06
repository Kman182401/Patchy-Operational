---
name: restart
description: Restart the Patchy Bot systemd service and verify it started successfully. Use when the user says "restart", "restart bot", "reboot the bot", "apply changes", or after any code change to qbt_telegram_bot.py or the patchy_bot/ package. Also invoke automatically after editing bot runtime code.
---

# Restart & Verify Bot Service

Restart the Telegram bot and confirm it came up healthy. Run these steps in order:

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate service restart and health verification to the `config-infra-agent` (sequential with error diagnosis).
- **On failure:** If the service fails to start, delegate failure log analysis to the `error-detective` agent with the journalctl output from Step 3.

## Step 1 — Restart the service

```bash
sudo systemctl restart telegram-qbt-bot.service
```

## Step 2 — Wait briefly, then check status

```bash
sleep 2 && systemctl is-active telegram-qbt-bot.service
```

## Step 3 — If the service is NOT `active`, pull the failure logs

```bash
journalctl -u telegram-qbt-bot.service --no-pager -n 40 --since "2 minutes ago"
```

Read the logs and identify the root cause (import error, config issue, syntax error, etc.). Report:
- The exact error line from the traceback
- What file and line number caused it
- A plain-English explanation of what went wrong
- A suggested fix

## Step 4 — If the service IS `active`, confirm with a quick log check

```bash
journalctl -u telegram-qbt-bot.service --no-pager -n 10 --since "1 minute ago"
```

Look for:
- Successful startup messages (e.g., "Bot started", polling started)
- Any warnings that appeared during startup
- Confirm no tracebacks or error-level messages

## Report format

**If healthy:**
> Bot restarted successfully. No errors in startup logs.

Plus any warnings worth noting.

**If failed:**
> Bot failed to start. [root cause in plain English]. Fix: [specific action].

Then offer to fix the issue immediately.

## Key details
- Service name: `telegram-qbt-bot.service`
- Working directory: `/home/karson/Patchy_Bot/telegram-qbt`
- Runtime entry point: `qbt_telegram_bot.py`
- Python venv: `/home/karson/Patchy_Bot/telegram-qbt/.venv/bin/python`
