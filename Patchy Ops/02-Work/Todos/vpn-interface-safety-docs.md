---
tags:
  - work/todo
aliases:
  - VPN interface safety guard
created: 2026-04-11
updated: 2026-04-11
status: open
priority: medium
---

# VPN interface safety guard

## Overview

qBittorrent has a setting called "network interface" that locks all torrent traffic to a specific network card. Some people set it to their VPN interface (like `surfshark_wg`) thinking that's the safe move. **Don't.** When you do that on this machine, the libtorrent library inside qBittorrent loses access to the local DNS resolver at `127.0.0.1:53`, and the whole thing stops being able to look up tracker hostnames. The symptom is qBT going to status `firewalled` and downloads never starting.

We don't actually need that setting at all, because the operating system already forces every qBT packet through the VPN using policy routing (Surfshark's kill switch sets up `ip rule 31565` pointing at routing table `300000`). The VPN enforcement is handled below qBT — qBT just has to talk plain TCP and DNS like normal.

The task: add a startup guard in the bot that reads qBT's preferences, and if `current_network_interface` is set to a VPN interface, refuse to start (or loudly warn) and explain why. Also write down the "we learned this the hard way" story so the next person — human or AI — doesn't re-break it.

> [!code]- Claude Code Reference
> **Affected files**
> - `telegram-qbt/patchy_bot/__main__.py` — has a NOTE around line 70: "Do NOT bind qBT to the VPN interface here"
> - `telegram-qbt/patchy_bot/config.py` — VPN interface name comes from env
> - `telegram-qbt/patchy_bot/clients/qbittorrent.py` — `set_preferences()` should NOT have the guard (would break legitimate uses)
>
> **Where to add the guard**
> - Startup-time check in `__main__.py` (or a small helper called from there)
> - Read qBT preferences via `QBClient`, compare `current_network_interface` against the VPN interface name from config
> - On match: log a clear error and either exit or block startup
>
> **Diagnostic commands**
> - Check current binding: query qBT API `/api/v2/app/preferences` → field `current_network_interface`
> - VPN routing rule: `ip rule show | grep 31565`
> - Routing table: `ip route show table 300000`
>
> **Background memory notes**
> - `~/.claude/projects/-home-karson-Patchy-Bot/memory/project_qbt_interface_binding_dns.md`
> - `~/.claude/projects/-home-karson-Patchy-Bot/memory/feedback_no_qbt_interface_binding.md`
>
> **Tests:** `.venv/bin/python -m pytest -q` after changes.
