# Patchy Bot Domain Knowledge

Last updated: April 2026. If anything here conflicts with the actual source code, the code is correct.

## Quality Scoring System

Two-layer ranking system for torrent results. Uses the `rank-torrent-name` (RTN) library for parsing.

### Layer 1: Resolution Tier (Primary Sort)
Results are first grouped by resolution:
- Tier 4: 2160p (4K)
- Tier 3: 1080p
- Tier 2: 720p
- Tier 1: 480p
- Tier 0: Unknown

### Layer 2: Format Score (Within Each Tier)

Source Quality: REMUX +100, BluRay +80, WEB-DL +70, WEB-RIP +55, HDTV +35, DVDRIP +15

Codec (resolution-aware — this is a key design decision):
- 4K: HEVC (x265) +80, AVC (x264) +40
- 1080p and below: AVC (x264) +70, HEVC (x265) **-50 penalty** (unnecessary at lower res), XviD -200
- AV1: Hard-reject when av1_reject=True (default)

Audio scoring varies by resolution tier. For 4K: TrueHD+Atmos +100 down to DD 5.1 +40. For 1080p and below: DDP+Atmos +70 down to MP3 +10. DTS-HD and TrueHD get lower scores at 1080p because lossless audio at lower resolution is overkill.

Seed buckets: >=50 seeds +60, >=25 +50, >=10 +40, >=5 +25, >=3 +10, >=1 +2, 0 = hard reject.

Bonuses: PROPER/REPACK +15, Dolby Vision at 4K +25, HDR10 at 4K +20, network stream tag +5, dual/multi audio +10.
Penalties: DV at 1080p -10, hardcoded subs -200.

Release groups: HQ groups (+30) include NTG, FLUX, DON, etc. LQ groups (-500) include YIFY, YTS, EVO, etc. See quality.py for the full lists.

Hard rejections (immediate exclusion): CAM/TS/SCR, upscaled content, AV1 (configurable), zero seeders.

Public API: `score_torrent()`, `quality_label()`, `parse_quality()`, `is_season_pack()`.

### Example Calculation
1080p WEB-DL x264 DDP Atmos from NTG with 30 seeds:
- Source: WEB-DL = +70
- Codec: x264 at 1080p = +70
- Audio: DDP + Atmos at 1080p = +70
- Seeds: 30 (>=25 bucket) = +50
- Group: NTG (HQ) = +30
- Total format score: 290

## Testing Patterns

The project has a 162-test suite. All tests must pass before any PR or deployment.

### Running Tests
```bash
# From the project root, with venv activated:
pytest

# Run specific test file:
pytest tests/test_schedule.py

# Run with verbose output:
pytest -v

# Run specific test:
pytest tests/test_search.py::test_quality_scoring -v
```

### Test Structure
- Tests mirror the handler module structure
- Fixtures provide mock HandlerContext with pre-configured mock clients
- qBT client calls are mocked (never hit real qBT in tests)
- SQLite tests use in-memory databases
- Async tests use pytest-asyncio

### Writing New Tests
- New handler functionality needs tests in the corresponding test file
- Mock external API calls (qBT, Plex, TVMaze, TMDB, LLM) — never make real network calls
- Test both success and error paths
- For callback handlers: test the callback data parsing and the expected Telegram message output

## Common Issues & Debugging Guide

### Telegram API Errors
- **"Message is not modified"**: You're editing a message with the same content. Check that the new content actually differs before calling `edit_message_text`.
- **"Bad Request: message to edit not found"**: The message was deleted or the chat was cleared. Handle this gracefully — don't let it crash the handler.
- **Flood control (429)**: python-telegram-bot handles basic retries, but rapid inline keyboard updates can trigger this. Add small delays between rapid edits.
- **"Conflict: terminated by other getUpdates"**: Two bot instances running simultaneously. Check that only one `telegram-qbt-bot.service` instance is active.

### qBittorrent Issues
- **Connection refused**: qBT service isn't running or the URL is wrong. Check `QBT_BASE_URL` and `systemctl status qbittorrent`.
- **403 after restart**: Cookie expired. QBClient handles re-auth automatically via `_request()`, but if it persists, check credentials.
- **Search returns no results**: qBT search plugins may be disabled or outdated. Use `/plugins` command to check status.
- **Thread safety**: QBClient uses `threading.Lock()`. If you see race conditions, ensure all qBT calls go through QBClient methods (never bypass the lock).

### SQLite Issues
- **"database is locked"**: Another process has a write lock. Check busy_timeout (should be 5000ms). WAL mode should prevent most of these, but long-running writes can still block.
- **Schema changes**: Never modify the schema directly. Add migration logic in store.py that checks for missing columns/tables on startup.

### Plex Issues
- **Library scan doesn't detect new files**: Plex takes time to scan. The completion handler triggers a scan, but large libraries can be slow. Check `PLEX_BASE_URL` and `PLEX_TOKEN`.
- **Episode inventory mismatch**: Plex may have different naming conventions than TVMaze. The fallback matching in `episode_inventory()` handles most cases.

### Schedule System Issues
- **Track not checking on time**: `next_check_at` may be set too far in the future. Check the track's `next_check_at` and `next_air_ts` values.
- **Auto-download not triggering**: Check `auto_state_json` — the state machine may be stuck. Common cause: a previous search returned no results and the state wasn't reset.
- **Metadata source health**: Check `schedule_runner_status.metadata_source_health_json` for TVMaze/TMDB API issues.

### General Debugging Steps
1. Check journalctl: `journalctl -u telegram-qbt-bot.service -f`
2. Look at the JSON log output for structured error context
3. Check SQLite state: `sqlite3 state.sqlite3` and inspect relevant tables
4. For handler issues: trace the callback prefix through the if/elif chain in bot.py
5. For background runner issues: check the runner's last_error_text in the relevant status table
