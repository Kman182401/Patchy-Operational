---
tags:
  - reference
aliases:
  - User Preferences
created: 2026-04-11
updated: 2026-04-11
---

# Preferences

## Overview

This is the master list of how the user wants Patchy Bot built and changed. **Read it before starting any task.**

New preferences get added under "Learned Preferences" with a date — they never get deleted, only struck through if they go obsolete.

### Telegram message style

We use **HTML parse mode** for every Telegram message because Telegram supports it natively and it lets us do bold, italic, and code spans without the constant `\_` and `\*` escaping headache that Markdown causes when filenames contain underscores.

Any dynamic value (filename, title, error message) that goes into a message has to be passed through `_h()` (a thin wrapper around `html.escape`) so that things like `<` and `&` in titles can't break the message or get interpreted as fake HTML.

### Buttons and selection

When the user picks something from a list of buttons, we mark the picked item with a leading `✅`. **Unselected items are plain text** — never `⬜`. The empty checkbox emoji renders weirdly on different devices and looks cluttered.

For navigation, the only labels we use are `↩️ Back` and `🏠 Home`. **No "Cancel" buttons, ever.** "Cancel" feels like throwing work away; "Back" feels like stepping out, which is what's actually happening.

Almost everything in the bot is driven by inline keyboard buttons rather than typed text. If a flow can be done with buttons, it has to be done with buttons.

### Code style and patterns

- **Type hints required** on every new function signature so the linter and humans can both see what's going on.
- **Parameterized SQL only.** Never glue strings into queries — use `?` placeholders.
- **Scoring functions penalize, they don't hard-reject.** If a torrent is bad, subtract from its score; don't return `-9999`. The exception is real safety (malware, etc.).
- **In-memory caching** for hot polling loops, with SQLite as the restart-safe backup. Don't hammer the database in a tight loop.
- **Files stay under 500 lines.** If something grows past that, decompose it.
- **Group EMA variables.** When we use multiple related smoothing variables (like `smooth_progress_pct`, `smooth_dls`, `smooth_uls`), they all get initialized and checked together — never one without the others.

### Architecture rules

- Runtime code lives in `telegram-qbt/patchy_bot/`. The old `qbt_telegram_bot.py` is a back-compat shim — don't edit it for runtime changes.
- **Anything that has to survive a restart** goes in SQLite via `store.py`. Transient UI flow state can stay in memory.
- **Movies and TV are siblings.** Any change to Movie Search has to also be applied to TV Search, and vice versa. Same for any other paired flow.
- **Download path parity.** If a change touches the immediate download path, it also has to touch the deferred-hash pending path in `handlers/download.py` — they're two halves of one feature.
- **SQLite is in WAL mode** with `busy_timeout=5000`. Don't disable that.
- **DB file permissions are `0o600`** (owner-only). Backup directories are `0o700`.
- **`QBClient` is thread-safe via `threading.Lock()`** — keep the lock scope minimal and never hold it across an `await`.
- **Path containment uses `PurePosixPath.is_relative_to()`**, never `str.startswith()` (which gets fooled by directory name overlaps).
- **No `os.path.exists()` before `shutil.move()`.** That's a TOCTOU race. Use try/except instead.
- **Validate file extensions** before moving anything into the Plex library directories.

### Process

- **Always restart** `telegram-qbt-bot.service` after any change under `patchy_bot/`.
- **Run `pytest -q`** in `telegram-qbt/` for any Python area you touched, when tests exist for it.
- **Subagent-driven development.** Every task gets dispatched to the matching domain subagent. Don't write domain logic inline.
- **Prefer code over docs** when they disagree — the code is the source of truth.
- **Targeted changes only.** Don't rewrite unrelated flows or move files around without a clear reason.
- **No git writes** in `Patchy_Bot/` unless the user asks in the current message.
- **No saving plans to files.** Plans are presented inline in chat.
- **No `type: "prompt"` hooks of any kind.** They cause mid-process halts and infinite loops.

### Branding

Patchy is a pirate. The branding emoji is `🏴‍☠️` — never `🐾`.

## Learned Preferences

_New preferences discovered during work get added here with a date. Never deleted; obsolete entries get ~~strikethrough~~._

> [!code]- Claude Code Reference
> **Telegram UI**
> - HTML parse mode only; never Markdown
> - Escape all dynamic values with `_h()` from `utils.py` (wraps `html.escape`)
> - Selected items: `✅` prefix; unselected: plain text (never `⬜`)
> - Navigation: `↩️ Back` / `🏠 Home` only (never `Cancel`)
> - Inline buttons over text input wherever possible
> - Callback data format: colon-delimited `prefix:param1:param2`
> - Branding emoji: `🏴‍☠️`
>
> **Code style**
> - Type hints on all new function signatures
> - Parameterized SQL queries only
> - Scoring functions: penalize (`score -= N`), do not hard-reject
> - In-memory cache for hot loops; SQLite as restart-safe fallback
> - Use `episode_code(season, episode)` (returns `S01E05`)
> - Use `build_requests_session()` for HTTP clients
> - Use `human_size()`, `now_ts()`
> - Group EMA variables (init/check together)
> - Files under 500 lines
>
> **Architecture**
> - Edit `patchy_bot/` package modules; `qbt_telegram_bot.py` is a shim
> - Restart-safe state → `store.py`; transient → memory
> - Movies/TV feature parity
> - Download immediate-path / deferred-hash pending-path parity
> - WAL mode + `busy_timeout=5000`
> - DB file `0o600`, backup dir `0o700`
> - `QBClient` thread-safe via `threading.Lock()`; minimal scope; no lock-across-await
> - `PurePosixPath.is_relative_to()` for containment
> - No `os.path.exists()` before `shutil.move()`
> - Validate file extensions before Plex moves
> - Never bind qBT to VPN interface (breaks libtorrent DNS)
>
> **Process**
> - Restart `telegram-qbt-bot.service` after any `patchy_bot/` change
> - `pytest -q` in `telegram-qbt/` for touched areas
> - Subagent-driven development (delegate per task; two-stage review; no inline)
> - Prefer code over docs
> - Targeted changes only
> - No git writes unless explicitly requested
> - No plan files
> - No `type: "prompt"` hooks
> - No hardcoded `model` in Agent tool calls — let `settings.json` decide
>
> **Don'ts**
> - No `⬜` emoji
> - No "Cancel" buttons
> - No commits of secrets / `.env` / credentials
> - No edits to `qbt_telegram_bot.py` for runtime changes
> - No inline domain implementation — always delegate
