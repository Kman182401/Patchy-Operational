# Task ID: 8

**Title:** Extract the command handlers

**Status:** done

**Dependencies:** 2 ✓, 3 ✓, 4 ✓, 5 ✓, 6 ✓, 7 ✓

**Priority:** medium

**Description:** Move slash command methods into patchy_bot/handlers/commands.py: cmd_start, cmd_search, cmd_schedule, cmd_remove, cmd_show, cmd_add, cmd_categories, cmd_mkcat, cmd_setminseeds, cmd_setlimit, cmd_profile, cmd_active, cmd_plugins, cmd_help, cmd_health, cmd_speed, cmd_unlock, cmd_logout, _cmd_text_fallback, _health_report, _speed_report, on_error. Register all menu:* and flow:* callback prefixes (12 prefixes). Move display helpers: _send_active, _render_active_ui, _send_categories, _render_categories_ui, _send_plugins, _render_plugins_ui.

**Details:**

This is the last major extraction. Command handlers are thin dispatchers — cmd_search sets up a flow and calls the search handler, cmd_schedule calls the schedule handler, etc. The main complexity is that many cmd_* methods reference other domain handlers. After tasks 4-7 extract those domains, the command handlers become simple delegation wrappers. Also includes: _health_report (~95 lines of system health checks), _speed_report (~50 lines), and the menu:* callback group which navigates between Command Center screens. The on_error method handles unhandled exceptions.

**Test Strategy:**

Add at least 3 new tests for _health_report and _speed_report. Deploy and verify every slash command works in Telegram. Test the Command Center menu flow end to end.
