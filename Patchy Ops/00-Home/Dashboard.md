---
tags:
  - home
aliases:
  - Patchy Dashboard
created: 2026-04-11
updated: 2026-04-11
---

# Dashboard

## Overview

Welcome to the Patchy Bot vault. Patchy is a Telegram-based assistant that searches for movies and TV shows, hands them off to qBittorrent for downloading, scans the results for malware, and organizes the finished files into a Plex media library. This dashboard is your starting point — it shows what work is open right now, what was finished recently, and how all the pieces of the system fit together.

## Open Work

```dataview
TABLE priority, status, file.folder AS "Bucket"
FROM #work/todo OR #work/upgrade
WHERE status != "done"
SORT priority ASC
```

## Recent Changelog

```dataview
TABLE created
FROM #changelog
SORT created DESC
LIMIT 5
```

## System Map

```mermaid
graph TD
    TG[Telegram API] -->|polling| BA[BotApp<br>bot.py]
    BA --> CMD[commands.py<br>18 slash commands]
    BA --> CB[CallbackDispatcher<br>dispatch.py]
    CB --> SCH[schedule.py<br>TV + movie tracking]
    CB --> DL[download.py<br>Progress + completion]
    CB --> RM[remove.py<br>Media removal]
    CB --> SR[search.py<br>Search + filter]
    CB --> CH[chat.py<br>LLM chat]
    BA --> UI[ui/<br>keyboards, rendering,<br>text, flow]
    SCH --> TVM[TVMetadataClient<br>TVMaze + TMDB]
    DL --> QBT[QBClient<br>qBittorrent API]
    RM --> PLX[PlexInventoryClient<br>Plex XML API]
    DL --> PLX
    DL --> ORG[plex_organizer.py<br>File organization]
    DL --> MAL[malware.py<br>Fake + malware scan gate]
    SR --> MAL
    SR --> QAL[quality.py<br>RTN scoring]
    DL --> QAL
    CH --> LLM[PatchyLLMClient<br>OpenAI-compatible]
    BA --> DB[(SQLite WAL<br>14 tables)]
    BA --> HLT[health.py<br>VPN + disk + qBT checks]
```

## Quick Links

[[System Overview]] | [[Work Board]] | [[Preferences]] | [[Ideas Index]] | [[Changelog Index]] | [[Vault Guide]] | [[SETUP]]

> [!code]- Claude Code Reference
> **Runner timing**
> - Schedule runner: 60s tick
> - Remove runner: 60s tick
> - Completion poller: 60s tick
> - Command center refresh: 3s tick
>
> **Service dependency summary**
> - `telegram-qbt-bot.service` (systemd) → polls Telegram, depends on local `qbittorrent-nox.service` and Plex (`plexmediaserver.service`) being reachable on the LAN. Surfshark WireGuard policy routing handles VPN enforcement at the OS level — qBT must NOT be interface-bound.
>
> **Tech stack**
> - Python 3.12+
> - python-telegram-bot (long polling, not webhook)
> - SQLite WAL mode, `busy_timeout=5000`
> - `asyncio` event loop with background runner tasks
> - systemd unit for process supervision
>
> **Current line counts**
> - `bot.py`: 5023 lines (Phase 2 decomposition target: under 2000)
