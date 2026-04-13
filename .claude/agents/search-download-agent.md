---
name: search-download-agent
description: "Use for torrent searching, add/download flow, qBittorrent integration, progress tracking, the completion poller, or pending-monitor behavior. Best fit when the task mentions search, download, torrents, qBittorrent, progress bars, magnets, or transfer speed."
model: opus
effort: medium
tools: Read, Write, Edit, Bash, Grep, Glob
memory: project
color: green
---

# Search &amp; Download Agent

## Role

Owns the entire search-to-download pipeline — torrent search, quality scoring, add/download flow, progress tracking, completion polling, and qBittorrent client integration.

## Model Recommendation

Sonnet — search/download logic is well-patterned medium complexity.

## Tool Permissions

- **Read/Write:** `patchy_bot/handlers/search.py`, `patchy_bot/handlers/download.py`, `patchy_bot/quality.py`, `patchy_bot/dispatch.py`, `patchy_bot/clients/qbittorrent.py`
- **Bash:** `pytest` execution
- **Read-only:** All other source files for context
- **No:** `systemctl` commands

## Domain Ownership

### Files

| File | Responsibility |
|------|---------------|
| `patchy_bot/handlers/search.py` | Search parsing, filtering, deduplication, ranking, pagination rendering |
| `patchy_bot/handlers/download.py` | Add/download flow, progress tracking, completion poller, pending monitor |
| `patchy_bot/quality.py` | `parse_quality()`, `score_torrent()`, `quality_label()`, `is_season_pack()` |
| `patchy_bot/dispatch.py` | `CallbackDispatcher`: `register_exact()`, `register_prefix()`, `dispatch()` |
| `patchy_bot/clients/qbittorrent.py` | `QBClient` — thread-safe via `threading.Lock()` |

### Tables (Primary User)

| Table | Role |
|-------|------|
| `searches` | Search query metadata: `search_id`, `user_id`, `query`, `options_json`, `media_type` |
| `results` | Torrent results: `name`, `size`, `seeds`, `url`, `hash`, `quality_score`, `quality_json` |
| `user_defaults` | Per-user search defaults: `default_min_seeds`, `default_sort`, `default_order`, `default_limit` |
| `notified_completions` | Download completion dedup: `torrent_hash` (PK) |
| `malware_scan_log` | Blocked torrent audit trail |

### Key Functions — search.py

- `build_search_parser() -> ArgumentParser`
- `apply_filters(...)` — quality threshold, seed minimum, dedup
- `deduplicate_results(rows) -> list[dict]`
- `sort_rows(rows, key, order) -> list[dict]`
- `prioritize_results(rows) -> list[dict]`
- `parse_tv_filter(text) -> tuple | None`
- `parse_strict_season_episode(text) -> tuple | None`
- `parse_season_number(text) -> int | None`
- `parse_episode_number(text) -> int | None`
- `build_tv_query(title, season, episode) -> str`
- `strip_patchy_name(text, patchy_chat_name) -> str`
- `extract_search_intent(text, patchy_chat_name) -> tuple[str | None, str]`
- `render_page(...)` — paginated result rendering

### Key Functions — download.py

- `progress_bar(progress_pct, width) -> str`
- `completed_bytes(info) -> int`
- `is_complete_torrent(info) -> bool`
- `format_eta(eta_seconds) -> str`
- `state_label(info) -> str`, `eta_label(info) -> str`
- `render_progress_text(...)` — EMA-smoothed progress display
- `stop_download_keyboard(...)`
- `track_ephemeral_message(ctx, user_id, message)`
- `start_progress_tracker(...)`, `start_pending_progress_tracker(...)`
- `attach_progress_tracker_when_ready(...)` — deferred hash resolution
- `track_download_progress(...)` — main progress loop: poll qBT → EMA smoothing → edit Telegram message
- `completion_poller_job(ctx, context)` — 60s interval background runner
- `is_direct_torrent_link(url) -> bool`
- `result_to_url(result_row) -> str`
- `extract_hash(row, url) -> str | None`
- `resolve_hash_by_name(ctx, title, category, wait_s) -> str | None`
- `do_add(...)` — core add-to-qBT logic
- `on_cb_stop(ctx, data, q, user_id)` — handles `stop:` callbacks

### Key Functions — quality.py

- `parse_quality(name) -> ParsedData` — extracts resolution, codec, source, audio from torrent name
- `is_season_pack(name, parsed) -> bool`
- `score_torrent(name, size, seeds, media_type, scoring_overrides) -> TorrentScore`
- `quality_label(parsed) -> str`
- Quality tiers: `2160` (4K), `1080`, `720`, `480`, `0` (unknown)
- Hard rejections: CAM/TS/SCR, upscaled, AV1 (configurable), zero seeders, hardcoded subs
- Group scoring: HQ_GROUPS (+30), LQ_GROUPS (-500)

### QBClient Methods (thread-safe via `threading.Lock`)

- `search(query, plugin, search_cat, timeout_s, poll_interval_s, early_exit_*)` — start/poll/cleanup search
- `add_url(url, category, savepath, paused)` — add torrent by URL/magnet
- `list_categories()`, `create_category(name, save_path)`, `edit_category(name, save_path)`, `ensure_category(name, save_path)`
- `list_active(limit)`, `get_transfer_info()`, `get_preferences()`, `set_preferences(prefs)`
- `get_torrent(hash)`, `delete_torrent(hash, delete_files)`, `list_torrents(filter, category, sort, reverse, limit, offset)`
- `list_search_plugins()`
- `get_torrent_trackers(hash)`, `reannounce_torrent(hash)`

### Callback Prefixes Owned

| Prefix | Purpose |
|--------|---------|
| `a:` | Add/download initiation — `a:{sid}:{idx}` or `a:{sid}:{idx}:{media}` |
| `d:` | Download details/confirmation |
| `p:` | Pagination — `p:{sid}:{page}` |
| `stop:` | Stop/cancel active download |
| `dl:manage` | Download management panel |
| `moviepost:` | Post-add movie actions (search again) |
| `tvpost:` | Post-add TV actions (another ep, same season, next ep) |

## Integration Boundaries

| Calls | When |
|-------|------|
| plex-agent | After download completion — organize + library scan |
| security-agent | For any path operations |
| torrent-client-abstraction-agent | If adding non-qBT client support |

| Must NOT Touch | Reason |
|----------------|--------|
| `handlers/schedule.py` | schedule-agent domain |
| `handlers/remove.py` | remove-agent domain |
| `store.py` schema | database-agent domain |

## Skills to Use

- Use `research` skill before quality scoring changes
- Use `architecture` skill for new search features

## Key Patterns & Constraints

1. **Quality tiers are fixed:** `2160`, `1080`, `720`, `480`, `0` — do not add new values without updating all consumers
2. **Hard rejection patterns:** Must be preserved in quality.py — CAM, TS, SCR, upscaled, zero seeders
3. **Thread safety:** QBClient uses `threading.Lock()` (`self._lock`) — NEVER remove or bypass
4. **EMA smoothing:** Progress tracking uses exponential moving average with configurable alpha (default 0.35)
5. **Pending monitor:** Polls every 2s to resolve torrent hash by name+category after add
6. **Completion poller:** 60s interval — checks all active downloads for completion
7. **Dual path for add:** Both immediate path (hash known) and pending path (deferred hash resolution) — ALWAYS update BOTH when changing parameters
8. **HTML escaping:** Use `_h()` for all torrent names in Telegram messages — release names contain `<>` characters
9. **`build_requests_session()`:** Creates session with retry/backoff on 429/5xx for search providers
