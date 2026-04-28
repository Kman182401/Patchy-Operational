# Community 16 — Schedule Handler

**53 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `on_cb_schedule()` | `telegram-qbt/patchy_bot/handlers/schedule.py:L1914` | 36 |
| `FakeBotApp` | `telegram-qbt/tests/test_schedule.py:L43` | 21 |
| `.create_schedule_track()` | `telegram-qbt/patchy_bot/store.py:L1088` | 14 |
| `test_schedule.py` | `telegram-qbt/tests/test_schedule.py:L1` | 12 |
| `_make_probe()` | `telegram-qbt/tests/test_schedule.py:L32` | 10 |
| `_make_show()` | `telegram-qbt/tests/test_schedule.py:L28` | 9 |
| `TestCreateScheduleTrackEnabled` | `telegram-qbt/tests/test_schedule.py:L138` | 9 |
| `._schedule_row()` | `telegram-qbt/patchy_bot/store.py:L1074` | 8 |
| `test_pkback_deletes_disabled_track()` | `telegram-qbt/tests/test_schedule.py:L236` | 7 |
| `test_dlgo_from_picker_activates_track()` | `telegram-qbt/tests/test_schedule.py:L300` | 7 |
| `test_dlgo_from_picker_without_pending_still_works()` | `telegram-qbt/tests/test_schedule.py:L338` | 7 |
| `.get_schedule_track()` | `telegram-qbt/patchy_bot/store.py:L1152` | 6 |
| `.test_update_enabled_activates_track()` | `telegram-qbt/tests/test_schedule.py:L185` | 6 |
| `._schedule_preview_text()` | `telegram-qbt/tests/test_schedule.py:L85` | 5 |
| `.test_disabled_track_invisible_to_due_query()` | `telegram-qbt/tests/test_schedule.py:L170` | 5 |

## Connected Communities

- [[Community 0 — Core Types & Clients]] (24 edges)
- [[Community 4 — Parsing & Utilities]] (13 edges)
- [[Community 6 — Movie Scheduling]] (12 edges)
- [[Community 1 — BotApp & Command Flow]] (9 edges)
- [[Community 8 — Callback Dispatch]] (5 edges)
- [[Community 7 — Runners & Progress]] (2 edges)

## All Nodes (53)

- `on_cb_schedule()` — `telegram-qbt/patchy_bot/handlers/schedule.py` (36)
- `FakeBotApp` — `telegram-qbt/tests/test_schedule.py` (21)
- `.create_schedule_track()` — `telegram-qbt/patchy_bot/store.py` (14)
- `test_schedule.py` — `telegram-qbt/tests/test_schedule.py` (12)
- `_make_probe()` — `telegram-qbt/tests/test_schedule.py` (10)
- `_make_show()` — `telegram-qbt/tests/test_schedule.py` (9)
- `TestCreateScheduleTrackEnabled` — `telegram-qbt/tests/test_schedule.py` (9)
- `._schedule_row()` — `telegram-qbt/patchy_bot/store.py` (8)
- `test_pkback_deletes_disabled_track()` — `telegram-qbt/tests/test_schedule.py` (7)
- `test_dlgo_from_picker_activates_track()` — `telegram-qbt/tests/test_schedule.py` (7)
- `test_dlgo_from_picker_without_pending_still_works()` — `telegram-qbt/tests/test_schedule.py` (7)
- `.get_schedule_track()` — `telegram-qbt/patchy_bot/store.py` (6)
- `.test_update_enabled_activates_track()` — `telegram-qbt/tests/test_schedule.py` (6)
- `._schedule_preview_text()` — `telegram-qbt/tests/test_schedule.py` (5)
- `.test_disabled_track_invisible_to_due_query()` — `telegram-qbt/tests/test_schedule.py` (5)
- `._clear_flow()` — `telegram-qbt/tests/test_movie_schedule.py` (5)
- `._render_command_center()` — `telegram-qbt/tests/test_movie_schedule.py` (5)
- `._schedule_download_requested()` — `telegram-qbt/tests/test_schedule.py` (4)
- `.test_default_enabled_is_1()` — `telegram-qbt/tests/test_schedule.py` (4)
- `.test_enabled_0_creates_disabled_track()` — `telegram-qbt/tests/test_schedule.py` (4)
- `.test_dedup_returns_existing_track()` — `telegram-qbt/tests/test_schedule.py` (4)
- `test_pkback_without_pending_track_is_safe()` — `telegram-qbt/tests/test_schedule.py` (4)
- `._home_only_keyboard()` — `telegram-qbt/tests/test_movie_schedule.py` (4)
- `.list_due_schedule_tracks()` — `telegram-qbt/patchy_bot/store.py` (3)
- `._schedule_confirm_selection()` — `telegram-qbt/tests/test_schedule.py` (3)
- `test_dlback_from_picker_preserves_pending_track_id()` — `telegram-qbt/tests/test_schedule.py` (3)
- `test_schedule_preview_text_missing_strips_season_prefix()` — `telegram-qbt/tests/test_parsing.py` (3)
- `.get_schedule_track_any()` — `telegram-qbt/patchy_bot/store.py` (2)
- `.list_schedule_tracks()` — `telegram-qbt/patchy_bot/store.py` (2)
- `._on_cb_schedule()` — `telegram-qbt/patchy_bot/bot.py` (2)
- `schedule_dl_confirm_keyboard()` — `telegram-qbt/patchy_bot/handlers/schedule.py` (2)
- `._schedule_preview_keyboard()` — `telegram-qbt/tests/test_schedule.py` (2)
- `._schedule_picker_text()` — `telegram-qbt/tests/test_schedule.py` (2)
- `._schedule_picker_keyboard()` — `telegram-qbt/tests/test_schedule.py` (2)
- `fake_app()` — `telegram-qbt/tests/test_schedule.py` (2)
- `test_home_only_keyboard_contains_home_button()` — `telegram-qbt/tests/test_parsing.py` (2)
- `test_render_command_center_edits_existing_message()` — `telegram-qbt/tests/test_parsing.py` (2)
- `test_schedule_preview_text_inventory_uses_status_icons()` — `telegram-qbt/tests/test_parsing.py` (2)
- `test_schedule_preview_text_next_air_ts_uses_relative_time()` — `telegram-qbt/tests/test_parsing.py` (2)
- `test_schedule_download_requested_edits_status_card_not_new_message()` — `telegram-qbt/tests/test_parsing.py` (2)
- `test_schedule_download_requested_no_waiting_for_hash_message()` — `telegram-qbt/tests/test_parsing.py` (2)
- `Missing and other-season-gaps lines show Exx, not SxxExx.` — `telegram-qbt/tests/test_parsing.py` (2)
- `.__init__()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._set_flow()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._get_flow()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._clear_flow()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._render_schedule_ui()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._render_nav_ui()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._home_only_keyboard()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._schedule_dl_confirm_text()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._schedule_dl_confirm_keyboard()` — `telegram-qbt/tests/test_schedule.py` (1)
- `._cleanup_poster_photo()` — `telegram-qbt/tests/test_schedule.py` (1)
- `query()` — `telegram-qbt/tests/test_schedule.py` (1)
