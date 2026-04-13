# How to Use This Vault

Fast and easy. Especially on your phone.

Two layers:

- **Quick capture** — `Inbox/`, `Daily/`, this guide. Use these on the go.
- **Operational** — `00-Home/` through `05-Changelog/`. Patchy Bot tooling writes here. You don't need to touch them by hand.

When in doubt, dump into Inbox or your Daily Note.

## Tasks — One-tap Workflow

**The fastest way: `Tasks.md`**
It's bookmarked at the top of your left sidebar. One tap to open. Four sections (Today / This Week / Someday / Waiting On / Done). Type freely.

**Add a task** — tap the ☑ checkbox button (first button in the mobile toolbar). It drops a `- [ ]` on the current line. Type the task. Done.

**Complete a task** — tap the `[ ]` box. It flips to `[x]` and the whole line visually crosses out and dims. No extra taps.

**Add a note under a task** — tap at the end of the task, press Enter, then tap the `→|` indent button. Type the note. You get:
```
- [ ] Fix the bug
    - tried restarting, still broken
    - error message: ...
```
Completing the parent task leaves the notes readable (they only dim slightly).

**iOS home-screen shortcuts for true zero-tap capture:**
Open Safari, go to each URL below, Share → Add to Home Screen:

- `obsidian://open?vault=Patchy%20Ops&file=Tasks` — jump straight to Tasks
- `obsidian://daily?vault=Patchy%20Ops` — jump straight to today's daily note
- `obsidian://new?vault=Patchy%20Ops&file=Inbox%2FQuick&append=true&content=%0A-%20%5B%20%5D%20` — append a new task line to `Inbox/Quick.md`

For a **text-prompt one-tap** ("ask me what the task is, then add it"), build an iOS Shortcut:
1. Shortcuts app → `+` → Add Action → "Ask for Input" (prompt: "New task")
2. Add Action → "URL" → set to `obsidian://new?vault=Patchy%20Ops&file=Tasks&append=true&content=%0A-%20%5B%20%5D%20` then append the "Provided Input" variable (URL-encoded)
3. Add Action → "Open URLs"
4. Save → Add to Home Screen

Now tapping that icon: prompt → type → done. The task lands in `Tasks.md`.

## One-tap Capture

**Daily Note (recommended)**
Tap the 📅 calendar icon in the mobile toolbar. Today's note opens with sections ready to fill in. Type under Quick Notes, To-Do, or Ideas. Auto-saves.

**New Note**
Tap the pencil/compose icon. A blank note is created in `Inbox/`. Type the title, type the thought. Done.

**From the iOS home screen**
Open Safari, type `obsidian://daily`, tap Share → Add to Home Screen. Now one tap from your home screen drops you into today's daily note.

## Folders

- **Inbox/** — quick captures, unsorted notes
- **Daily/** — auto-created daily notes
- **00-Home/** — Dashboard and vault guide (auto)
- **01-System/** — Patchy Bot architecture (auto)
- **02-Work/** — active todos and upgrades
- **03-Reference/** — conventions, runbook, preferences
- **04-Ideas/** — parked ideas
- **05-Changelog/** — session changelog entries
- **_templates/** — note templates (don't touch)

## Core Plugins

Built-in only. No community plugins.

- **Daily Notes** — one note per day with a template
- **Templates** — pre-fills new notes with sections
- **Bookmarks** — pinned notes in the left sidebar
- **Search** — the 🔍 magnifying glass in the mobile toolbar
- **Quick Switcher** — jump between notes fast
- **Slash Commands** — type `/` inside a note for formatting
- **Outline** — headings of the current note
- **File Recovery** — undelete safety net

## Working-Context.md

The file `Working-Context.md` at the vault root is the bridge to Claude.ai on mobile. Keep it updated with what you're working on, recent decisions, and blockers. Paste its GitHub raw URL into Claude mobile so Claude can fetch the latest state.

GitHub raw URL (update after first push):

```
https://raw.githubusercontent.com/Kman182401/Patchy-Operational/main/Patchy%20Ops/Working-Context.md
```

## Tips

- **Don't organize.** Dump into Inbox or Daily. Sort later, or don't.
- **Links:** type `[[` and start typing a note name. The main power feature of Obsidian.
- **Tags:** add `#patchy`, `#idea`, `#todo` anywhere. Search finds them.
- **Sync:** Obsidian Sync pushes edits between phone and PC. Then `push` on PC updates GitHub.
