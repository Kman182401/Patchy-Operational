# Patchy Bot — Bugs Log (ARCHIVED 2026-04-08)

> **FROZEN ARCHIVE — do not append.** New bug forensics go in the live
> auto-memory store at `~/.claude/projects/-home-karson-Patchy-Bot/memory/`
> as `bugs_YYYY-MM-DD.md` entries. See this directory's `MEMORY.md` for
> the archive rationale.

## Entry Format
```
## [YYYY-MM-DD HH:MM] Brief bug title
- **Symptom:** What was observed / reported
- **Root cause:** Why it happened
- **Fix:** What was changed to resolve it
- **Files changed:** List of files
- **Verification:** How to confirm the fix works
```

---

## [2026-04-07] User's typed show-name not cleaned up from chat
- **Symptom:** When user typed a show name in schedule flow, the message stayed cluttering chat
- **Root cause:** No cleanup call after search-results render
- **Fix:** Added `_cleanup_private_user_message(msg)` after both initial and re-search renders
- **Files changed:** `patchy_bot/bot.py`
- **Verification:** Type a show name in schedule flow — message should disappear after results appear

## [2026-04-07] Schedule menu labels vague, movie button always shown
- **Symptom:** "My Shows" label was vague; single "Movies" button shown even with no tracked movies
- **Root cause:** No conditional rendering based on tracked movie count
- **Fix:** Renamed to "Active Tracking" with count; split movie button into "Add New Movie" + "My Movies (N)" when tracks exist
- **Files changed:** `patchy_bot/handlers/commands.py`
- **Verification:** Open schedule menu with and without tracked movies — buttons should adapt

## [2026-04-07] HTML injection via unescaped torrent names in add-confirmation
- **Symptom:** Torrent names with `<group>` tags broke Telegram HTML rendering
- **Root cause:** `do_add()` used raw `row['name']` without HTML-escaping in parse_mode=HTML message
- **Fix:** Wrapped all dynamic values in `_h()` (html.escape)
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Add a torrent with `<` or `>` in the name — should render as text, not HTML tags

## [2026-04-07] Pending progress tracker lost header and keyboard after hash resolved
- **Symptom:** Pending tracker showed bare "Live Monitor Attached" without summary or post-add keyboard
- **Root cause:** `start_pending_progress_tracker()` didn't accept/forward `header` or `post_add_rows` params
- **Fix:** Added `header` and `post_add_rows` kwargs through full chain: bot.py → pending tracker functions
- **Files changed:** `patchy_bot/bot.py`, `patchy_bot/handlers/download.py`
- **Verification:** Add a torrent where hash isn't immediately available — tracker should show full summary

## [2026-04-07] Pending tracker timeout gave no user notification
- **Symptom:** When `resolve_hash_by_name()` failed after 35s, user saw nothing — no tracker, no explanation
- **Root cause:** Timeout path returned silently with no message
- **Fix:** Added user notification ("Monitor Could Not Attach") and health event logging on timeout
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Simulate a hash resolution failure — user should see timeout message

## [2026-04-07] Progress tracker died after 5 consecutive Telegram edit errors
- **Symptom:** Tracker stopped updating with "Monitor Paused" after 5 API timeouts; download continued invisibly
- **Root cause:** `edit_error_streak >= 5` break was too aggressive for transient timeouts
- **Fix:** Removed the 5-error break entirely — Telegram's own rate limiting handles recovery
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Tracker should continue through API timeouts without stopping

## [2026-04-07] Stalled torrents had no automatic recovery — user told to manually cancel
- **Symptom:** Metadata-stuck torrents required manual intervention
- **Root cause:** Stall warning only informed user; no automatic action taken
- **Fix:** `track_download_progress()` now calls `qbt.reannounce_torrent()` when stall warning fires
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Stall warning message should mention reannounce was attempted

## [2026-04-07] Path safety used string startswith instead of proper path containment
- **Symptom:** Theoretical path traversal — `/media/tv-extra` would pass `startswith("/media/tv")` check
- **Root cause:** `str.startswith()` doesn't handle path boundaries correctly
- **Fix:** Replaced with `PurePosixPath.is_relative_to()` check
- **Files changed:** `patchy_bot/plex_organizer.py`
- **Verification:** `grep -n "startswith.*os.sep" patchy_bot/plex_organizer.py` should return zero results

## [2026-04-07] Plex organizer accepted non-media files (.nfo, .txt, etc.)
- **Symptom:** Junk files from torrent downloads moved into Plex library folders
- **Root cause:** No extension checks in organize_tv() single-file path or organize_movie()
- **Fix:** Added extension checks against KEEP_EXTS / VIDEO_EXTS; directory downloads verify video file exists
- **Files changed:** `patchy_bot/plex_organizer.py`
- **Verification:** Download with .nfo files — only media files should end up in Plex library

## [2026-04-07] Plex organizer TOCTOU race on file existence check
- **Symptom:** Intermittent `shutil.Error` when two completion events processed same file concurrently
- **Root cause:** `if not os.path.exists(dst): shutil.move(...)` — classic TOCTOU race
- **Fix:** Replaced with try/except catching FileExistsError and shutil.Error("already exists")
- **Files changed:** `patchy_bot/plex_organizer.py`
- **Verification:** `grep -n "os.path.exists.*shutil.move" patchy_bot/plex_organizer.py` should return zero

## [2026-04-07] Progress tracker crashed on NoneType when smooth_dls/smooth_uls were None
- **Symptom:** Tracker silently died with TypeError computing EMA smoothing
- **Root cause:** Guard only checked `smooth_progress_pct is None`, not `smooth_dls` or `smooth_uls`
- **Fix:** Changed guard to check all three smoothing variables
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Ensure all smooth_* variables checked in guard condition

## [2026-04-07] resolve_hash_by_name matched old torrents with similar names
- **Symptom:** Progress tracker attached to wrong (old) torrent with partially matching name
- **Root cause:** Fuzzy matching (Priority 3-4) had no recency filter
- **Fix:** Added `is_recent` check — fuzzy matches require torrent added within last 60 seconds
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Add a torrent with name similar to an old one — should track the new one

## [2026-04-07] Completion poller hammered DB for every already-seen torrent
- **Symptom:** 60s poller re-queried every completed hash against DB on every tick
- **Root cause:** No in-memory dedup; no recency filter
- **Fix:** Added `_poller_seen_hashes` in-memory cache + 24h recency filter
- **Files changed:** `patchy_bot/handlers/download.py`
- **Verification:** Enable SQLite query logging; watch for repeated `is_completion_notified` calls

## [2026-04-07] qBT health check didn't detect "firewalled" status — only "unreachable"
- **Symptom:** qBT reported firewalled after VPN reconnect; torrents stalled with no peers
- **Root cause:** Health check only caught exceptions (unreachable), not firewalled connection_status
- **Fix:** Health check now inspects `connection_status` from `get_transfer_info()`; auto-clears stale interface binding
- **Files changed:** `patchy_bot/bot.py`
- **Verification:** `journalctl -u telegram-qbt-bot.service | grep "firewalled"` — auto-clear should follow
