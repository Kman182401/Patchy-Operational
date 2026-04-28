# Graph Report (2026-04-15)

> Part of [[Patchy Bot Knowledge Graph]] — see also [[God Nodes]]

## Corpus Check
- 81 files · ~235,753 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3262 nodes · 8544 edges · 33 communities detected
- Extraction: 52% EXTRACTED · 48% INFERRED · 0% AMBIGUOUS · INFERRED: 4092 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[Community 0 — Core Types & Clients|Community 0 — Core Types & Clients]]
- [[Community 1 — BotApp & Command Flow|Community 1 — BotApp & Command Flow]]
- [[Community 2 — Download Pipeline|Community 2 — Download Pipeline]]
- [[Community 3 — Malware Scanning|Community 3 — Malware Scanning]]
- [[Community 4 — Parsing & Utilities|Community 4 — Parsing & Utilities]]
- [[Community 5 — Search & Filters|Community 5 — Search & Filters]]
- [[Community 6 — Movie Scheduling|Community 6 — Movie Scheduling]]
- [[Community 7 — Runners & Progress|Community 7 — Runners & Progress]]
- [[Community 8 — Callback Dispatch|Community 8 — Callback Dispatch]]
- [[Community 9 — Store Internals|Community 9 — Store Internals]]
- [[Community 10 — Quality Scoring|Community 10 — Quality Scoring]]
- [[Community 11 — Plex Organizer|Community 11 — Plex Organizer]]
- [[Community 12 — Full Series Downloads|Community 12 — Full Series Downloads]]
- [[Community 13 — Completion Security|Community 13 — Completion Security]]
- [[Community 14 — TMDB Metadata|Community 14 — TMDB Metadata]]
- [[Community 15 — Health & LLM Client|Community 15 — Health & LLM Client]]
- [[Community 16 — Schedule Handler|Community 16 — Schedule Handler]]
- [[Community 17 — Skill Creator Scripts|Community 17 — Skill Creator Scripts]]
- [[Community 18 — Delete Safety|Community 18 — Delete Safety]]
- [[Community 19 — Health Checks & VPN|Community 19 — Health Checks & VPN]]
- [[Community 20 — Plex Client Tests|Community 20 — Plex Client Tests]]
- [[Community 21 — UI Rendering & Flow|Community 21 — UI Rendering & Flow]]
- [[Community 22 — Theatrical Search|Community 22 — Theatrical Search]]
- [[Community 23 — Media Choice Normalize|Community 23 — Media Choice Normalize]]
- [[Community 24 — Benchmark Aggregation|Community 24 — Benchmark Aggregation]]
- [[Community 25 — Skill Packaging|Community 25 — Skill Packaging]]
- [[Community 26 — Report Generator|Community 26 — Report Generator]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]

## God Nodes (most connected - your core abstractions)
1. `BotApp` - 367 edges
2. `HandlerContext` - 330 edges
3. `Store` - 243 edges
4. `ScanResult` - 172 edges
5. `TVMetadataClient` - 150 edges
6. `MovieReleaseStatus` - 130 edges
7. `CallbackDispatcher` - 124 edges
8. `DoAddResult` - 124 edges
9. `Config` - 106 edges
10. `now_ts()` - 103 edges

## Surprising Connections (you probably didn't know these)
- `Bootstrap all tables, indexes, and migrations on *conn*.` --uses--> `Config`  [INFERRED]
  telegram-qbt/patchy_bot/store.py → telegram-qbt/patchy_bot/config.py
- `Bootstrap schema using a temporary connection (file-based DBs only).` --uses--> `Config`  [INFERRED]
  telegram-qbt/patchy_bot/store.py → telegram-qbt/patchy_bot/config.py
- `Insert a download health event and return its event_id.` --uses--> `Config`  [INFERRED]
  telegram-qbt/patchy_bot/store.py → telegram-qbt/patchy_bot/config.py
- `Retrieve health events for a user with optional filters.` --uses--> `Config`  [INFERRED]
  telegram-qbt/patchy_bot/store.py → telegram-qbt/patchy_bot/config.py
- `Log a blocked torrent to the malware scan log.` --uses--> `Config`  [INFERRED]
  telegram-qbt/patchy_bot/store.py → telegram-qbt/patchy_bot/config.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (225): ABC, BaseHandler, Base handler class that all domain handlers extend., Abstract base for domain-specific handler modules.      Each handler receives a, Register callback-query prefixes with the CallbackDispatcher., Return (command_name, handler_coroutine) pairs to register.          Override in, Telegram bot application — command handlers, callback router, and lifecycle., Normalize series_missing_by_season to string-keyed dict and ensure current seaso (+217 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (128): BotApp, _build_tv_query(), _extract_post_add_rows(), _progress_bar(), _schedule_show_info(), Send user text to the LLM and reply with the response.      Maintains per-user c, reply_patchy_chat(), cmd_active() (+120 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (260): _active_progress_hashes(), _advance_download_queue(), attach_progress_tracker_when_ready(), _batch_monitor_entries(), batch_stop_keyboard(), _BoundedHashSet, _cleanup_missing_files_torrents(), _clear_pending_scan() (+252 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (149): _movie_result_is_theatrical_source(), _apply_co_occurrence(), _archive_ext(), _basename(), _build_result(), _check_archives_in_media(), _check_double_extensions(), _check_executables() (+141 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (263): _compact_action_rows(), _extract_show_name(), _parse_season_number(), _parse_strict_season_episode(), _remove_kind_label(), from_env(), compact_action_rows(), full_series_confirm_keyboard() (+255 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (200): _deduplicate_results(), _extract_movie_name(), _sort_rows(), chat_needs_qbt_snapshot(), patchy_system_prompt(), LLM / Patchy-chat handler functions.  These are the four methods extracted from, Return the LLM system prompt for Patchy chat.      Args:         ctx: Shared han, Strip the bot's name from the start of the user's message.      Args:         ct (+192 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (120): candidate_nav_keyboard(), Build a keyboard for cycling through search result candidates.      Layout (top, backup_job(), episode_status_icon(), No1080pError, on_cb_movie_schedule(), on_text_movie_schedule(), schedule_active_line() (+112 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (144): completed_bytes(), eta_label(), extract_hash(), is_complete_torrent(), Convert a search result row into a torrent/magnet URL suitable for qBT., Extract the torrent info-hash from either the result row or the magnet URL., Return the number of completed bytes for a torrent info dict., Return True if the torrent info indicates a fully downloaded torrent. (+136 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (102): build_qbt_snapshot(), Build a read-only qBT status string for LLM context.      Assembles active-torre, cmd_malware_stats(), on_cb_flow(), on_cb_menu(), _parse_malware_stats_range(), Handle ``menu:*`` callback queries — Command Center navigation., Handle ``flow:*`` callback queries — TV search flow transitions. (+94 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (58): main(), now_ts(), Bootstrap schema using a temporary connection (file-based DBs only)., Bootstrap all tables, indexes, and migrations on *conn*., Insert a download health event and return its event_id., Retrieve health events for a user with optional filters., Log a blocked torrent to the malware scan log., Aggregate malware scan statistics.          Returns keys: total_blocks (int), by (+50 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (105): is_season_pack(), parse_quality(), quality_label(), Torrent quality scoring engine backed by RTN (rank-torrent-name).  Two-layer ran, Thin wrapper around RTN parse().      Args:         name: Raw torrent name strin, Return True if the torrent is a season pack rather than a single episode.      U, Score a torrent for quality ranking.      Higher ``resolution_tier`` always beat, Build a short quality label for UI display.      Args:         parsed: RTN Parse (+97 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (48): _dots_to_spaces(), _find_existing_movie_dir(), _find_existing_show_dir(), organize_download(), organize_movie(), organize_tv(), OrganizeResult, _parse_movie() (+40 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (74): _cancel_cleanup(), _delete_partial_season_files(), _drive_season_individual(), _drive_season_pack(), FullSeriesResult, FullSeriesState, Full Series Download engine (Phase B, Task 4).  Sequential, pack-first download, Pull torrent progress from qBT into the state (no-op if no hash). (+66 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (42): _apply_completion_security_gate(), _clamd_available(), CompletionSecurityResult, Return True iff *target* resolves inside one of *allowed_roots*.      Used as a, _run_clamav_scan(), _validate_safe_path(), gate_ctx(), Tests for the completion-security gate: ClamAV scanning and the ``_apply_complet (+34 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (27): TestTMDBMovieMethods, Tests for poster/image URL extraction in TVMetadataClient., search_movies builds full poster URL from poster_path., search_movies returns poster_url=None when poster_path is null., search_movies returns poster_url=None when poster_path is empty string., search_movies returns empty list when tmdb_api_key is not configured., Verify the hostname allowlist that guards _send_poster_photo., Import and return BotApp._POSTER_ALLOWED_HOSTS without instantiating BotApp. (+19 more)

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (42): _norm_path(), health_report(), Build the /health status report.      Args:         ctx: Handler context with al, _extract_content(), auto_delete_after(), ensure_media_categories(), norm_path(), Shared utility functions used by multiple handler modules.  Canonical implementa (+34 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (20): on_cb_schedule(), schedule_dl_confirm_keyboard(), Missing and other-season-gaps lines show Exx, not SxxExx., test_home_only_keyboard_contains_home_button(), test_render_command_center_edits_existing_message(), test_schedule_download_requested_edits_status_card_not_new_message(), test_schedule_download_requested_no_waiting_for_hash_message(), test_schedule_preview_text_inventory_uses_status_icons() (+12 more)

### Community 17 - "Community 17"
Cohesion: 0.06
Nodes (38): BaseHTTPRequestHandler, build_run(), embed_file(), find_runs(), _find_runs_recursive(), generate_html(), get_mime_type(), _kill_port() (+30 more)

### Community 18 - "Community 18"
Cohesion: 0.08
Nodes (23): _make_bot(), _make_config(), Unit tests for the _delete_remove_candidate path-safety guards.  These tests ver, Tests for movies root_key — expects exactly depth 1 (one folder)., Movies must be exactly 1 level deep — a subfolder inside a movie dir is rejected, Trying to delete the media root itself must fail., TV show removal (remove_kind='show') expects depth 1., TV season removal (remove_kind='season') expects depth 2. (+15 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (29): Build the /speed dashboard text.      Args:         ctx: Handler context with qb, speed_report(), check_disk_space(), check_qbt_connection(), check_vpn(), run_preflight(), qbt_transport_status(), Check qBittorrent connection status and bound network interface. (+21 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (16): _norm_media_path(), _path_matches_remove_target(), FakeResponse, _make_client(), Tests for patchy_bot.clients.plex.PlexInventoryClient., Minimal stand-in for requests.Response., When all rating_keys 404, the item is confirmed absent., When metadata still returns 200, item is NOT absent. (+8 more)

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (32): clear_flow(), get_flow(), Flow state management — get/set/clear per-user modal state., Store ``payload`` as the current flow state for ``user_id``., Return the current flow state for ``user_id``, or ``None`` if absent., Remove the flow state for ``user_id`` (no-op if not present)., set_flow(), cancel_pending_trackers_for_user() (+24 more)

### Community 22 - "Community 22"
Cohesion: 0.16
Nodes (14): _FakeScheduleApp, _make_bot(), _make_update(), test_detect_status_home_available(), test_detect_status_in_theaters(), test_detect_status_no_api_key(), test_detect_status_no_results(), test_detect_status_search_raises() (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.19
Nodes (4): normalize_media_choice(), Map user input to canonical 'movies' or 'tv', or None if unrecognized., normalize_media_choice maps user input to canonical 'movies' or 'tv'., TestNormalizeMediaChoice

### Community 24 - "Community 24"
Cohesion: 0.24
Nodes (11): aggregate_results(), calculate_stats(), generate_benchmark(), generate_markdown(), load_run_results(), main(), Aggregate run results into summary statistics.      Returns run_summary with sta, Generate complete benchmark.json from run results. (+3 more)

### Community 25 - "Community 25"
Cohesion: 0.28
Nodes (7): main(), package_skill(), Check if a path should be excluded from packaging., Package a skill folder into a .skill file.      Args:         skill_path: Path t, should_exclude(), Basic validation of a skill, validate_skill()

### Community 26 - "Community 26"
Cohesion: 0.67
Nodes (3): generate_html(), main(), Generate HTML report from loop output data. If auto_refresh is True, adds a meta

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Backward-compat list of human-readable reason strings.

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): When qBT delete leaves the dir behind, rmtree fallback removes it.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): When cfg.log_clean_scans=True, a malware_scan_clean health event is logged.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): When cfg.log_clean_scans=False, no health event is logged on clean scans.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **315 isolated node(s):** `Bot configuration loaded from environment variables.`, `Escape user-provided text for safe HTML parse_mode rendering.`, `Return a human-readable relative time string: 'in 3h', '2d ago', 'just now', 'TB`, `Per-user sliding-window rate limiter.`, `Per-user sliding-window rate limiter.      Tracks command timestamps per user in` (+310 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 27`** (1 nodes): `qbt_telegram_bot.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Backward-compat list of human-readable reason strings.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `When qBT delete leaves the dir behind, rmtree fallback removes it.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `When cfg.log_clean_scans=True, a malware_scan_clean health event is logged.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `When cfg.log_clean_scans=False, no health event is logged on clean scans.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BotApp` connect `Community 1` to `Community 0`, `Community 2`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 14`, `Community 15`, `Community 16`, `Community 18`, `Community 19`, `Community 21`, `Community 22`?**
  _High betweenness centrality (0.275) - this node is a cross-community bridge._
- **Why does `HandlerContext` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 12`, `Community 13`, `Community 14`, `Community 15`, `Community 16`, `Community 19`, `Community 21`, `Community 23`?**
  _High betweenness centrality (0.266) - this node is a cross-community bridge._
- **Why does `Store` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 9`, `Community 14`, `Community 15`, `Community 16`, `Community 21`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Are the 149 inferred relationships involving `BotApp` (e.g. with `Entry point for the Patchy Bot package.  Run with: python -m patchy_bot` and `# NOTE: Do NOT bind qBT to the VPN interface here.`) actually correct?**
  _`BotApp` has 149 INFERRED edges - model-reasoned connections that need verification._
- **Are the 328 inferred relationships involving `HandlerContext` (e.g. with `BotApp` and `Telegram bot application — command handlers, callback router, and lifecycle.`) actually correct?**
  _`HandlerContext` has 328 INFERRED edges - model-reasoned connections that need verification._
- **Are the 173 inferred relationships involving `Store` (e.g. with `Config` and `BotApp`) actually correct?**
  _`Store` has 173 INFERRED edges - model-reasoned connections that need verification._
- **Are the 169 inferred relationships involving `ScanResult` (e.g. with `_BoundedHashSet` and `CompletionSecurityResult`) actually correct?**
  _`ScanResult` has 169 INFERRED edges - model-reasoned connections that need verification._