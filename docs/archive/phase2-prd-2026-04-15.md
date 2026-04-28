# Patchy Bot — Phase 2 PRD: Monolith Decomposition

## 1. Problem Statement

`patchy_bot/bot.py` is a **6,671-line monolithic class** (`BotApp`) containing ~185 methods, 53+ callback prefixes in a single 1,251-line if/elif chain, and 9 logically distinct domains fused into one file. This causes:

- **Blast radius**: Any edit to one domain (e.g., schedule) can silently break unrelated domains (e.g., remove) because all code shares the same namespace and class scope.
- **Untestable isolation**: Testing a single callback handler requires instantiating the entire `BotApp` with all its clients and state. 162 tests exist but only cover parsing, path safety, and auth — zero coverage for download tracking, search execution, command handlers, and most callback flows.
- **Merge conflicts**: Any two concurrent feature branches touching bot.py will conflict because all domains live in the same file.
- **Onboarding cost**: A developer must understand 6,671 lines of interleaved domains to make any change safely.
- **Background task races**: Progress trackers, CC refresh loops, and background runners operate as `asyncio.Task` alongside the sequential handler chain, reading/writing shared dicts (`user_flow`, `progress_tasks`, etc.) without synchronization.

## 2. Current Architecture

### Module Map (verified line counts)

```
patchy_bot/                         # 9,238 lines total
  bot.py              6,671         # THE MONOLITH — all handlers, callbacks, runners
  store.py              882         # SQLite: 11 tables, 30+ CRUD methods, WAL mode
  config.py             162         # Config dataclass, 48 env vars
  utils.py              356         # Pure functions, constants, episode parsing
  rate_limiter.py        67         # Per-user sliding-window rate limiter
  logging_config.py      48         # JSON formatter for journalctl
  __main__.py            82         # Entry: logging -> Config -> BotApp -> polling
  __init__.py            58         # Re-exports
  clients/
    qbittorrent.py      253         # QBClient: qBT WebUI API v2 (thread-safe)
    llm.py              111         # PatchyLLMClient: OpenAI-compat
    tv_metadata.py      158         # TVMetadataClient: TVMaze + TMDB
    plex.py             389         # PlexInventoryClient: Plex XML API

plex_organizer.py       336         # Outside package — moves downloads to Plex folders
qbt_telegram_bot.py      53         # Backward-compat shim (tests import from here)

tests/
  test_parsing.py     3,327         # 122 tests — primary suite
  test_delete_safety.py 431         # 20 tests — path safety
  test_auth_ratelimit.py 225        # 20 tests — auth/rate-limit
```

### Dependency Arrows

```
__main__.py ---> bot.py ---> config.py
                  |   |---> store.py ---> utils.py
                  |   |---> rate_limiter.py
                  |   |---> utils.py
                  |   |---> clients/{qbittorrent, llm, tv_metadata, plex}.py ---> utils.py
                  |   \---> plex_organizer.py  (OUTSIDE PACKAGE — cross-boundary)
                  |
tests/*.py ---> qbt_telegram_bot.py ---> patchy_bot.*  (backward-compat shim)
```

### bot.py Domain Boundaries (verified method names and line ranges)

| Domain | Lines | Method Count | Key Methods |
|--------|-------|-------------|-------------|
| Init & lifecycle | 68-193 | 4 | `__init__`, `_post_init`, `_post_stop`, `build_application` |
| Infrastructure helpers | 194-301 | 8 | `_targets`, `_storage_status`, `_qbt_transport_status`, `_ensure_media_categories` |
| Auth system | 302-360 | 4 | `_is_allowlisted`, `_requires_password`, `is_allowed`, `deny` |
| Flow & UI framework | 354-568 | 15 | `_set_flow`, `_get_flow`, `_clear_flow`, `_render_nav_ui`, `_render_flow_ui`, `_render_remove_ui`, `_render_schedule_ui`, `_render_tv_ui` |
| Download tracking | 567-987 | 15 | `_track_download_progress`, `_completion_poller_job`, `_start_progress_tracker` |
| Command center | 987-1299 | 16 | `_command_center_keyboard`, `_render_command_center`, `_command_center_refresh_loop`, `_start_text`, `_help_text` |
| **Schedule system** | **1300-2791** | **~60** | `_schedule_runner_job`, `_schedule_probe_bundle`, `_schedule_attempt_auto_acquire`, all `_schedule_*` keyboards/text |
| Search & LLM chat | 2791-3257 | 13 | `_run_search`, `_apply_filters`, `_render_page`, `_reply_patchy_chat` |
| **Remove system** | **3257-4121** | **~45** | `_find_remove_candidates`, `_delete_remove_candidate`, `_remove_runner_job`, all `_remove_*` keyboards/text |
| Display commands | 4121-4290 | 7 | `_send_active`, `_render_active_ui`, `_send_categories`, `_render_categories_ui` |
| Command handlers | 4290-5374 | 28 | `cmd_start` through `cmd_logout`, `on_text` (330 lines), `_do_add` |
| **Callback router** | **5374-6625** | **1** | `on_callback` — 1,251 lines, 53 prefixes in if/elif chain |

### Callback Prefix Groups (53 total)

- **nav:** `nav:home` (1)
- **add/download:** `a:`, `d:`, `p:` (3)
- **remove:** `rm:cancel`, `rm:browse`, `rm:browsecat:`, `rm:bpage:`, `rm:pick:`, `rm:series`, `rm:seasons`, `rm:cpage:`, `rm:child:`, `rm:seasondel`, `rm:episodes`, `rm:epage:`, `rm:episode:`, `rm:back:show`, `rm:back:season`, `rm:review`, `rm:clear`, `rm:confirm` (18)
- **schedule:** `sch:cancel`, `sch:pick:`, `sch:change`, `sch:season`, `sch:confirm:all`, `sch:confirm:series`, `sch:confirm:pick`, `sch:confirm`, `sch:all:`, `sch:pickeps:`, `sch:pktog:`, `sch:pkseason:`, `sch:pkconfirm`, `sch:pkback`, `sch:dlgo`, `sch:dlback`, `sch:ep:`, `sch:skip:` (18)
- **menu:** `menu:movie`, `menu:tv`, `menu:schedule`, `menu:remove`, `menu:active`, `menu:storage`, `menu:plugins`, `menu:profile`, `menu:help` (9)
- **flow:** `flow:tv_filter_set`, `flow:tv_filter_skip`, `flow:tv_full_series` (3)
- **stop:** `stop:` (1)

### Test Coverage Summary

| Domain | Tests | Verdict |
|--------|-------|---------|
| Utils/parsing | 122 | Covered |
| Path safety | 20 | Covered |
| Auth/rate-limit | 20 | Covered |
| UI rendering | ~15 | Partial |
| Schedule logic | ~12 | Partial |
| Remove logic | ~10 | Partial |
| Download tracking | 0 | **Gap** |
| Search execution | 0 | **Gap** |
| LLM/Patchy chat | 0 | **Gap** |
| Command handlers | 0 | **Gap** |
| QBClient | 0 | **Gap** |
| TVMetadataClient | 0 | **Gap** |
| plex_organizer | 0 | **Gap** |

## 3. Target Architecture

After decomposition, the package structure becomes:

```
patchy_bot/
  __main__.py              # Unchanged
  bot.py                   # Slim orchestrator: init, build_application, shared state (~800 lines target)
  config.py                # Unchanged
  store.py                 # Unchanged
  utils.py                 # Unchanged
  rate_limiter.py          # Unchanged
  logging_config.py        # Unchanged

  types.py                 # Shared types: HandlerContext dataclass, callback dispatch types

  dispatch.py              # Prefix-based callback dispatcher (replaces if/elif chain)

  handlers/
    __init__.py
    base.py                # BaseHandler ABC — shared interface all handlers implement
    auth.py                # Auth check, password flow, deny, session management
    commands.py            # Slash command handlers: /start, /help, /health, /speed, /profile, etc.
    search.py              # Search execution, filters, page rendering, _run_search
    download.py            # Download tracking, progress, completion poller, _do_add, VPN check
    schedule.py            # Schedule system: all _schedule_* methods, runner job, callbacks
    remove.py              # Remove system: all _remove_* methods, runner job, callbacks
    chat.py                # Patchy LLM chat: _reply_patchy_chat, system prompt, qbt snapshot

  ui/
    __init__.py
    keyboards.py           # All _*_keyboard() methods: command center, nav footer, media picker
    text.py                # All _*_text() methods: start text, help text, storage display
    flow.py                # Flow state management: _set_flow, _get_flow, _clear_flow
    rendering.py           # Render helpers: _render_nav_ui, _render_flow_ui, ephemeral cleanup
```

### What Moves Where

| From bot.py | To | Method Count |
|-------------|----|----|
| Auth methods (L302-360) + password handling in on_text | `handlers/auth.py` | ~8 |
| `_run_search`, `_apply_filters`, `_sort_rows`, `_render_page`, `_build_search_parser`, TV filter methods | `handlers/search.py` | ~13 |
| `_track_download_progress`, `_completion_poller_job`, `_do_add`, `_start_progress_tracker`, VPN check, all progress methods | `handlers/download.py` | ~20 |
| All `_schedule_*` methods + `sch:*` callbacks + `_schedule_runner_job` + `_backup_job` | `handlers/schedule.py` | ~65 |
| All `_remove_*` methods + `rm:*` callbacks + `_remove_runner_job` | `handlers/remove.py` | ~50 |
| `_reply_patchy_chat`, `_patchy_system_prompt`, `_build_qbt_snapshot`, `_chat_needs_qbt_snapshot` | `handlers/chat.py` | ~5 |
| `cmd_start` through `cmd_logout`, `_health_report`, `_speed_report`, display commands | `handlers/commands.py` | ~25 |
| All `_*_keyboard()` methods | `ui/keyboards.py` | ~20 |
| All `_*_text()` methods | `ui/text.py` | ~15 |
| Flow state methods + render helpers + ephemeral cleanup | `ui/flow.py` + `ui/rendering.py` | ~15 |

### What Stays in bot.py

- `BotApp.__init__` — creates clients, state dicts, handler instances
- `build_application` — registers handlers via the dispatcher
- `on_text` — delegates to the appropriate handler based on flow mode
- `on_callback` — replaced by a thin dispatcher call
- Shared state dict declarations (`user_flow`, `user_nav_ui`, `progress_tasks`, etc.)

**Target: bot.py shrinks from 6,671 to ~800 lines.**

### Callback Dispatcher Design

Replace the 1,251-line if/elif chain with a prefix-based dispatcher:

```python
# dispatch.py
class CallbackDispatcher:
    def __init__(self):
        self._exact: dict[str, Callable] = {}
        self._prefix: list[tuple[str, Callable]] = []

    def register_exact(self, data: str, handler: Callable):
        self._exact[data] = handler

    def register_prefix(self, prefix: str, handler: Callable):
        self._prefix.append((prefix, handler))
        # Sort by prefix length descending for longest-match-first
        self._prefix.sort(key=lambda x: len(x[0]), reverse=True)

    async def dispatch(self, data: str, **kwargs) -> bool:
        if data in self._exact:
            await self._exact[data](**kwargs)
            return True
        for prefix, handler in self._prefix:
            if data.startswith(prefix):
                await handler(**kwargs)
                return True
        return False
```

Each handler module registers its own prefixes during `BotApp.__init__`. This gives O(1) exact-match dispatch and clean isolation.

## 4. Migration Strategy

### Approach: Strangler Fig

Each task follows this pattern:
1. Create the new module with methods extracted from bot.py
2. In bot.py, replace the extracted methods with thin delegation calls to the new module
3. Run tests — existing tests must pass unchanged
4. Deploy (systemd restart) and verify in Telegram
5. If broken, revert the extract — bot.py still has the delegation stubs, which can be reverted to inline code

### Ordering Rationale

Foundation work first (types, dispatcher, handler base), then domain extractions in dependency order (low coupling domains first, high coupling last), then cleanup.

## 5. Task Breakdown

### Task 1: Create shared types and handler base class
- **Description**: Create `patchy_bot/types.py` with a `HandlerContext` dataclass that wraps the shared state handlers need (cfg, store, qbt, plex, tvmeta, llm, rate_limiter, user_flow, user_nav_ui, progress_tasks, chat_history). Create `patchy_bot/handlers/base.py` with a `BaseHandler` ABC that accepts this context. This establishes the contract all extracted handlers will follow.
- **Dependencies**: None
- **Priority**: high
- **testStrategy**: Import types.py and base.py, instantiate HandlerContext with dummy values, create a trivial BaseHandler subclass. Run existing test suite — must still pass.

### Task 2: Build the callback dispatcher
- **Description**: Create `patchy_bot/dispatch.py` with a `CallbackDispatcher` class supporting exact-match and prefix-match registration. Replace the `on_callback` if/elif chain in bot.py with a dispatcher that routes to the same existing methods (still on BotApp). This is a mechanical refactor — behavior does not change, only the dispatch mechanism.
- **Dependencies**: [1]
- **Priority**: high
- **testStrategy**: Register all 53 current prefixes on the dispatcher. Unit test that each prefix routes to the correct method name. Run existing callback tests — all must pass. Deploy and verify all Telegram button flows work.

### Task 3: Extract UI builders into ui/ modules
- **Description**: Move all `_*_keyboard()` methods into `patchy_bot/ui/keyboards.py` and all `_*_text()` methods into `patchy_bot/ui/text.py`. Move flow state helpers (`_set_flow`, `_get_flow`, `_clear_flow`) into `patchy_bot/ui/flow.py`. Move render helpers (`_render_nav_ui`, `_render_flow_ui`, `_render_remove_ui`, `_render_schedule_ui`, `_render_tv_ui`, ephemeral cleanup) into `patchy_bot/ui/rendering.py`. In bot.py, replace each moved method with a delegation call or direct import.
- **Dependencies**: [1]
- **Priority**: high
- **testStrategy**: All existing tests that call UI methods (test_parsing.py has ~15 such tests) must pass. Deploy and verify all Telegram screens render correctly. Spot-check: Command Center, remove candidate list, schedule preview, TV filter choice.

### Task 4: Extract the search handler
- **Description**: Move search-related methods into `patchy_bot/handlers/search.py`: `_build_search_parser`, `_apply_filters`, `_sort_rows`, `_parse_tv_filter`, `_build_tv_query`, `_strip_patchy_name`, `_extract_search_intent`, `_render_page`, `_run_search`. The handler registers itself with the dispatcher for `a:`, `d:`, and `p:` callback prefixes. Update bot.py's `on_text` movie/tv flow branches to delegate to the search handler.
- **Dependencies**: [2, 3]
- **Priority**: high
- **testStrategy**: Add at least 5 new unit tests for `_apply_filters` and `_sort_rows` with known input/output pairs. Existing episode-code tests must pass. Deploy and test: movie search flow, TV search flow, page navigation, add-to-library flow.

### Task 5: Extract the download tracking handler
- **Description**: Move download/progress methods into `patchy_bot/handlers/download.py`: `_progress_bar`, `_completed_bytes`, `_is_complete_torrent`, `_format_eta`, `_state_label`, `_eta_label`, `_render_progress_text`, `_start_progress_tracker`, `_start_pending_progress_tracker`, `_attach_progress_tracker_when_ready`, `_stop_download_keyboard`, `_tracker_send_fallback`, `_safe_tracker_edit`, `_track_download_progress`, `_completion_poller_job`, `_is_direct_torrent_link`, `_result_to_url`, `_extract_hash`, `_resolve_hash_by_name`, `_vpn_ready_for_download`, `_do_add`. Register `stop:` callback prefix.
- **Dependencies**: [2, 3]
- **Priority**: medium
- **testStrategy**: Add at least 5 new unit tests for `_progress_bar`, `_format_eta`, `_is_complete_torrent` with known inputs. Deploy and test: start a download, verify progress bar updates, verify completion notification fires.

### Task 6: Extract the schedule handler
- **Description**: Move all `_schedule_*` methods (~60 methods, lines 1300-2791) plus `_backup_job` into `patchy_bot/handlers/schedule.py`. Register all `sch:*` callback prefixes. Update bot.py's `on_text` schedule flow branches to delegate. This is the largest extraction (~1,490 lines).
- **Dependencies**: [2, 3, 5]
- **Priority**: high
- **testStrategy**: All existing schedule tests in test_parsing.py (~12 tests) must pass. Deploy and test: /schedule flow, show lookup, season pick, episode picker, confirm tracking, verify schedule runner fires on interval.

### Task 7: Extract the remove handler
- **Description**: Move all `_remove_*` methods (~45 methods, lines 3257-4121) plus `_cleanup_qbt_for_path`, `_delete_remove_candidate`, `_delete_remove_candidates`, `_remove_runner_job`, `_remove_build_job_verification`, `_remove_attempt_plex_cleanup` into `patchy_bot/handlers/remove.py`. Register all `rm:*` callback prefixes. Update bot.py's `on_text` remove flow branches to delegate.
- **Dependencies**: [2, 3]
- **Priority**: high
- **testStrategy**: All 20 delete-safety tests must pass. All existing remove UI tests must pass. Deploy and test: /remove search flow, browse library, multi-select, confirm delete, Plex cleanup notification.

### Task 8: Extract the command handlers
- **Description**: Move slash command methods into `patchy_bot/handlers/commands.py`: `cmd_start`, `cmd_search`, `cmd_schedule`, `cmd_remove`, `cmd_show`, `cmd_add`, `cmd_categories`, `cmd_mkcat`, `cmd_setminseeds`, `cmd_setlimit`, `cmd_profile`, `cmd_active`, `cmd_plugins`, `cmd_help`, `cmd_health`, `cmd_speed`, `cmd_unlock`, `cmd_logout`, `_cmd_text_fallback`, `_health_report`, `_speed_report`, `on_error`. Register all `menu:*` and `flow:*` callback prefixes. Move display helpers: `_send_active`, `_render_active_ui`, `_send_categories`, `_render_categories_ui`, `_send_plugins`, `_render_plugins_ui`.
- **Dependencies**: [2, 3, 4, 5, 6, 7]
- **Priority**: medium
- **testStrategy**: Add at least 3 new tests for `_health_report` and `_speed_report`. Deploy and verify every slash command works in Telegram. Test the Command Center menu flow end to end.

### Task 9: Extract the LLM chat handler
- **Description**: Move Patchy chat methods into `patchy_bot/handlers/chat.py`: `_chat_needs_qbt_snapshot`, `_build_qbt_snapshot`, `_patchy_system_prompt`, `_reply_patchy_chat`. Re-enable Patchy chat (currently gated by config — remove the hardcoded disable, rely on `patchy_chat_enabled` config flag).
- **Dependencies**: [1, 3]
- **Priority**: low
- **testStrategy**: Add at least 3 unit tests: `_chat_needs_qbt_snapshot` with various inputs, `_patchy_system_prompt` returns non-empty string, `_build_qbt_snapshot` with mock QBClient. Deploy and test: send a free-text message that triggers the chat fallback.

### Task 10: Move plex_organizer.py into the package
- **Description**: Move `plex_organizer.py` from the `telegram-qbt/` root into `patchy_bot/plex_organizer.py`. Update the import in bot.py from `from plex_organizer import organize_download` to `from .plex_organizer import organize_download`. Update the backward-compat shim in `qbt_telegram_bot.py` if it re-exports anything from plex_organizer. This eliminates the cross-boundary import that depends on the working directory.
- **Dependencies**: None
- **Priority**: medium
- **testStrategy**: Run existing test suite — must pass. Import `patchy_bot.plex_organizer` from any directory and verify it loads without error. Deploy and verify a completed download gets organized into Plex folders.

### Task 11: Add pytest configuration
- **Description**: Add `[tool.pytest.ini_options]` to `pyproject.toml` with: `testpaths = ["tests"]`, `python_files = ["test_*.py"]`, `python_functions = ["test_*"]`, `addopts = "-q --tb=short"`. Verify all 162 existing tests still pass with the new config.
- **Dependencies**: None
- **Priority**: low
- **testStrategy**: Run `python -m pytest` from the telegram-qbt directory and confirm all 162 tests pass with the new configuration. Verify `pytest` (without `python -m`) also works.

### Task 12: Test backfill for extracted modules
- **Description**: Add targeted tests for the largest coverage gaps exposed during extraction. Minimum new tests: (1) `handlers/search.py` — `_apply_filters` with quality/size/seed filters, `_sort_rows` with various keys; (2) `handlers/download.py` — `_progress_bar` at 0/50/100%, `_format_eta` edge cases, `_is_complete_torrent` for various states; (3) `handlers/commands.py` — `_health_report` returns valid HTML, `_speed_report` formats correctly; (4) `handlers/chat.py` — `_chat_needs_qbt_snapshot` returns correct boolean. Target: +30 new tests minimum.
- **Dependencies**: [4, 5, 6, 7, 8, 9]
- **Priority**: medium
- **testStrategy**: Run full test suite. Coverage for each new handler module should have at least 3 focused unit tests. No existing tests should regress.

### Task 13: Final cleanup — remove dead code from bot.py
- **Description**: After all extractions are complete: (1) Remove all delegation stubs from bot.py that now just call handler methods — replace with direct handler references in build_application. (2) Remove orphaned imports. (3) Verify bot.py is under 1,000 lines. (4) Update the backward-compat shim in `qbt_telegram_bot.py` to re-export from new module locations if needed. (5) Update `patchy_bot/__init__.py` re-exports.
- **Dependencies**: [4, 5, 6, 7, 8, 9, 10]
- **Priority**: low
- **testStrategy**: Run full test suite — all 162+ tests must pass. Import from `qbt_telegram_bot` in a test script and verify all documented public names are still accessible. Deploy and verify complete end-to-end flow: /start -> search movie -> add -> monitor progress -> complete -> /schedule show -> /remove item.

## 6. Risks and Mitigations

### Risk 1: Breaking the backward-compat shim
**Impact**: Tests import from `qbt_telegram_bot.py`, which re-exports `from patchy_bot import *`. Moving methods into handler submodules could break these exports.
**Mitigation**: Every extraction task must verify `qbt_telegram_bot.py` imports still resolve. The shim only needs to re-export public names (classes, utility functions), not internal handler methods. Update `patchy_bot/__init__.py` as needed.

### Risk 2: Shared mutable state access after extraction
**Impact**: Extracted handlers need access to `self.user_flow`, `self.store`, `self.qbt`, etc. Passing too many arguments creates unwieldy signatures.
**Mitigation**: The `HandlerContext` dataclass (Task 1) bundles all shared state into one object. Each handler receives it at construction time. This keeps signatures clean and makes dependencies explicit.

### Risk 3: Background task races become visible
**Impact**: Progress trackers and schedule runners access shared state concurrently. Moving code into separate modules doesn't change the concurrency model, but could expose assumptions about execution order.
**Mitigation**: Do not change `concurrent_updates=False`. Background tasks already use `asyncio.to_thread()` for blocking calls. Document which state each handler module reads/writes so future work can add proper synchronization.

### Risk 4: Large extraction tasks (schedule = 1,490 lines, remove = 863 lines)
**Impact**: These are the riskiest extractions — many methods, high internal coupling, and callback routing all tangled together.
**Mitigation**: Extract methods mechanically first (copy, then delegate), run tests at each step. The schedule and remove domains are already well-prefixed (`_schedule_*`, `_remove_*`) which makes them easy to identify and move as a batch.

### Risk 5: plex_organizer.py relocation breaks systemd service
**Impact**: The service runs `python -m patchy_bot` from a working directory. If plex_organizer moves into the package, the import path changes.
**Mitigation**: Task 10 explicitly updates the import path. Test by running `python -c "from patchy_bot.plex_organizer import organize_download"` before deploying.

### Risk 6: Bot downtime during deployment
**Impact**: Each extraction requires a `systemctl restart` which briefly stops the bot.
**Mitigation**: Each task is deployable independently with a single restart (~2s downtime). No database migrations, no config changes. If a deployment breaks, `git checkout bot.py` and restart to restore the previous state.

## 7. Success Criteria

| Metric | Before | After | Measurement |
|--------|--------|-------|-------------|
| `bot.py` line count | 6,671 | < 1,000 | `wc -l patchy_bot/bot.py` |
| `on_callback` method length | 1,251 lines | 0 (replaced by dispatcher) | Method no longer exists |
| Handler module count | 0 | 7 (auth, search, download, schedule, remove, commands, chat) | `ls patchy_bot/handlers/*.py` |
| UI module count | 0 | 4 (keyboards, text, flow, rendering) | `ls patchy_bot/ui/*.py` |
| Test count | 162 | 192+ (minimum 30 new) | `pytest --co -q \| wc -l` |
| Test regression | 0 failures | 0 failures | All 162 existing tests pass after every task |
| Zero-downtime verification | N/A | Every task deployed and verified in Telegram | Manual verification checklist per task |
| Backward-compat shim | Works | Still works | `python -c "from qbt_telegram_bot import BotApp, Store, Config"` |
| Cross-boundary import | `from plex_organizer import ...` | `from .plex_organizer import ...` | plex_organizer lives inside patchy_bot/ |
