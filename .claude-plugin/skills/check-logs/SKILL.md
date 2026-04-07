---
name: check-logs
description: Inspect recent Patchy Bot service logs and summarize what matters. Use for runtime diagnosis, restart failures, crashes, warnings, slowdowns, or “what happened?” questions. Do not use for purely static code review.
---

# Bot Log Inspector

Pull recent logs from the Patchy Bot systemd service, parse them, and surface what matters.

Service name: `telegram-qbt-bot.service`

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate log retrieval and service status checks to the `config-infra-agent` (sequential with review).
- **On domain-specific errors:** Route the finding to the relevant project agent after extracting the key log evidence.

## Step 1 — Pull recent logs

By default, get the last 15 minutes of logs. If the user specifies a time range, use that instead.

```bash
journalctl -u telegram-qbt-bot.service --no-pager -n 200 --since "15 minutes ago" 2>&1
```

If the user asks for a specific severity, filter accordingly:
- Errors only: `journalctl -u telegram-qbt-bot.service --no-pager -p err --since "15 minutes ago"`
- Warnings and above: `journalctl -u telegram-qbt-bot.service --no-pager -p warning --since "15 minutes ago"`

## Step 2 — Analyze the output

The bot uses `structlog` which may output JSON or colored text depending on `LOG_FORMAT` config.

### Categorize log entries into:

**Errors (report these first)**
- Python tracebacks / exceptions
- API connection failures (qBittorrent, Plex, TVMaze, TMDb)
- Authentication failures
- Database errors
- Telegram API errors (message edit failures, timeout, etc.)

**Warnings (report if relevant)**
- Rate limit hits
- VPN check failures
- Degraded service connections
- Retry attempts

**Operational (summarize briefly)**
- Bot startup/shutdown
- Search requests processed
- Downloads added
- Schedule checks completed

### Look specifically for these common issues:
- `403` from qBittorrent — auth session expired
- `Conflict` from Telegram — another bot instance running
- `TimedOut` — Telegram API slowness
- `MessageNotModified` — tried to edit message with same content (harmless)
- `BadRequest: message to edit not found` — message was deleted
- `sqlite3.OperationalError` — database locked or corrupted
- Tracebacks with `ImportError` or `ModuleNotFoundError` — broken install
- `ConnectionRefusedError` — qBittorrent or Plex service down

## Step 3 — Report

### Log Summary (last N minutes)

**Errors: N**
For each error, show:
- Timestamp
- Error type and message (one line)
- Plain-English explanation
- Whether it needs action or is transient

**Warnings: N**
Brief list of warning types and counts.

**Activity: N entries**
Brief summary of what the bot was doing (e.g., "processed 3 searches, added 1 download, ran 2 schedule checks").

### Verdict
- **Healthy** — no errors, normal activity
- **Noisy but OK** — some transient errors (MessageNotModified, etc.) but nothing actionable
- **Needs attention** — persistent errors that indicate a real problem, with suggested fix

If no logs are found, check if the service is running:
```bash
systemctl is-active telegram-qbt-bot.service && systemctl show telegram-qbt-bot.service --property=ActiveEnterTimestamp
```
