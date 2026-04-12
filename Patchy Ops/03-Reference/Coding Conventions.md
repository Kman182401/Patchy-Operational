---
tags:
  - reference
aliases:
  - Coding Conventions
created: 2026-04-11
updated: 2026-04-11
---

# Coding Conventions

## Overview

These are the rules for changing Patchy Bot's code. They come from the project `CLAUDE.md` files and from things the user has explicitly said in past sessions. Each one has a "why" so you know when it applies and when it doesn't.

### Where the code lives

Almost all runtime code lives under `telegram-qbt/patchy_bot/`. The file `telegram-qbt/qbt_telegram_bot.py` is **not** the bot — it's a thin backward-compatibility shim left over from when the bot was a single file. **Don't edit it for runtime changes.** Edit the package modules instead. If you change the shim, the actual bot doesn't change, and you'll waste a debug session figuring out why.

### Restart-safe state goes in SQLite

If a piece of state has to survive the bot restarting (a tracked show, a queued removal, an auth record), it goes in SQLite via `store.py`. Transient UI flow state — "the user is on step 3 of the add-show wizard" — can stay in memory and gets thrown away on restart. This split exists because losing your auth token across restarts would be terrible, but losing a half-finished wizard is fine.

### Telegram HTML escaping

Every dynamic value going into a Telegram message has to be passed through `_h()` (a wrapper around `html.escape` in `utils.py`). The bot uses HTML parse mode for everything, and an unescaped `<` or `&` in a torrent title will either break the message or get interpreted as a fake tag. **Yes, even if you "know" the value is safe.** Things like file names from search results are not safe.

```python
# Wrong
await msg.reply_text(f"Adding <b>{title}</b>", parse_mode="HTML")
# Right
await msg.reply_text(f"Adding <b>{_h(title)}</b>", parse_mode="HTML")
```

### Download path parity

The download flow has two halves: an **immediate path** (we got the torrent hash right away from qBT) and a **deferred-hash pending path** (qBT didn't return the hash, so we have a separate async chain that watches for it). Both halves live in `handlers/download.py`. **If a change touches one, it has to touch the other** — otherwise downloads added one way get a feature that downloads added the other way don't. This has bitten us before.

### Restart after every code change

After any change under `telegram-qbt/patchy_bot/`, run `sudo systemctl restart telegram-qbt-bot.service`. The bot does not hot-reload. There's no exception to this — even a one-line tweak needs a restart to actually be live.

### Movies and TV stay in lockstep

Movie Search and TV Search are sibling features. **Any change to one has to be applied to the other**, unless the user explicitly asks for divergence. If you fix a bug in TV result rendering, the same bug almost certainly exists in movie result rendering, and the user expects them to feel identical.

### Never bind qBT to the VPN interface

In qBittorrent's preferences, do not set `current_network_interface` to a VPN interface name (`surfshark_wg`, etc.). It seems like a safety improvement but it actually breaks libtorrent's ability to reach the local DNS resolver, and downloads silently stop working. The VPN is enforced at the OS level via policy routing — qBT doesn't need to know about it. There's a memory note about this and an open task ([[vpn-interface-safety-docs]]) to add a runtime guard.

### No Cancel buttons

Navigation buttons say `↩️ Back` or `🏠 Home`. **Never `Cancel`.** The user has explicitly said "Cancel" feels destructive and they don't want it in the bot UI.

### No ⬜ in the UI

For lists where the user picks items, picked entries get a leading `✅`. **Unselected entries are plain text.** The empty checkbox emoji `⬜` is banned because it renders inconsistently and looks cluttered.

### Subagent-driven development

The user wants every Patchy Bot task delegated to the matching domain subagent (database, schedule, ui, search-download, etc.) rather than implemented inline by the top-level assistant. There's a two-stage review of subagent output before applying anything. The point: keep domain logic concentrated in the agents that own it.

> [!code]- Claude Code Reference
> Quick-scan list of all conventions:
>
> - Runtime code lives in `telegram-qbt/patchy_bot/`
> - `telegram-qbt/qbt_telegram_bot.py` is a back-compat shim — do not edit
> - Restart-safe state → SQLite via `store.py`; transient → in-memory
> - All Telegram messages use HTML parse mode
> - Escape all dynamic message values with `_h()` from `utils.py`
> - Callback data format: colon-delimited `prefix:param1:param2`
> - Selected items: `✅` prefix; unselected: plain text (never `⬜`)
> - Navigation: `↩️ Back` / `🏠 Home` only (never `Cancel`)
> - Inline buttons over text input wherever possible
> - Type hints required on new function signatures
> - Parameterized SQL queries only — no string concat
> - Scoring functions penalize (`score -= N`), do not hard-reject
> - In-memory cache for hot loops; SQLite as restart-safe fallback
> - Use `episode_code(season, episode)` (returns `S01E05`)
> - Use `build_requests_session()` for HTTP clients
> - Use `human_size()`, `now_ts()`
> - EMA variables: init/check related smoothing variables together
> - Files under 500 lines — decompose if growing past
> - WAL mode + `busy_timeout=5000`
> - DB file permissions `0o600`; backup dir `0o700`
> - `QBClient` is thread-safe via `threading.Lock()`; keep scope minimal; never hold across `await`
> - Path containment uses `PurePosixPath.is_relative_to()`, never `str.startswith()`
> - No `os.path.exists()` before `shutil.move()` (TOCTOU race) — use try/except
> - Validate file extensions before moving into Plex library directories
> - Movies/TV feature parity — change both or neither
> - Download immediate-path / deferred-hash pending-path parity (in `handlers/download.py`)
> - Never bind qBT to VPN interface (breaks libtorrent DNS at `127.0.0.1:53`)
> - Restart `telegram-qbt-bot.service` after any change under `patchy_bot/`
> - `pytest -q` in `telegram-qbt/` for touched Python areas
> - Subagent-driven development: delegate per task, two-stage review, no inline
> - Prefer code over docs when they disagree
> - Targeted changes only — no unrelated rewrites
> - No git writes in `Patchy_Bot/` unless explicitly requested
> - No commits of secrets, `.env`, or credentials
> - No saving plans to files — present plans inline only
> - No `type: "prompt"` hooks of any kind (mid-process halts / infinite loops)
> - Never hardcode `model` in Agent tool calls — let `settings.json` route
> - Branding emoji: `🏴‍☠️` (never `🐾`)
