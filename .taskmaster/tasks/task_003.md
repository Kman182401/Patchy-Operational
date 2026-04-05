# Task ID: 3

**Title:** Extract UI builders into ui/ modules

**Status:** pending

**Dependencies:** 1

**Priority:** high

**Description:** Move all _*_keyboard() methods into patchy_bot/ui/keyboards.py and all _*_text() methods into patchy_bot/ui/text.py. Move flow state helpers (_set_flow, _get_flow, _clear_flow) into patchy_bot/ui/flow.py. Move render helpers (_render_nav_ui, _render_flow_ui, _render_remove_ui, _render_schedule_ui, _render_tv_ui, ephemeral cleanup) into patchy_bot/ui/rendering.py. In bot.py, replace each moved method with a delegation call or direct import.

**Details:**

This task extracts ~500 lines of UI code from bot.py into 4 new modules under patchy_bot/ui/. The keyboard methods include: _nav_footer, _home_only_keyboard, _compact_action_rows, _command_center_keyboard, _tv_filter_choice_keyboard, _media_picker_keyboard, _stop_download_keyboard, _remove_prompt_keyboard, _remove_browse_root_keyboard, _remove_candidate_keyboard, _remove_confirm_keyboard, _remove_show_action_keyboard, _remove_season_action_keyboard, _remove_paginated_keyboard, _schedule_candidate_keyboard, _schedule_preview_keyboard, _schedule_missing_keyboard, _schedule_episode_picker_keyboard, _schedule_picker_keyboard, _schedule_dl_confirm_keyboard. Text methods include: _tv_filter_choice_text, _tv_filter_prompt_text, _tv_title_prompt_text, _start_text, _help_text, _plex_storage_display, _active_downloads_section, _schedule_preview_text, _schedule_track_ready_text, _schedule_missing_text, _schedule_picker_text, _schedule_dl_confirm_text, _remove_candidate_text, _remove_candidates_text, _remove_confirm_text, _remove_list_text, _remove_show_actions_text, _remove_season_actions_text. Create patchy_bot/ui/__init__.py.

**Test Strategy:**

All existing tests that call UI methods (test_parsing.py has ~15 such tests) must pass. Deploy and verify all Telegram screens render correctly. Spot-check: Command Center, remove candidate list, schedule preview, TV filter choice.

## Subtasks

### 3.1. Create ui/keyboards.py with all _*_keyboard() methods

**Status:** pending  
**Dependencies:** None  

Extract ~20 keyboard builder methods from bot.py into patchy_bot/ui/keyboards.py. Each method becomes a standalone function that receives HandlerContext.

### 3.2. Create ui/text.py with all _*_text() methods

**Status:** pending  
**Dependencies:** None  

Extract ~18 text builder methods from bot.py into patchy_bot/ui/text.py. Each method receives HandlerContext for access to config and store.

### 3.3. Create ui/flow.py with flow state management

**Status:** pending  
**Dependencies:** None  

Extract _set_flow, _get_flow, _clear_flow and flow UI message tracking into patchy_bot/ui/flow.py.

### 3.4. Create ui/rendering.py with render helpers

**Status:** pending  
**Dependencies:** None  

Extract _render_nav_ui, _render_flow_ui, _render_remove_ui, _render_schedule_ui, _render_tv_ui, _cleanup_private_user_message, ephemeral message cleanup into patchy_bot/ui/rendering.py.

### 3.5. Wire delegation stubs in bot.py and verify all UI tests pass

**Status:** pending  
**Dependencies:** None  

Replace each extracted method in bot.py with a delegation to the new ui/ module. Run full test suite — 15+ UI tests must pass.
