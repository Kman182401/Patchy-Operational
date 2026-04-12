---
tags:
  - reference
aliases:
  - Operations Runbook
created: 2026-04-11
updated: 2026-04-11
---

# Ops Runbook

## Overview

This is the day-to-day "how do I run Patchy Bot" guide. If something looks wrong, start here.

### Is the bot running?

Patchy Bot runs as a systemd service called `telegram-qbt-bot.service`. To see if it's alive, ask systemd for its status. A healthy bot says `active (running)` and shows a recent log line about polling Telegram.

### How to restart it

**Any time you change a Python file under `telegram-qbt/patchy_bot/`, you have to restart the service.** The bot loads the code into memory at startup; it does not hot-reload.

Skipping the restart means your change isn't actually live, no matter how good the code is. This is non-negotiable — it's the most common reason "my fix didn't do anything."

### What's running in the background

The bot is not just a chat handler. Several loops tick in the background:

- **Schedule runner** — every **60 seconds**. Looks at the TV episodes and movies you're tracking and decides if anything is due to download right now.
- **Remove runner** — every **60 seconds**. Processes pending media-removal jobs (the "delete this show from Plex" jobs you queued).
- **Completion poller** — every **60 seconds**. Notices when a torrent finishes, kicks off the organize step, and sends you the completion notification.
- **qBT health check** — every **300 seconds** (5 minutes). Pings qBittorrent to make sure the connection is still healthy.
- **Command center refresh** — every **3 seconds**, per active user. Updates the live "command center" message in your chat with current download progress.

The schedule runner has its own internal timing rules:

- **Release grace period:** 90 minutes. After an episode airs, the runner waits this long before declaring it ready to download — gives release groups time to actually post the file.
- **Retry interval:** 1 hour (3600 s). If a scheduled item fails (no torrents found, etc.), wait this long before trying again.
- **Metadata retry backoff:** starts at 15 minutes for the first retry and grows from there.
- **Pending stale threshold:** 3 hours. Pending downloads that haven't progressed in this long are considered stuck.

### When something seems broken

In rough order of "fastest to check":

1. **Service status.** Did it crash? Is it restarting in a loop?
2. **Recent logs.** The last 10 minutes of journal usually shows the actual error.
3. **`/health` command in Telegram.** Runs `cmd_health` → `health_report()` and gives you a snapshot of qBT, Plex, the database, and the runners.
4. **VPN status.** If qBT shows status `firewalled`, the VPN routing or DNS is broken. **Never** "fix" this by binding qBT to the VPN interface — that breaks libtorrent DNS. See the VPN safety task in [[Work Board]].
5. **qBT connectivity.** Can the bot reach the qBittorrent Web UI at all?
6. **Disk space.** Plex paths and the qBT save path filling up causes weird and varied symptoms.

### Service dependencies

The systemd unit declares it must start `After=network-online.target qbittorrent.service` and `Wants=network-online.target`.

Translation: the network has to be up and qBittorrent has to be running before Patchy Bot starts. If qBittorrent dies, the bot keeps running but every download will fail until qBT comes back.

### Filesystem the service can write to

The unit hardens the system with `ProtectSystem=strict`, `NoNewPrivileges=true`, and `PrivateTmp=true`, then explicitly grants write access to four paths:

- `/home/karson/Patchy_Bot/telegram-qbt`
- `/home/karson/Downloads`
- `/home/karson/MySSD/Plex Videos`
- `/home/karson/MySSD/Plex Movies`

If the bot ever needs to write somewhere new, the unit file's `ReadWritePaths=` lines have to be updated and the service reloaded.

> [!code]- Claude Code Reference
> **Service file**
> - Path: `/home/karson/Patchy_Bot/telegram-qbt/telegram-qbt-bot.service`
> - Unit name: `telegram-qbt-bot.service`
> - `ExecStart=/home/karson/Patchy_Bot/telegram-qbt/.venv/bin/python -m patchy_bot`
> - `WorkingDirectory=/home/karson/Patchy_Bot/telegram-qbt`
> - `EnvironmentFile=/home/karson/Patchy_Bot/telegram-qbt/.env`
> - `User=karson`, `Group=karson`
> - `Restart=on-failure`, `RestartSec=5`
> - `After=network-online.target qbittorrent.service`
> - `Wants=network-online.target`
> - `WantedBy=multi-user.target`
> - Hardening: `ProtectSystem=strict`, `NoNewPrivileges=true`, `PrivateTmp=true`
> - `ReadWritePaths`: `telegram-qbt/`, `~/Downloads`, `~/MySSD/Plex Videos`, `~/MySSD/Plex Movies`
>
> **Service commands**
> ```
> sudo systemctl status telegram-qbt-bot.service
> sudo systemctl restart telegram-qbt-bot.service
> sudo journalctl -u telegram-qbt-bot.service -f
> sudo journalctl -u telegram-qbt-bot.service --since "10 minutes ago"
> ```
>
> **In-bot health command**
> - Telegram command: `/health`
> - Handler: `cmd_health` in `telegram-qbt/patchy_bot/handlers/commands.py` (line ~817)
> - Builder: `health_report(ctx)` in `handlers/commands.py` (line ~85)
> - Wired in `bot.py` at `app.add_handler(CommandHandler("health", self.cmd_health))`
>
> **Background runner intervals (verified in source)**
> | Runner | Interval | Source |
> |---|---|---|
> | schedule-runner | 60 s | `handlers/schedule.py::schedule_runner_interval_s` |
> | remove-runner | 60 s | `handlers/remove.py::remove_runner_interval_s` |
> | completion poller | 60 s | bot.py runner orchestration |
> | qbt-health-check | 300 s | `bot.py` line ~226 (`interval=300`, `name="qbt-health-check"`) |
> | command center refresh | 3 s | `bot.py::_command_center_refresh_loop` (`await asyncio.sleep(3)`) |
>
> **Schedule subsystem timings (verified in `handlers/schedule.py`)**
> | Constant | Value | Function |
> |---|---|---|
> | Release grace | 90 min (5400 s) | `schedule_release_grace_s` → `90 * 60` |
> | Retry interval | 1 hr (3600 s) | `schedule_retry_interval_s` → `3600` |
> | Pending stale | 3 hr (10800 s) | `schedule_pending_stale_s` → `3 * 3600` |
> | Metadata retry (first failure) | 15 min (900 s) | `schedule_metadata_retry_backoff_s` → `15 * 60` |
>
> **Completion poller interval:** the unverified value above (60 s) matches `telegram-qbt/CLAUDE.md`'s runner table but the literal sleep was not located in this pass — confirm against `bot.py` runner orchestration if exact precision matters.
