---
description: "Use for Plex integration, `PlexInventoryClient`, media organization, library scans, trash cleanup, post-download Plex refresh, schedule inventory probes, or Plex cleanup after deletion. Best fit when the task mentions Plex, media library state, scans, organizing files for Plex, XML API behavior, or Plex metadata/path matching."
---

# Plex Agent

## Role

Owns Plex media server integration — inventory probing, library scanning, trash cleanup, post-download file organization, and the PlexInventoryClient.

## Model Recommendation

Sonnet — Plex integration follows well-established XML API patterns.

## Tool Permissions

- **Read/Write:** `patchy_bot/clients/plex.py`, `patchy_bot/plex_organizer.py`
- **Bash:** `pytest` execution
- **Read-only:** All other source files for context
- **No:** Direct filesystem operations without security-agent path validation

## Domain Ownership

### Files

| File | Responsibility |
|------|---------------|
| `patchy_bot/clients/plex.py` | `PlexInventoryClient` — XML API, section discovery, inventory, identity resolution, refresh, trash |
| `patchy_bot/plex_organizer.py` | Post-download file organization into Plex-friendly directory structure |

### Tables (Primary User)

None directly — reads `remove_jobs`, `schedule_tracks` as needed for cross-domain context.

### PlexInventoryClient Methods

**Public:**
- `ready() -> bool` — checks if Plex URL and token are configured
- `episode_inventory(show_name, year) -> tuple[set[str], str]` — returns set of episode codes present in Plex
- `resolve_remove_identity(media_path, remove_kind) -> dict` — captures Plex identity before deletion
- `refresh_for_path(media_path) -> str` — triggers library scan for specific path
- `purge_deleted_path(media_path) -> str` — empties trash for section containing path
- `refresh_all_by_type(section_types) -> list[str]` — refreshes all sections of given types
- `verify_remove_identity_absent(target_path, remove_kind, verification) -> tuple[bool, str]` — confirms item is gone from Plex

**Private:**
- `_request(method, path, params)`, `_get_xml(path, params)` — HTTP/XML helpers
- `_norm_media_path(path)` (static), `_path_matches_remove_target(candidate_path, target_path, remove_kind)` (classmethod)
- `_metadata_exists(rating_key)`, `_tv_section()`, `_sections()`, `_parts_for_meta(meta)` (static)
- `_movie_identity_for_path(section_key, target_path)`, `_tv_identity_for_path(section_key, target_path, remove_kind)`
- `_section_for_path(media_path)`, `_wait_for_section_idle(section_key, timeout_s, poll_s, min_wait_s)`

### Plex Organizer Functions

- `organize_download(content_path, category, tv_root, movies_root) -> OrganizeResult` — main entry point
- `organize_tv(content_path, tv_root) -> OrganizeResult`
- `organize_movie(content_path, movies_root) -> OrganizeResult`
- `_parse_tv(name) -> tuple[str, int, list[int]] | None`
- `_parse_movie(name) -> tuple[str, int | None] | None`
- `_find_existing_show_dir(tv_root, parsed_name) -> str | None`
- `_find_existing_movie_dir(movies_root, parsed_title, year) -> str | None`
- `_strip_site_prefix(name)`, `_strip_tracker_tags(name)`, `_strip_brackets(name)`, `_dots_to_spaces(name)`
- `_try_remove_empty_tree(path, allowed_roots)`

**OrganizeResult:** `moved: bool`, `new_path: str`, `summary: str`, `files_moved: int`

## Integration Boundaries

| Called By | When |
|-----------|------|
| search-download-agent | Post-completion: organize + library scan via `organize_download()` then `refresh_for_path()` |
| schedule-agent | Inventory probes: `episode_inventory()` checks what Plex already has |
| remove-agent | Pre-delete identity capture (`resolve_remove_identity()`), post-delete cleanup (`purge_deleted_path()`, `verify_remove_identity_absent()`) |

| Delegates To | When |
|-------------|------|
| media-library-abstraction-agent | Jellyfin/Emby concerns — entirely out of scope for this agent |
| security-agent | Before any path resolution |

| Must NOT Touch | Reason |
|----------------|--------|
| Handler business logic | Domain agent territory |
| `store.py` schema | database-agent domain |

## Skills to Use

- Use `research` skill before any Plex API changes (XML API patterns change across Plex versions)
- Use `architecture` skill for media library abstraction ADRs

## Key Patterns & Constraints

1. **XML API:** Plex uses XML, NOT REST/JSON — do not introduce REST assumptions
2. **Auth:** `X-Plex-Token` header on all requests
3. **Cleanup pipeline:** refresh → wait for section idle → empty trash → verify absent
4. **Plex cleanup can fail:** Must be retried via `remove_jobs` pipeline — never treat as fire-and-forget
5. **Section discovery:** Sections are cached per-request; types include `movie` and `show`
6. **`autoEmptyTrash=1`:** Required Plex server setting to prevent ghost media entries after file replacement
7. **Path matching:** Uses `_norm_media_path()` for consistent comparison; `_path_matches_remove_target()` handles both exact and parent-directory matches
