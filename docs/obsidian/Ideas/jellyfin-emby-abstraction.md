---
tags: [idea, priority-low, open]
created: 2026-04-11
module: patchy_bot/clients/plex.py
related: []
---

# Idea: Jellyfin / Emby media library abstraction

## Description
The `media-library-abstraction-agent` already exists in `.claude/agents/` for planning Jellyfin/Emby support. Currently the bot is tightly coupled to Plex via `PlexInventoryClient`. An abstraction layer would allow users to choose their media server.

Similarly, the `torrent-client-abstraction-agent` exists for Transmission/rTorrent support planning.

## Why it matters
Widens the potential user base beyond Plex + qBittorrent users. Both abstraction agents are already defined but no implementation work has started.

## Open questions
- Would the abstraction be a compile-time plugin or runtime config?
- How to handle feature differences (Plex has rating keys, Jellyfin has different metadata)?
- Is there enough demand to justify the complexity?
