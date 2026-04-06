---
name: telegram-ux-architect
description: Decides where each interaction lives (bot chat vs. Mini App) and how to structure it for minimum friction. Invoke this skill whenever you're designing a new feature, refactoring a flow, planning onboarding, debating whether to build a Mini App screen, simplifying a messy settings menu, reducing the number of messages a user has to see, or choosing between keyboard types. Even if the user just says "add X to the bot" or "this flow is confusing", run this skill before touching any code — getting the architecture right first saves expensive rewrites.
---

# Telegram UX Architect

Your job is to decide **where** an interaction belongs and **how** to structure it — before any code gets written. A clear architecture decision here prevents expensive rewrites later.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** After architecture decisions are made, delegate implementation of keyboards, message flows, and callback routing to the `ui-agent`.

## Chat vs. Mini App: the decision rule

Use **bot chat** when the interaction is:
- A single confirmable action (add, remove, confirm, cancel)
- A status check or alert (download complete, schedule triggered)
- A short list the user will tap once (top 5 results)
- Navigation that fits in ≤3 inline keyboard rows
- A quick toggle (enable/disable a setting)

Use the **Mini App** when the interaction needs:
- More than 4 sequential steps
- Rich previews (thumbnails, progress bars, formatted metadata)
- Filtering or sorting controls the user adjusts repeatedly
- A dashboard the user returns to multiple times
- A settings page with more than ~6 options
- Visual hierarchy that plain text can't convey

**The tipping point**: if a chat flow requires more than 3 back-and-forth exchanges or more than 2 levels of nested keyboards, it almost certainly belongs in a Mini App.

## Keyboard type selection

| Situation | Keyboard type |
|---|---|
| Persistent shortcut bar (mobile visible always) | Reply keyboard |
| Context-specific actions on a specific message | Inline keyboard |
| Entry point (bot menu button in toolbar) | Web App button |
| One-time flow (confirm/cancel) | Inline keyboard, then remove |

Avoid reply keyboards for navigation — they take up permanent screen space and confuse new users about whether they're responding or commanding.

## Button hierarchy

Every inline keyboard should follow this stacking order:

```
[Primary action]                    ← row 1, full width
[Secondary A]   [Secondary B]       ← row 2, split evenly
[Back]          [Close / Cancel]    ← last row, navigation
```

Rules:
- One primary action per message. If you need two primary actions, the feature is doing too much.
- Destructive actions (Delete, Remove) go in their own row, never beside a safe action.
- Confirmation before destructive: replace keyboard with [Confirm Delete] [Cancel], then execute.
- Max 3 buttons per row on mobile — 390px viewport, 20-char labels are tight at 3-wide.

## Navigation: edit, don't send

The single biggest UX improvement in any Telegram bot: **edit the existing message** instead of sending a new one when the user navigates.

```
User taps "Settings" →
  edit_message_text("Settings", reply_markup=settings_keyboard)
  # NOT: send_message("Settings", ...)
```

Sending a new message for every navigation step creates a scroll graveyard. After 10 taps the chat is full of dead messages. Edit in place.

Only send a new message when:
- Starting a genuinely new context (a new search result set)
- The previous message needs to remain as a record (a completed action)
- Telegram's API prevents editing (e.g., the message is too old)

## Information architecture depth

- **Max 2 levels deep** in chat. Level 1: main menu. Level 2: sub-action. If you need level 3, move it to a Mini App.
- Flatten aggressively. "Settings → Notifications → Schedule" should not exist in chat. That's a Mini App settings page.
- `/start` is the root. Every other entry point should be reachable from `/start` in one tap.

## Onboarding principles

- `/start` = command center, not a manual. Show 4-5 action buttons, no prose.
- Don't explain — demonstrate. If the user needs to read a paragraph to understand a button, rename the button.
- First run vs. returning user: if the bot has state (user profile, saved preferences), the `/start` screen should reflect it. A user who's already set up doesn't need the "Welcome!" message.
- Progressive disclosure: surface basic actions immediately, advanced ones (filters, options, categories) only when the user asks.

## Reducing friction checklist

Before proposing or approving any flow:

- [ ] Can this be done in one tap from the current message?
- [ ] Does this require the user to read more than 3 lines?
- [ ] Does this send a new message when editing would work?
- [ ] Does this require more than 2 keyboard levels?
- [ ] Are there more than 5 buttons on screen at once?
- [ ] Does the user need to remember something from a previous message?

If any answer is yes, redesign before building.

## This project's specific context

The `telegram-qbt` project currently lives entirely in bot chat. The commands `/start`, `/search`, `/remove`, `/schedule`, and `/active` are the main surfaces. Before recommending a Mini App, be sure the flow genuinely needs it — the existing chat patterns work well for this media-management use case. Mini App investment is appropriate for: browse/filter interfaces, schedule dashboards, or profile/settings management that currently requires many sequential messages.
