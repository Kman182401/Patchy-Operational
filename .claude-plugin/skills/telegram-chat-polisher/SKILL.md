---
name: telegram-chat-polisher
description: Refines Telegram bot chat UI — message text, button labels, keyboard layouts, and navigation flows. Invoke this skill when writing or reviewing /start, search results, settings menus, inline keyboards, confirmation prompts, status messages, or any message a user reads and taps. Also invoke it when a flow currently sends multiple sequential messages and could be a single editable keyboard, when button labels are too long or vague, or when a menu has too many competing options. Even if the user says "clean up the messages" or "the buttons are confusing" or "improve /start", invoke this skill first.
---

# Telegram Chat Polisher

The goal is a bot that feels immediate, clear, and native to Telegram — not like a web form squeezed into a chat window.

## The edit-first principle

Sending a new message for every navigation step creates a chat that fills with stale messages. **Edit the existing message instead.**

```python
# Navigating to a sub-menu
async def handle_settings(query: CallbackQuery) -> None:
    await query.edit_message_text(
        "Settings",
        reply_markup=settings_keyboard()
    )
    # Never: await query.message.reply_text(...)

# Toggling a setting — flip the label, edit in place
async def handle_toggle_notifications(query: CallbackQuery) -> None:
    new_state = toggle_setting(query.from_user.id, "notifications")
    label = "Notifications: ON" if new_state else "Notifications: OFF"
    keyboard = build_settings_keyboard(notifications_on=new_state)
    await query.edit_message_reply_markup(reply_markup=keyboard)
```

Send a **new message** only when:
- Starting a genuinely new context (new search, new session)
- The old message should remain as a visible record (a completed add/remove)
- Telegram won't allow editing (message is over 48 hours old, or was deleted)

## Button label rules

| Do | Don't |
|---|---|
| Add Movie | Click here to add a movie |
| Remove | Delete this item |
| Search Again | Go back and search |
| Schedule | Set up schedule |
| Active (3) | View active downloads |

- **Action verb first**: "Add", "Remove", "Search", "View", "Confirm"
- **Max 20 characters** including emoji — anything longer wraps or truncates on small phones
- **One emoji max per button**, placed at the front, only when it adds meaning
- **Avoid "Back"** as a standalone label — prefer context: "Back to Results", "Back to Menu"
- Destructive buttons say exactly what they destroy: "Delete Torrent", "Cancel Schedule", not just "Delete"

## Message text rules

Structure every message as:

```
[Bold header — max 40 chars]

[Body — max 3 lines, only if genuinely needed]
```

- Users scan Telegram messages, they don't read them. If the body can be removed and the buttons still make sense, remove it.
- Use `✅` `❌` `⏳` `📥` `📺` for state — they communicate instantly.
- Never explain what the buttons do in the message body. The button label does that.
- Avoid markdown that clutters: don't bold random words, don't use headers (`#`) in chat messages.

**Example — before/after:**

Before:
```
Search Results
Here are the top results for your search. Please tap the Add button next to the one
you want to add to qBittorrent. You can also tap Show More to see additional results.

[Add] [Add] [Add] [Show More] [Cancel]
```

After:
```
🔍 Results for "Dune 2021 4K" (8 found)

[📥 Add #1] [📥 Add #2]
[📥 Add #3] [Show More →]
[✖ Cancel]
```

## /start command center

`/start` is the bot's home screen. It should load instantly and show exactly what the user can do.

Structure:
```
[Bot name / brief tagline — 1 line]

[Primary action 1]
[Primary action 2]  [Primary action 3]
[Settings]          [Status]
```

Rules:
- No "Welcome to the bot! Here's how to use me:" paragraphs
- 4-6 action buttons maximum
- First button = the action the user will use 80% of the time
- Status/health/profile go last

For a returning user with active downloads, show active count inline: `Active (2)`.

## Keyboard layout hierarchy

```
[PRIMARY ACTION]               ← row 1, full width
[Secondary A]  [Secondary B]  ← row 2, 2-column
[Navigation A] [Navigation B] ← last row, 2-column
```

- One primary action per keyboard. If two actions feel equally important, pick one — the other goes secondary.
- Confirmation before any destructive action:
  ```
  [Confirm Delete ✓]  [Cancel ✗]
  ```
  Never put Confirm and Cancel on separate rows — they're a paired decision.
- Pagination: `[← Prev]  Page 2/5  [Next →]` — keep the page indicator as disabled/text button in the middle.

## callback_data conventions

Telegram enforces a 64-byte limit on `callback_data`. Keep it short.

```python
# Good — namespaced, compact
"add:123"
"rm:456"
"page:search:2"
"tog:notif:1"

# Bad — too verbose, may hit byte limit
"action=add&torrent_id=123&user_id=456"
```

Format: `command:payload` or `command:subcommand:payload`

Never put user-visible text in callback_data — it's an internal state key, not a label.

## Paginating results

For paginated search results, edit the message for every page turn:

```python
async def show_results(query: CallbackQuery, page: int) -> None:
    results = get_results_page(page)
    await query.edit_message_text(
        format_results(results, page),
        reply_markup=pagination_keyboard(page, total_pages)
    )
```

Never append pages as new messages — the user can't scroll back through 5 messages of results without losing their place.

## Settings menus

Settings should be a single editable message. Each toggle edits the keyboard in place.

Pattern:
```
⚙️ Settings

[Notifications: ON ✓]
[Auto-schedule: OFF]
[Profile]
[Back to Menu]
```

Tapping a toggle immediately edits the button label — no confirmation needed for non-destructive toggles. The changed label *is* the confirmation.

## Status and alert messages

Ephemeral confirmations (download added, torrent removed) should be:
1. Answer callback query with a toast: `await query.answer("✅ Added")` — this shows as a non-intrusive popup
2. Or edit the current message if the state meaningfully changes

Use `answer()` for quick confirmations — it doesn't add noise to the chat. Reserve `send_message()` for state changes the user needs to be able to scroll back to.
