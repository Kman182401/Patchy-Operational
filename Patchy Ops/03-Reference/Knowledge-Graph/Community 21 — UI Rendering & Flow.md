# Community 21 — UI Rendering & Flow

**37 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `rendering.py` | `telegram-qbt/patchy_bot/ui/rendering.py:L1` | 17 |
| `render_flow_ui()` | `telegram-qbt/patchy_bot/ui/rendering.py:L206` | 8 |
| `flow.py` | `telegram-qbt/patchy_bot/ui/flow.py:L1` | 6 |
| `remember_nav_ui_message()` | `telegram-qbt/patchy_bot/ui/rendering.py:L23` | 5 |
| `remember_flow_ui_message()` | `telegram-qbt/patchy_bot/ui/rendering.py:L39` | 5 |
| `strip_old_keyboard()` | `telegram-qbt/patchy_bot/ui/rendering.py:L88` | 5 |
| `render_nav_ui()` | `telegram-qbt/patchy_bot/ui/rendering.py:L153` | 5 |
| `cancel_pending_trackers_for_user()` | `telegram-qbt/patchy_bot/ui/rendering.py:L136` | 4 |
| `render_remove_ui()` | `telegram-qbt/patchy_bot/ui/rendering.py:L261` | 4 |
| `render_schedule_ui()` | `telegram-qbt/patchy_bot/ui/rendering.py:L286` | 4 |
| `render_tv_ui()` | `telegram-qbt/patchy_bot/ui/rendering.py:L311` | 4 |
| `set_flow()` | `telegram-qbt/patchy_bot/ui/flow.py:L10` | 4 |
| `clear_flow()` | `telegram-qbt/patchy_bot/ui/flow.py:L20` | 4 |
| `.save_command_center()` | `telegram-qbt/patchy_bot/store.py:L514` | 3 |
| `._strip_old_keyboard()` | `telegram-qbt/patchy_bot/bot.py:L489` | 3 |

## Connected Communities

- [[Community 0 — Core Types & Clients]] (21 edges)
- [[Community 1 — BotApp & Command Flow]] (14 edges)
- [[Community 4 — Parsing & Utilities]] (2 edges)
- [[Community 2 — Download Pipeline]] (2 edges)
- [[Community 6 — Movie Scheduling]] (1 edges)

## All Nodes (37)

- `rendering.py` — `telegram-qbt/patchy_bot/ui/rendering.py` (17)
- `render_flow_ui()` — `telegram-qbt/patchy_bot/ui/rendering.py` (8)
- `flow.py` — `telegram-qbt/patchy_bot/ui/flow.py` (6)
- `remember_nav_ui_message()` — `telegram-qbt/patchy_bot/ui/rendering.py` (5)
- `remember_flow_ui_message()` — `telegram-qbt/patchy_bot/ui/rendering.py` (5)
- `strip_old_keyboard()` — `telegram-qbt/patchy_bot/ui/rendering.py` (5)
- `render_nav_ui()` — `telegram-qbt/patchy_bot/ui/rendering.py` (5)
- `cancel_pending_trackers_for_user()` — `telegram-qbt/patchy_bot/ui/rendering.py` (4)
- `render_remove_ui()` — `telegram-qbt/patchy_bot/ui/rendering.py` (4)
- `render_schedule_ui()` — `telegram-qbt/patchy_bot/ui/rendering.py` (4)
- `render_tv_ui()` — `telegram-qbt/patchy_bot/ui/rendering.py` (4)
- `set_flow()` — `telegram-qbt/patchy_bot/ui/flow.py` (4)
- `clear_flow()` — `telegram-qbt/patchy_bot/ui/flow.py` (4)
- `.save_command_center()` — `telegram-qbt/patchy_bot/store.py` (3)
- `._strip_old_keyboard()` — `telegram-qbt/patchy_bot/bot.py` (3)
- `track_ephemeral_message()` — `telegram-qbt/patchy_bot/ui/rendering.py` (3)
- `cleanup_ephemeral_messages()` — `telegram-qbt/patchy_bot/ui/rendering.py` (3)
- `get_flow()` — `telegram-qbt/patchy_bot/ui/flow.py` (3)
- `._remember_flow_ui_message()` — `telegram-qbt/patchy_bot/bot.py` (2)
- `delete_old_nav_ui()` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Render helpers — nav-UI, flow-UI, and ephemeral-message lifecycle.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Persist the command-center message location in memory and the DB.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Store the flow-message location inside ``flow`` and re-save to ``ctx``.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Register a message for later bulk deletion.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Delete all ephemeral messages tracked for ``user_id``.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Remove the inline keyboard from an old message.      Called before sending a rep` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Delete the previous command-center message so /start shows a clean chat.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Cancel pending-tracker asyncio tasks for ``user_id``.      Prevents stale monito` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Render (or update) the command-center message for ``user_id``.      Edits the ex` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Render (or update) a flow-mode UI message.      Edits the existing flow message` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Convenience wrapper around ``render_flow_ui`` for the remove flow.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Convenience wrapper around ``render_flow_ui`` for the schedule flow.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Convenience wrapper around ``render_flow_ui`` for the TV-search flow.` — `telegram-qbt/patchy_bot/ui/rendering.py` (2)
- `Flow state management — get/set/clear per-user modal state.` — `telegram-qbt/patchy_bot/ui/flow.py` (2)
- `Store ``payload`` as the current flow state for ``user_id``.` — `telegram-qbt/patchy_bot/ui/flow.py` (2)
- `Return the current flow state for ``user_id``, or ``None`` if absent.` — `telegram-qbt/patchy_bot/ui/flow.py` (2)
- `Remove the flow state for ``user_id`` (no-op if not present).` — `telegram-qbt/patchy_bot/ui/flow.py` (2)
