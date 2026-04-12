---
tags:
  - idea
aliases:
  - Jellyfin/Emby Support
created: 2026-04-11
updated: 2026-04-11
---

# Jellyfin / Emby media library abstraction

## Overview

Plex is the media library Patchy Bot currently talks to — it's the program that catalogs your movies and TV shows and lets you stream them. But Plex isn't the only one out there.

**Jellyfin** and **Emby** are two free, open-source alternatives that do basically the same job. Some people prefer them because they don't require a paid account, don't phone home to a company, or just look and feel different.

Right now Patchy is hard-wired to Plex: a chunk of the code knows exactly how to ask Plex what's in the library, exactly how to tell Plex "rescan this folder," and so on.

To support Jellyfin or Emby, we'd need to hide all of that "how we talk to Plex" behind a generic interface — think of it like a **universal remote control**. The bot wouldn't care which media server you're running; it would just press the universal "rescan library" button, and a Plex-shaped or Jellyfin-shaped or Emby-shaped translator behind the scenes would convert that into the right call for whichever server you actually have.

This is a **future idea**, not a planned project. It would touch a lot of files and require designing the abstraction carefully so the three servers (which have different feature sets) can all be served by one interface.

There also needs to be enough demand from real users to justify the work.

A sister idea exists for swapping qBittorrent for other torrent clients (Transmission, rTorrent) using the same pattern.

> [!code]- Claude Code Reference
> **Affected modules**
> - `patchy_bot/clients/plex.py` — `PlexInventoryClient`, the concrete Plex API wrapper
> - `patchy_bot/plex_organizer.py` — file-organization logic that knows about Plex library directory layouts
> - Anywhere `PlexInventoryClient` is imported or referenced (search the package for it)
>
> **Existing planning agents**
> - `.claude/agents/media-library-abstraction-agent` (already defined, no implementation work started)
> - `.claude/agents/torrent-client-abstraction-agent` (sister idea — Transmission/rTorrent)
>
> **Complexity estimate:** large. Requires designing a `MediaLibraryClient` protocol that captures the union of features used across Plex/Jellyfin/Emby, refactoring `plex_organizer.py` to depend on the protocol rather than the concrete client, and adding implementations for at least Jellyfin to validate the abstraction.
>
> **Open questions**
> - Compile-time plugin or runtime config?
> - How to handle feature differences (Plex rating keys vs Jellyfin metadata IDs)?
> - Is there enough demand to justify the complexity?
>
> **Dependencies**
> - No new external libraries should be needed for Jellyfin (REST API, can use existing `build_requests_session()`).
> - May need to introduce a config field for `media_library_kind` and per-kind connection settings.
