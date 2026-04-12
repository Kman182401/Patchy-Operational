---
tags:
  - work/upgrade
aliases:
  - Alert notifications Clear button
created: 2026-04-11
updated: 2026-04-11
status: open
priority: low
---

# Alert notifications Clear button

## Overview

Patchy Bot sends two kinds of notification messages into the Telegram chat: **success** notifications (a download finished, a search completed) and **alert** notifications (a download stalled, the VPN dropped, qBittorrent is firewalled, disk space is low). Success notifications are useful as a permanent record. Alerts are different — once you've seen an alert and the underlying problem is gone, the alert is just clutter.

This upgrade adds a **"Clear"** button to alert notifications only. Tapping the button deletes the alert message from the chat, the same way the user could delete it manually, but with one tap instead of long-press → select → delete. Success notifications keep the existing layout and do not get the button.

The work needs to find every place that emits an alert (the runners, the download handlers, the health checker), add the button to those keyboards, and register a single dispatcher callback that handles the delete.

> [!code]- Claude Code Reference
> **Alert emission sites (incomplete — verify by grep)**
> - `patchy_bot/handlers/download.py` — stall, tracker error, pending timeout, malware scan failures
> - `patchy_bot/health.py` — VPN drop, qBT firewalled, disk low
> - `patchy_bot/bot.py` — runner-emitted alerts (qbt health check tick, schedule runner errors)
>
> **UI**
> - `patchy_bot/ui/keyboards.py` — add a `clear_alert_keyboard()` (or extend an existing builder) that includes a single button with callback data like `alert:clear`
> - Use `↩️ Back` / `🏠 Home` conventions — but for this case the only button is `🧹 Clear` since there's nothing else to navigate to
>
> **Dispatcher**
> - Register an `alert:` prefix handler via `CallbackDispatcher` in `dispatch.py`
> - The handler calls `context.bot.delete_message(chat_id, message_id)` and does nothing else
>
> **Distinguishing success vs alert**
> - The button must appear ONLY on alert messages, never on success notifications. The cleanest way is per-call: each emission site explicitly attaches the clear keyboard for alerts and omits it for successes — do not try to detect alert vs success after the fact.
>
> **Tests**
> - Add a callback test for `alert:clear` in `tests/test_handlers.py`
> - Confirm `pytest -q` from `telegram-qbt/` is green
