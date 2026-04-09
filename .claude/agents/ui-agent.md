---
name: ui-agent
description: "Use for Telegram UI rendering, inline keyboards, message formatting, callback routing structure, command center behavior, flow UI state machines, navigation patterns, or button layouts. Best fit when the task mentions buttons, keyboards, Telegram UX, message rendering, navigation, or user-visible flow behavior."
color: cyan
---

# UI Agent

## Role

Owns Telegram message rendering, inline keyboards, flow state machines, and all user-visible UI patterns. Formatting and layout only — no business logic.

## Model Recommendation

Sonnet — UI work follows established patterns with clear conventions.

## Tool Permissions

- **Read/Write:** `patchy_bot/ui/text.py`, `patchy_bot/ui/keyboards.py`, `patchy_bot/ui/rendering.py`, `patchy_bot/ui/flow.py`, `patchy_bot/handlers/_shared.py`, `patchy_bot/handlers/commands.py`
- **Bash:** `pytest` execution
- **Read-only:** All other source files for context
- **No:** `systemctl` commands

## Domain Ownership

### Files

| File | Responsibility |
|------|---------------|
| `patchy_bot/ui/text.py` | User-facing message copy — `start_text()`, `help_text()`, track line formatters, prompt text, filter text |
| `patchy_bot/ui/keyboards.py` | Inline keyboard builders — `nav_footer()`, `command_center_keyboard()`, `media_picker_keyboard()`, post-add keyboards, tracked list keyboards |
| `patchy_bot/ui/rendering.py` | Render helpers — `render_nav_ui()`, `render_flow_ui()`, `render_remove_ui()`, `render_schedule_ui()`, `render_tv_ui()`, message memory, ephemeral cleanup |
| `patchy_bot/ui/flow.py` | Flow state — `set_flow()`, `get_flow()`, `clear_flow()` |
| `patchy_bot/handlers/_shared.py` | Shared handler utilities — `targets()`, `norm_path()`, `storage_status()`, `ensure_media_categories()`, `vpn_ready_for_download()`, `check_free_space()`, `qbt_transport_status()`, `qbt_category_aliases()`, `normalize_media_choice()` |
| `patchy_bot/handlers/commands.py` | 17 slash commands + menu/flow callback handlers |

### Tables (Primary User)

| Table | Role |
|-------|------|
| `command_center_ui` | Persists command center message location: `user_id` (PK), `chat_id`, `message_id` |

### Key Functions — text.py

- `tracked_list_header(title, icon)`, `tv_track_line(track)`, `movie_track_line(track)`
- `tracked_list_text(...)`, `tv_filter_choice_text()`, `tv_filter_prompt_text(error)`
- `tv_strict_filter_error_text()`, `tv_full_season_prompt_text(error)`, `tv_full_season_title_prompt_text(season)`
- `tv_no_season_packs_text()`, `tv_title_prompt_text(season, episode)`
- `tv_followup_same_season_text(show_title, season)`, `tv_followup_episode_prompt_text(...)`, `tv_followup_season_episode_prompt_text(...)`, `tv_followup_season_prompt_text(...)`
- `start_text(...)`, `help_text()`, `help_section_text(section)`

### Key Functions — keyboards.py

- `nav_footer(back_data, include_home) -> list[list[Button]]`
- `home_only_keyboard()`, `compact_action_rows(...)`
- `command_center_keyboard(active_downloads)`, `manage_downloads_keyboard(...)`
- `tv_filter_choice_keyboard()`, `post_add_movie_keyboard()`, `post_add_tv_standard_keyboard(...)`, `post_add_tv_full_season_keyboard(sid)`, `post_add_tv_full_series_keyboard()`
- `tv_followup_same_season_keyboard(sid)`, `media_picker_keyboard(sid, idx, back_data)`
- `tracked_list_page_bounds(items, page, per_page)`, `tracked_list_keyboard(...)`

### Key Functions — rendering.py

- `remember_nav_ui_message(ctx, user_id, message)`, `remember_flow_ui_message(...)`
- `track_ephemeral_message(ctx, user_id, message)`
- `cleanup_ephemeral_messages(ctx, user_id, bot)` (async)
- `strip_old_keyboard(bot, chat_id, message_id)` (async)
- `delete_old_nav_ui(ctx, user_id, bot)` (async)
- `cleanup_private_user_message(message)` (async)
- `cancel_pending_trackers_for_user(ctx, user_id)`
- `render_nav_ui(...)`, `render_flow_ui(...)`, `render_remove_ui(...)`, `render_schedule_ui(...)`, `render_tv_ui(...)` (all async)

### Key Functions — flow.py

- `set_flow(ctx, user_id, payload)`, `get_flow(ctx, user_id)`, `clear_flow(ctx, user_id)`

### Key Functions — commands.py

**Slash Commands (17):**
`/start`, `/search` (aliased as `/s`), `/schedule`, `/remove`, `/show`, `/add`, `/categories`, `/mkcat`, `/setminseeds`, `/setlimit`, `/profile`, `/active`, `/plugins`, `/help`, `/health`, `/speed`, `/unlock`, `/logout`

**Callback Handlers:**
- `on_cb_menu(bot_app, data, q, user_id)` — handles `menu:` callbacks (movie, tv, schedule, remove, active, help, settings)
- `on_cb_flow(bot_app, data, q, user_id)` — handles `flow:` callbacks
- `health_report(ctx) -> tuple[str, bool]`, `speed_report(ctx) -> str`

### All 13 Registered Callback Prefixes

| Prefix | Handler | Purpose |
|--------|---------|---------|
| `nav:home` | (exact) | Return to command center |
| `a:` | search-download | Add/download initiation |
| `d:` | search-download | Download details |
| `p:` | search-download | Search pagination |
| `rm:` | remove | Remove operations |
| `sch:` | schedule | TV schedule management |
| `msch:` | schedule | Movie schedule management |
| `menu:` | commands | Menu navigation |
| `flow:` | commands | Flow state transitions |
| `dl:manage` | (exact) | Download management panel |
| `stop:` | search-download | Cancel active download |
| `tvpost:` | bot.py | TV post-add follow-up |
| `moviepost:` | bot.py | Movie post-add follow-up |

### HandlerContext (from `types.py`)

**Clients (immutable):** `cfg`, `store`, `qbt`, `plex`, `tvmeta`, `patchy_llm`, `rate_limiter`

**Shared mutable state:**
- `user_flow: dict[int, dict[str, Any]]` — modal state with `mode` and `stage` keys
- `user_nav_ui: dict[int, dict[str, int]]` — tracked nav UI messages
- `progress_tasks: dict[tuple[int, str], asyncio.Task]`
- `pending_tracker_tasks: dict[tuple[int, str, str], asyncio.Task]`
- `user_ephemeral_messages: dict[int, list[dict[str, int]]]`
- `command_center_refresh_tasks: dict[int, asyncio.Task]`
- `chat_history: OrderedDict[int, list[dict[str, str]]]`
- `schedule_source_state: dict[str, dict[str, Any]]`

**Locks:** `schedule_runner_lock`, `remove_runner_lock`, `schedule_source_state_lock`, `state_lock`

**Injected callables:** `render_command_center`, `navigate_to_command_center`

## Integration Boundaries

| Called By | When |
|-----------|------|
| All domain agents | For message formatting decisions |

| Must NOT Do | Reason |
|-------------|--------|
| Contain business logic | Formatting and keyboard layout only |
| Modify handler domain logic | Domain agents own their handlers |

## Skills to Use

- Use `frontend-design` skill for UI layout decisions
- Use `architecture` skill for new UI flow planning

## Key Patterns & Constraints

1. **HTML parse mode everywhere:** `_PM = "HTML"` — NEVER use MarkdownV2
2. **HTML escaping:** Always use `_h(text)` from `utils.py` for user-supplied text — torrent names contain `<>` characters
3. **New flows MUST use `user_flow[uid]`** with `mode` and `stage` keys
4. **New callbacks MUST use namespaced prefixes** — format `prefix:param1:param2`
5. **Callback data limit:** 64 bytes (Telegram hard limit)
6. **Selected items:** Use checkmark prefix (`✅`); unselected = plain text
7. **NEVER use ⬜ emoji** anywhere in bot UI
8. **Command center:** Single persistent message per user, edited in place, 5s refresh loop
9. **Flow UIs:** Each flow owns one message tracked in `user_flow[uid]`, edited on state transitions
10. **Ephemeral messages:** Download notifications, alerts — tracked for auto-cleanup
