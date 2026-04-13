# Patchy Bot — Patterns & Conventions (ARCHIVED 2026-04-08)

> **FROZEN ARCHIVE — do not append.** New patterns/conventions/gotchas go in
> the live auto-memory store at `~/.claude/projects/-home-karson-Patchy-Bot/memory/`
> as `feedback_*` entries. See this directory's `MEMORY.md` for the archive
> rationale.

## Entry Format
```
## [YYYY-MM-DD HH:MM] Pattern title
- **Category:** [convention | gotcha | pattern | anti-pattern]
- **Description:** What was discovered
- **Example:** Concrete example if helpful
- **Why it matters:** Impact if ignored
```

---

## [2026-04-07] Never use prompt-type hooks — command hooks only
- **Category:** anti-pattern
- **Description:** Prompt-type PostToolUse hooks halt Claude mid-workflow (any non-"ok" output stops continuation). Prompt-type Stop hooks create infinite loops (every response triggers another Stop event). Use only `type: "command"` hooks.
- **Example:** A prompt hook checking for security keywords triggered on .md files mentioning "auth", stopping work 3+ times per session. A Stop prompt hook caused 100+ loop iterations.
- **Why it matters:** Prompt hooks break the agentic workflow. Command hooks only produce output when real issues are found.

## [2026-04-07] Always HTML-escape dynamic values with _h() for Telegram HTML messages
- **Category:** convention
- **Description:** Any user-controlled or API-returned string inserted into a Telegram message with `parse_mode=HTML` must be wrapped in `_h()` (alias for `html.escape()`). Raw `<`/`>` in release names break rendering.
- **Example:** `_h(row['name'])` not `row['name']` in add-confirmation messages
- **Why it matters:** HTML injection breaks message rendering and could display unintended formatting

## [2026-04-07] Never use os.path.exists() before shutil.move() — TOCTOU race
- **Category:** anti-pattern
- **Description:** `if not os.path.exists(dst): shutil.move(src, dst)` is a TOCTOU race. Another process can create the destination between check and move.
- **Example:** Two completion events processing the same file concurrently caused `shutil.Error`
- **Why it matters:** Use try/except catching FileExistsError instead. Applies to any filesystem operation where target could be created by another process.

## [2026-04-07] Never fuzzy-match torrent names without recency filter
- **Category:** gotcha
- **Description:** Exact hash/name matches are safe at any age, but substring/fuzzy matches must be scoped to recently-added torrents (within ~60 seconds) to avoid attaching to old torrents with similar names.
- **Example:** "Show.S01E01.720p" fuzzy-matched "Show.S01E02.720p" added weeks ago
- **Why it matters:** Progress tracker attaches to wrong download; user sees incorrect progress

## [2026-04-07] Never kill monitors based on transient Telegram API errors
- **Category:** anti-pattern
- **Description:** Telegram API timeouts are transient and self-recover. Do not break out of monitoring loops after N consecutive edit errors.
- **Example:** 5-error streak break stopped progress tracker; download continued invisibly
- **Why it matters:** User loses visibility into active downloads

## [2026-04-07] Never require text input when inline buttons work
- **Category:** anti-pattern
- **Description:** Text input in Telegram bots creates validation burden, leaves garbage messages in chat, and breaks the callback-driven UX pattern. Use inline buttons for all navigation.
- **Example:** Season navigation changed from "type a number" to left/right arrow buttons
- **Why it matters:** Consistent UX; no message cleanup needed; no input validation edge cases

## [2026-04-07] Always validate file extensions before moving into Plex library
- **Category:** convention
- **Description:** Only media files (VIDEO_EXTS for movies, KEEP_EXTS for TV) should land in Plex library directories. Non-media files (.nfo, .txt) cause Plex scanner noise.
- **Why it matters:** Junk files in library dirs pollute Plex's database and scan output

## [2026-04-07] Never use str.startswith() for path containment checks
- **Category:** anti-pattern
- **Description:** `path.startswith(root + os.sep)` fails for paths that are prefixes of other paths. Use `PurePosixPath.is_relative_to()` or `os.path.commonpath()`.
- **Example:** `/media/tv-extra` passes `startswith("/media/tv")` — security vulnerability
- **Why it matters:** Path traversal vulnerability allowing operations outside intended directory

## [2026-04-07] Update BOTH immediate and pending progress tracker paths
- **Category:** gotcha
- **Description:** When adding parameters to a progress tracker code path, always update both the immediate path and the pending (deferred-hash) path in `handlers/download.py`. The pending path is a separate async chain.
- **Example:** `header` and `post_add_rows` were added to immediate path but forgotten in pending path
- **Why it matters:** Pending tracker loses context — shows bare message without summary or keyboard

## [2026-04-07] Initialize all EMA variables as a group
- **Category:** gotcha
- **Description:** When using multiple related EMA smoothing variables (smooth_progress_pct, smooth_dls, smooth_uls), check all of them before using any. They must be initialized together.
- **Why it matters:** Partial initialization causes NoneType crashes in the smoothing calculation

## [2026-04-07] Use in-memory caching for hot polling loops — DB as restart-safe fallback
- **Category:** pattern
- **Description:** Never query the DB in a polling loop for data that doesn't change between ticks. Use an in-memory set/dict with the DB as a safety net after service restart.
- **Example:** `_poller_seen_hashes` set eliminates repeated `is_completion_notified()` DB calls
- **Why it matters:** Prevents unnecessary SQLite load under high completed-torrent counts

## [2026-04-07] Scoring functions should penalize, not hard-reject
- **Category:** pattern
- **Description:** When a downstream feature may need low-quality results as a fallback, use a heavy penalty (e.g., score -= 200) instead of hard rejection (return -9999). This lets the caller decide.
- **Example:** CAM/TS sources changed from hard-reject to -200 penalty for movie scheduling
- **Why it matters:** Hard rejection removes the option for any consumer; penalties preserve choice

## [2026-04-05] Always use project subagents for domain work
- **Category:** convention
- **Description:** Delegate to matching project subagent (database-agent, schedule-agent, ui-agent, etc.) for any task in their domain. Never implement inline, even for "trivial" changes.
- **Why it matters:** User relies on color-coded agent labels to track work; inline implementation bypasses domain expertise

## [2026-04-05] Movie/TV search parity rule
- **Category:** convention
- **Description:** Any feature change to Movie Search must also be applied to TV Search, and vice versa. Check both paths after modifying either.
- **Why it matters:** Users expect consistent behavior across search types

## [2026-04-04] Edit patchy_bot/ package, not the shim
- **Category:** convention
- **Description:** Runtime changes go in `patchy_bot/` package modules. `qbt_telegram_bot.py` is a backward-compat shim that re-exports from the package.
- **Why it matters:** Edits to the shim are ignored at runtime; service runs `python -m patchy_bot`

## [2026-04-03] No git in Patchy_Bot
- **Category:** convention
- **Description:** No git commands, commits, or branches in ~/Patchy_Bot. Edit files directly and restart service.
- **Why it matters:** Git reset incident on 2026-04-03 caused production downtime with lost uncommitted work

## [2026-04-05] Never use ⬜ in bot UI
- **Category:** convention
- **Description:** For toggle/selection UIs, show `✅` on selected items and plain text (no prefix) on unselected items. Never use the `⬜` character.
- **Why it matters:** User explicitly requested its removal

## [2026-04-05] Always restart service after patchy_bot/ changes
- **Category:** convention
- **Description:** Run `sudo systemctl restart telegram-qbt-bot.service` after any file edit under `telegram-qbt/patchy_bot/`.
- **Why it matters:** Changes don't take effect until service restarts

## [2026-04-05] Never hardcode model in Agent tool calls
- **Category:** convention
- **Description:** Omit the `model` parameter in Agent tool calls. Global `~/.claude/settings.json` controls the subagent model. Hardcoding overrides the user's preference.
- **Why it matters:** User wants all subagents on claude-sonnet-4-6; explicit model param bypasses that

## [2026-04-04] No plan files — inline only
- **Category:** convention
- **Description:** Never save plans to files. Present all plans directly in chat conversation.
- **Why it matters:** User's explicit project rule; plan files are not wanted

## [2026-04-07] Never bind qBT to VPN interface
- **Category:** anti-pattern
- **Description:** Never set `current_network_interface` in qBT preferences to the VPN interface. OS-level Surfshark kill-switch (ip rule 31565 → routing table 300000) handles VPN routing. Interface binding breaks libtorrent DNS (can't reach 127.0.0.1:53).
- **Example:** Setting `surfshark_wg` caused all trackers to fail with "Host not found (authoritative)"
- **Why it matters:** All downloads stall at "getting metadata" with 0 peers

## [2026-04-06] Network topology reference
- **Category:** reference
- **Description:** DaWiFi_2.0 = ASUS RT-BE92U (192.168.50.0/24); ATT modem (192.168.1.0/24); Server at 192.168.50.40, Tailscale at 100.126.69.89. Plex access: LAN direct, ATT via port forward at 192.168.1.189:32400, remote via Tailscale (no Plex Remote Access).
- **Why it matters:** Context for network debugging, Plex connectivity issues, VPN configuration
