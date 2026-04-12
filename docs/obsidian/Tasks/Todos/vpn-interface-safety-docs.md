---
tags: [todo, priority-medium, open]
created: 2026-04-11
module: patchy_bot/__main__.py
related: []
---

# Todo: VPN interface binding safety documentation in-app

## Problem / What
The `__main__.py` entry point has a NOTE (line 70): "Do NOT bind qBT to the VPN interface here." This critical safety constraint is documented in CLAUDE.md and agent files but not surfaced to the user in the bot itself.

The constraint exists because interface binding breaks libtorrent DNS resolution (can't reach 127.0.0.1:53). The OS-level Surfshark kill-switch handles VPN routing via policy routing (ip rule 31565, table 300000).

## Expected Behavior / Why
If someone (human or AI) attempts to set `current_network_interface` in qBT preferences, the bot should warn or block the operation to prevent DNS breakage.

## Context
- Affects: `__main__.py`, `config.py`, `clients/qbittorrent.py`
- Root cause: safety constraint exists in docs but has no runtime guard
- Related: [[Architecture/clients|Clients]]

## Claude Code Notes
Consider adding a startup check in `__main__.py` that reads qBT preferences and warns if `current_network_interface` is set to the VPN interface. Do NOT add the guard to `set_preferences()` — that would break legitimate uses. Run tests after changes.
