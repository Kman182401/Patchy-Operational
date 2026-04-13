# Patchy Bot — System Audit Snapshot

**Generated:** 2026-04-13
**Repo root:** `/home/karson/Patchy_Bot`
**Runtime root:** `/home/karson/Patchy_Bot/telegram-qbt`

---

## 1. bot.py Line Count

```
5552 telegram-qbt/patchy_bot/bot.py
```

Note: The runtime `CLAUDE.md` claims "~4,752 lines" — **actual = 5,552 lines** (1.17× the documented figure; docs drift).

---

## 2. Full Package Tree (`patchy_bot/*.py`)

```
patchy_bot/__init__.py
patchy_bot/__main__.py
patchy_bot/bot.py
patchy_bot/config.py
patchy_bot/dispatch.py
patchy_bot/health.py
patchy_bot/logging_config.py
patchy_bot/malware.py
patchy_bot/path_safety.py
patchy_bot/plex_organizer.py
patchy_bot/quality.py
patchy_bot/rate_limiter.py
patchy_bot/store.py
patchy_bot/types.py
patchy_bot/utils.py
patchy_bot/clients/__init__.py
patchy_bot/clients/llm.py
patchy_bot/clients/plex.py
patchy_bot/clients/qbittorrent.py
patchy_bot/clients/tv_metadata.py
patchy_bot/handlers/__init__.py
patchy_bot/handlers/_shared.py
patchy_bot/handlers/base.py
patchy_bot/handlers/chat.py
patchy_bot/handlers/commands.py
patchy_bot/handlers/download.py
patchy_bot/handlers/full_series.py
patchy_bot/handlers/remove.py
patchy_bot/handlers/schedule.py
patchy_bot/handlers/search.py
patchy_bot/ui/__init__.py
patchy_bot/ui/flow.py
patchy_bot/ui/keyboards.py
patchy_bot/ui/rendering.py
patchy_bot/ui/text.py
```

**Total:** 35 `.py` files.

---

## 3. SQLite Tables (`CREATE TABLE` in store.py)

Primary CREATE TABLE statements (excluding `_new` migration temps):

1. `searches` (L60)
2. `results` (L68)
3. `user_defaults` (L85)
4. `user_auth` (L93)
5. `auth_attempts` (L99)
6. `schedule_tracks` (L106)
7. `schedule_runner_status` (L131)
8. `schedule_show_cache` (L146)
9. `remove_jobs` (L156)
10. `notified_completions` (L182)
11. `download_health_events` (L188)
12. `movie_tracks` (L202)
13. `command_center_ui` (L230)
14. `malware_scan_log` (L241)

**Total:** 14 tables. (Migration-only `_new` variants at L335, L414 exist but are transient.)

---

## 4. Public CRUD Methods in store.py

**Count (via `inspect.getmembers`):** 60 public methods on `Store`.

```
backup
cleanup
cleanup_old_completion_records
cleanup_old_health_events
cleanup_old_malware_logs
clear_auth_failures
clear_movie_track_pending_torrent
close
count_due_schedule_tracks
create_movie_track
create_remove_job
create_schedule_track
db_diagnostics
delete_movie_track
delete_schedule_track
get_command_center
get_completion_user_id
get_defaults
get_downloading_movie_tracks
get_health_events
get_movie_track
get_movie_tracks_for_user
get_movies_due_release_check
get_pending_movie_tracks
get_remove_job
get_result
get_schedule_runner_status
get_schedule_show_cache
get_schedule_track
get_schedule_track_any
get_search
get_title_only_tracks
increment_movie_plex_failures
is_auth_locked
is_completion_notified
is_unlocked
list_all_schedule_tracks
list_due_remove_jobs
list_due_schedule_tracks
list_schedule_tracks
lock_user
log_health_event
log_malware_block
mark_completion_notified
movie_track_exists_for_title
movie_track_exists_for_tmdb
record_auth_failure
reset_movie_plex_failures
save_command_center
save_search
set_defaults
set_movie_track_pending_torrent
unlock_user
update_movie_release_dates
update_movie_track_next_check
update_movie_track_status
update_remove_job
update_schedule_runner_status
update_schedule_track
upsert_schedule_show_cache
```

CLAUDE.md documents "56+" — **actual = 60**.

---

## 5. Config Env Vars

The `Config` dataclass has **60 fields**, all populated from environment variables in `Config.from_env()`.

Env var names (in order they appear in `from_env`):

```
TELEGRAM_BOT_TOKEN
ALLOWED_TELEGRAM_USER_IDS
DEFAULT_MIN_QUALITY
PATCHY_CHAT_ENABLED
PATCHY_LLM_BASE_URL
PATCHY_LLM_API_KEY
ALLOW_GROUP_CHATS
BOT_ACCESS_PASSWORD
ACCESS_SESSION_TTL_SECONDS
REQUIRE_VPN_FOR_DOWNLOADS
VPN_SERVICE_NAME
VPN_INTERFACE_NAME
QBT_BASE_URL
QBT_USERNAME
QBT_PASSWORD
TMDB_API_KEY
TMDB_REGION
PLEX_BASE_URL
PLEX_TOKEN
DB_PATH
RESULT_PAGE_SIZE
SEARCH_TIMEOUT_SECONDS
POLL_INTERVAL_SECONDS
SEARCH_EARLY_EXIT_MIN_RESULTS
SEARCH_EARLY_EXIT_IDLE_SECONDS
SEARCH_EARLY_EXIT_MAX_WAIT_SECONDS
DEFAULT_RESULT_LIMIT
DEFAULT_SORT
DEFAULT_ORDER
DEFAULT_MIN_SEEDS
MOVIES_CATEGORY
TV_CATEGORY
SPAM_CATEGORY
MOVIES_PATH
TV_PATH
SPAM_PATH
NVME_MOUNT_PATH
REQUIRE_NVME_MOUNT
PATCHY_CHAT_NAME
PATCHY_CHAT_MODEL
PATCHY_CHAT_FALLBACK_MODEL
PATCHY_CHAT_TIMEOUT_SECONDS
PATCHY_CHAT_MAX_TOKENS
PATCHY_CHAT_TEMPERATURE
PATCHY_CHAT_HISTORY_TURNS
PROGRESS_REFRESH_SECONDS
PROGRESS_EDIT_MIN_SECONDS
PROGRESS_SMOOTHING_ALPHA
PROGRESS_TRACK_TIMEOUT_SECONDS
STALL_METADATA_WARN_SECONDS
STALL_ZERO_PROGRESS_WARN_SECONDS
STALL_AUTO_RETRY_ENABLED
STALL_MAX_RETRIES
PREFLIGHT_CHECK_ENABLED
PREFLIGHT_MIN_DISK_GB
HEALTH_EVENT_RETENTION_DAYS
FILE_INSPECTION_TIMEOUT_SECONDS
MALWARE_SCAN_TIMEOUT_SECONDS
LOG_CLEAN_SCANS
BACKUP_DIR
```

---

## 6. Slash Commands

### `cmd_*` functions defined in `handlers/commands.py`

```
cmd_start         (L321)
cmd_search        (L370)
cmd_schedule      (L415)
cmd_remove        (L478)
cmd_show          (L499)
cmd_add           (L535)
cmd_categories    (L608)
cmd_mkcat         (L628)
cmd_setminseeds   (L655)
cmd_setlimit      (L681)
cmd_profile       (L707)
cmd_active        (L745)
cmd_plugins       (L768)
cmd_help          (L788)
cmd_health        (L817)
cmd_speed         (L834)
cmd_unlock        (L854)
cmd_logout        (L908)
cmd_text_fallback (L930)   [MessageHandler, not /slash]
```

### `CommandHandler` registrations in `bot.py` (`_register_handlers`, L5528+)

```
/start        → cmd_start
/help         → cmd_help
/health       → cmd_health
/speed        → cmd_speed
/search       → cmd_search
/schedule     → cmd_schedule
/remove       → cmd_remove
/show         → cmd_show
/add          → cmd_add
/categories   → cmd_categories
/mkcat        → cmd_mkcat
/setminseeds  → cmd_setminseeds
/setlimit     → cmd_setlimit
/profile      → cmd_profile
/active       → cmd_active
/plugins      → cmd_plugins
/unlock       → cmd_unlock
/logout       → cmd_logout
```

**Total: 18 registered slash commands.** `cmd_text_fallback` is bound separately as a `MessageHandler`, not a `CommandHandler`. Matches the runtime CLAUDE.md's "18 slash commands" figure.

---

## 7. Callback Registrations (`bot.py::_register_callbacks`, L165+)

| Kind | Prefix / Exact | Handler |
|------|----------------|---------|
| exact | `nav:home` | `_on_cb_nav_home` |
| prefix | `a:` | `_on_cb_add` |
| prefix | `d:` | `_on_cb_download` |
| prefix | `p:` | `_on_cb_page` |
| prefix | `rm:` | `_on_cb_remove` |
| prefix | `sch:` | `_on_cb_schedule` |
| prefix | `msch:` | `_on_cb_movie_schedule` |
| prefix | `menu:` | `_on_cb_menu` |
| prefix | `flow:` | `_on_cb_flow` |
| exact | `dl:manage` | `_on_cb_dl_manage` |
| prefix | `mwblock:` | `_on_cb_mwblock` |
| prefix | `stop:all:` | `_on_cb_stop` |
| prefix | `stop:` | `_on_cb_stop` |
| prefix | `tvpost:` | `_on_cb_tvpost` |
| prefix | `moviepost:` | `_on_cb_moviepost` |
| prefix | `tvpick:` | `_on_cb_tv_pick` |
| prefix | `moviepick:` | `_on_cb_movie_pick` |
| prefix | `fsd:` | `_on_cb_fsd` |

**Totals:** 2 `register_exact`, 16 `register_prefix` = **18 callback registrations**.

Runtime CLAUDE.md documents "2 exact + 12 prefix" — **prefix count is now 16, not 12** (docs drift: `mwblock:`, `stop:all:`, `stop:`, `tvpost:`, `moviepost:`, `tvpick:`, `moviepick:`, `fsd:` additions).

---

## 8. Test Files (`tests/test_*.py`)

```
test_auth_ratelimit.py
test_callbacks.py
test_candidate_cycling.py
test_completion_security_gate.py
test_delete_safety.py
test_dispatch.py
test_download_monitor.py
test_download_pipeline.py
test_full_series.py
test_handlers.py
test_health.py
test_health_store.py
test_llm_client.py
test_malware.py
test_movie_schedule.py
test_no_1080p.py
test_organizer.py
test_parsing.py
test_path_safety.py
test_plex_client.py
test_plex_organizer.py
test_poster_urls.py
test_progress.py
test_quality.py
test_runners.py
test_schedule.py
test_scoring.py
test_search_security.py
test_season_pack.py
test_theatrical_search.py
```

**Total: 30 test files.** (Runtime CLAUDE.md says "23 test files" — drifted; **actual = 30**.)

---

## 9. Test Count

```
.venv/bin/python -m pytest tests/ --collect-only -q
→ 1099 tests collected in 0.27s
```

**Total: 1,099 collected tests.** (Runtime CLAUDE.md says "760 tests" — drifted; **actual = 1,099**.)

---

## 10. Background Runner Intervals

| Runner | Interval | Source |
|--------|----------|--------|
| **schedule-runner** | 60 s | `handlers/schedule.py::schedule_runner_interval_s()` L71 `return 60` |
| **remove-runner** | 60 s | `handlers/remove.py::remove_runner_interval_s()` L56 `return 60` |
| **completion-poller** | 60 s (first=10 s) | `bot.py` L1204-1210 `run_repeating(... interval=60, first=10, name="completion-poller")` |
| **command center refresh** | 3 s active / 12 s idle | `bot.py::_command_center_refresh_loop` L1025 `asyncio.sleep(3)`; L1057 `asyncio.sleep(12)` when idle (breaks after 4 idle cycles) |
| **qbt-health-check** | 300 s | `bot.py` L236-239 `interval=300, first=300, name="qbt-health-check"` |

Other `asyncio.sleep` calls in `bot.py`: L2162 (5s), L2212 (5s) — both retry backoffs inside `_qbt_health_restart()`, not steady-state runner intervals.

---

## 11. Subagents (`.claude/agents/`)

```
audit-correctness-agent.md
audit-performance-agent.md
config-infra-agent.md
coverage-analysis-agent.md
database-agent.md
dependency-audit-agent.md
lint-type-agent.md
media-library-abstraction-agent.md
monitoring-metrics-agent.md
movie-tracking-agent.md
performance-optimization-agent.md
plex-agent.md
release-manager-agent.md
remove-agent.md
schedule-agent.md
search-download-agent.md
secret-scanner-agent.md
security-agent.md
security-scan-orchestrator.md
static-analysis-agent.md
supply-chain-scan-agent.md
taskmaster-sync-agent.md
test-agent.md
torrent-client-abstraction-agent.md
ui-agent.md
vault-manager.md
```

**Total: 26 agent files.** (Runtime CLAUDE.md says "25 agents" — off by one; `vault-manager.md` appears unlisted in docs.)

---

## 12. Skills (`skills/`)

```
assumptions-audit
diff-review
global
patchy-bot
reuse-check
scope-guard
```

**Total: 6 skill directories** in `skills/`. (`.claude/skills/` does not exist.)

---

## 13. Service Unit File

**Path:** `/etc/systemd/system/telegram-qbt-bot.service`

```ini
[Unit]
Description=Telegram qBittorrent Operator Bot
After=network-online.target qbittorrent.service
Wants=network-online.target

[Service]
Type=simple
User=karson
Group=karson
WorkingDirectory=/home/karson/Patchy_Bot/telegram-qbt
EnvironmentFile=/home/karson/Patchy_Bot/telegram-qbt/.env
ExecStart=/home/karson/Patchy_Bot/telegram-qbt/.venv/bin/python -m patchy_bot
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Dependencies:**
- `After=network-online.target qbittorrent.service`
- `Wants=network-online.target`
- (No `Requires=`)

**Hardening drift:** Runtime CLAUDE.md claims `ProtectSystem=strict`, `NoNewPrivileges=true`, `PrivateTmp=true`, `ReadWritePaths=...` — **none of these directives are present in the actual installed unit file.** The installed unit has no sandboxing hardening at all.

---

## 14. HandlerContext Fields (`types.py`)

From `@dataclass HandlerContext`:

**Clients (immutable after init):**
- `cfg: Config`
- `store: Store`
- `qbt: QBClient`
- `plex: PlexInventoryClient`
- `tvmeta: TVMetadataClient`
- `patchy_llm: PatchyLLMClient`
- `rate_limiter: RateLimiter`

**Shared mutable state:**
- `user_flow: dict[int, dict[str, Any]]`
- `user_nav_ui: dict[int, dict[str, int]]`
- `progress_tasks: dict[tuple[int, str], asyncio.Task[Any]]`
- `pending_tracker_tasks: dict[tuple[int, str, str], asyncio.Task[Any]]`
- `batch_monitor_messages: dict[int, Any]`
- `batch_monitor_tasks: dict[int, asyncio.Task[Any]]`
- `batch_monitor_data: dict[tuple[int, str], dict[str, Any]]`
- `user_ephemeral_messages: dict[int, list[dict[str, int]]]`
- `command_center_refresh_tasks: dict[int, asyncio.Task[Any]]`
- `chat_history: collections.OrderedDict[int, list[dict[str, str]]]`
- `chat_history_max_users: int = 50`

**Schedule source health:**
- `schedule_source_state: dict[str, dict[str, Any]]` (metadata + inventory sub-states)
- `schedule_source_state_lock: threading.Lock`

**Async locks for background runners:**
- `schedule_runner_lock: asyncio.Lock`
- `remove_runner_lock: asyncio.Lock`
- `state_lock: asyncio.Lock`

**Sequential download queue:**
- `download_queue: asyncio.Queue[dict[str, Any]]`
- `active_download_hash: str | None`
- `download_queue_lock: asyncio.Lock`

**Pending scans (torrents added, not resumed):**
- `pending_scans: dict[str, dict[str, Any]]`

**Fire-and-forget background tasks:**
- `background_tasks: set[asyncio.Task[Any]]`

**App / callback hooks (set post-init):**
- `app: Any = None`
- `render_command_center: Any = None`
- `navigate_to_command_center: Any = None`

**Total: 28 fields.** (7 clients + 11 mutable-state + 2 schedule-source + 3 async locks + 3 download-queue + 1 pending_scans + 1 background_tasks + 3 app/callbacks.)

---

## 15. `ui/` Module Structure

```
patchy_bot/ui/__init__.py
patchy_bot/ui/flow.py
patchy_bot/ui/keyboards.py
patchy_bot/ui/rendering.py
patchy_bot/ui/text.py
```

### `ui/flow.py` (public functions)

- `set_flow(ctx, user_id, payload)`
- `get_flow(ctx, user_id)`
- `clear_flow(ctx, user_id)`

### `ui/keyboards.py` (public functions)

- `nav_footer(*, back_data, include_home)`
- `home_only_keyboard()`
- `compact_action_rows(...)`
- `command_center_keyboard(...)`
- `manage_downloads_keyboard(...)`
- `tv_filter_choice_keyboard()`
- `post_add_movie_keyboard()`
- `post_add_tv_standard_keyboard(...)`
- `post_add_tv_full_season_keyboard(sid)`
- `post_add_tv_full_series_keyboard()`
- `tv_show_picker_keyboard(results, back_data)`
- `movie_picker_keyboard(results, back_data)`
- `tv_followup_same_season_keyboard(sid)`
- `candidate_nav_keyboard(...)`
- `media_picker_keyboard(sid, idx, *, back_data)`
- `full_series_confirm_keyboard(to_download)`
- `full_series_progress_keyboard()`
- `full_series_complete_keyboard()`
- `full_series_cancelled_keyboard()`
- `tracked_list_page_bounds(items, page, per_page)`
- `tracked_list_keyboard(...)`

### `ui/rendering.py` (public functions)

- `remember_nav_ui_message(ctx, user_id, message)`
- `remember_flow_ui_message(...)`
- `track_ephemeral_message(ctx, user_id, message)`
- `cleanup_ephemeral_messages(ctx, user_id, bot)` *(async)*
- `strip_old_keyboard(bot, chat_id, message_id)` *(async)*
- `delete_old_nav_ui(ctx, user_id, bot)` *(async)*
- `cleanup_private_user_message(message)` *(async)*
- `cancel_pending_trackers_for_user(ctx, user_id)`
- `render_nav_ui(...)` *(async)*
- `render_flow_ui(...)` *(async)*
- `render_remove_ui(...)` *(async)*
- `render_schedule_ui(...)` *(async)*
- `render_tv_ui(...)` *(async)*

### `ui/text.py` (public functions)

- `format_risk_badge(scan)`
- `tracked_list_header(title, icon)`
- `tv_track_line(track)`
- `movie_track_line(track)`
- `tracked_list_text(...)`
- `tv_filter_choice_text()`
- `tv_filter_prompt_text(error)`
- `tv_strict_filter_error_text()`
- `tv_full_season_prompt_text(error)`
- `tv_full_season_title_prompt_text(season)`
- `tv_no_season_packs_text()`
- `tv_title_prompt_text(season, episode)`
- `tv_followup_same_season_text(show_title, season)`
- `tv_followup_episode_prompt_text(...)`
- `tv_followup_season_episode_prompt_text(...)`
- `tv_followup_season_prompt_text(...)`
- `start_text(...)`
- `tv_candidate_caption(candidate, idx, total)`
- `movie_candidate_caption(candidate, idx, total, query)`
- `tv_show_picker_text(results)`
- `movie_picker_text(results)`
- `full_series_loading_text(show_name)`
- `full_series_bundle_error_text(show_name)`
- `full_series_confirm_text(...)`
- `full_series_status_text(state)`
- `full_series_complete_text(state)`
- `full_series_cancelled_text(state)`
- `help_text()`
- `help_section_text(section)`

---

## 16. `handlers/` Module Structure

```
patchy_bot/handlers/__init__.py
patchy_bot/handlers/_shared.py
patchy_bot/handlers/base.py
patchy_bot/handlers/chat.py
patchy_bot/handlers/commands.py
patchy_bot/handlers/download.py
patchy_bot/handlers/full_series.py
patchy_bot/handlers/remove.py
patchy_bot/handlers/schedule.py
patchy_bot/handlers/search.py
```

10 files total (9 modules + `__init__.py`).

---

## Documentation Drift Summary

The following values in `telegram-qbt/CLAUDE.md` are stale vs. actual code:

| Claim in docs | Actual |
|---------------|--------|
| `bot.py` "~4,752 lines" | **5,552 lines** |
| `store.py` "14 tables, 56+ CRUD methods" | 14 tables ✅, **60** CRUD methods |
| "2 exact + 12 prefix registrations" | **2 exact + 16 prefix** |
| "18 slash commands" | **18** ✅ |
| "760 tests across 23 test files" | **1,099 tests across 30 test files** |
| "25 agents" in `.claude/agents/` | **26 agents** (vault-manager added) |
| Service hardening: `ProtectSystem=strict`, `NoNewPrivileges=true`, `PrivateTmp=true`, `ReadWritePaths=...` | **None of these directives exist in the installed unit file** |

End of snapshot.
