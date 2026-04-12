# Preferences

> Claude Code: update this file when you learn something
> the user likes, dislikes, or wants done a specific way.
> Never remove entries — mark obsolete ones with
> ~~strikethrough~~. Add new entries with a date.

---

## UI / UX Preferences

- **HTML parse mode** for all Telegram messages — never switch to Markdown
- **Escape dynamic values** with `_h(text)` from `utils.py` (wraps `html.escape`)
- **Selected items** use `✅` prefix; unselected items use plain text — never use `⬜`
- **Navigation buttons** use "↩️ Back" or "🏠 Home" — never "Cancel"
- **Inline buttons** for all navigation — never require text input when buttons work
- **Callback data format:** colon-delimited `prefix:param1:param2`
- Branding emoji is `🏴‍☠️` (Patchy the Pirate) — never `🐾`

## Code Style Preferences

- **Type hints required** on all new function signatures
- **Parameterized SQL queries only** — no string concatenation
- **Scoring functions** should penalize (`score -= N`), not hard-reject (`return -9999`) unless it's a clear safety issue
- **In-memory caching** for hot polling loops; SQLite as restart-safe fallback
- Use `episode_code(season, episode)` for episode formatting (returns `S01E05`)
- Use `build_requests_session()` for all HTTP clients (retry/backoff built in)
- Use `human_size()` to format byte counts, `now_ts()` for current Unix timestamp
- **EMA variables:** when using multiple related smoothing variables, initialize and check all together
- **Files under 500 lines** — decompose if growing beyond

## Things I Don't Want

- No `⬜` emoji anywhere in bot UI
- No "Cancel" buttons — always "↩️ Back" or "🏠 Home"
- No `type: "prompt"` hooks — they cause mid-process halts or infinite loops
- No `type: "prompt"` Stop hooks — they create infinite loops
- No git writes in Patchy_Bot unless explicitly asked in the current message
- No commits of secrets, `.env` files, or credentials
- No modifications to `qbt_telegram_bot.py` (backward-compat shim) for runtime changes
- No saving plans to files — present all plans inline in chat only
- No binding qBT to VPN interface — OS policy routing already handles VPN enforcement
- No hardcoding `model` in Agent tool calls — let `settings.json` control model routing
- No inline code implementation — always delegate to domain subagents

## Architecture Preferences

- **Edit `patchy_bot/` package modules** for runtime changes; `qbt_telegram_bot.py` is a shim
- **State that must survive restarts** goes in SQLite via `store.py`; transient state stays in memory
- **Movie/TV feature parity:** any change to Movie Search must also be applied to TV Search and vice versa
- **Download path parity:** if a change touches the immediate path and the deferred-hash pending path, update both
- **WAL mode** with `busy_timeout=5000` — never disable
- **File permissions:** `0o600` for DB files, `0o700` for backup dirs
- **Thread safety:** `QBClient` uses `threading.Lock()` — preserve; keep lock scope minimal
- **Path safety:** use `PurePosixPath.is_relative_to()` for containment — never `str.startswith()`
- **No `os.path.exists()` before `shutil.move()`** — TOCTOU race; use try/except
- **Validate file extensions** before moving into Plex library dirs

## Process Preferences

- **Always restart** `telegram-qbt-bot.service` after any `patchy_bot/` code change
- **Run `pytest -q`** in `telegram-qbt/` for touched Python areas when tests exist
- **Subagent-driven development:** ALL Patchy Bot work must use subagent-driven development — dispatch per task, two-stage review, no inline code
- **Domain subagents first:** delegate to database, schedule, ui, test, security agents instead of handling inline
- **Prefer code over docs** when they disagree
- **Keep changes targeted** — do not rewrite unrelated flows or move files without clear reason
- Subagent prompts capped at ~50 lines

## Learned Preferences

_Claude Code adds new entries here as they are discovered._
