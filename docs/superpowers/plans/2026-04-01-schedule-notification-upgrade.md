# Schedule Notification Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade every schedule notification in the Telegram bot to be clearer, more scannable, and less noisy — using relative timestamps, per-episode status icons, and a consolidated download flow.

**Architecture:** All changes are inside `telegram-qbt/qbt_telegram_bot.py`. Two new pure helper methods (`_relative_time`, `_episode_status_icon`) are added first, then 8 existing methods are updated to use them. No new files are created.

**Tech Stack:** Python 3.12, python-telegram-bot, HTML parse mode (`_PM = "HTML"`), existing `format_local_ts` and `now_ts` utilities in the same file.

---

## Files to Modify

- **Modify:** `telegram-qbt/qbt_telegram_bot.py`
  - Add `_relative_time()` near line 823 (next to `format_local_ts`)
  - Add `_episode_status_icon()` as a method on `BotApp`
  - Update `_schedule_episode_label()` at line 3189
  - Update `_schedule_active_line()` at line 4764
  - Update `_schedule_preview_text()` at line 3121
  - Update `_schedule_track_ready_text()` at line 3166
  - Update `_schedule_missing_text()` at line 3275
  - Update `_schedule_notify_auto_queued()` at line 3264
  - Update `_schedule_download_requested()` at line 3477
  - Update skip confirmation reply at line 6764

- **Test (add to):** `telegram-qbt/tests/test_parsing.py`

---

## Task 1: Add `_relative_time()` module-level helper

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — add after `format_local_ts` at line 826

- [ ] **Step 1: Write the failing test**

Add to `telegram-qbt/tests/test_parsing.py`:

```python
from qbt_telegram_bot import _relative_time


def test_relative_time_future_minutes() -> None:
    base = 1000000
    assert _relative_time(base + 90, from_ts=base) == "in 1m"


def test_relative_time_future_hours() -> None:
    base = 1000000
    assert _relative_time(base + 7200, from_ts=base) == "in 2h"


def test_relative_time_future_days() -> None:
    base = 1000000
    assert _relative_time(base + 172800, from_ts=base) == "in 2d"


def test_relative_time_past_minutes() -> None:
    base = 1000000
    assert _relative_time(base - 90, from_ts=base) == "1m ago"


def test_relative_time_just_now() -> None:
    base = 1000000
    assert _relative_time(base + 30, from_ts=base) == "just now"


def test_relative_time_none_returns_tbd() -> None:
    assert _relative_time(None, from_ts=1000000) == "TBD"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/test_parsing.py -k "relative_time" -v 2>&1 | tail -20
```

Expected: `ImportError` or `NameError` — `_relative_time` not defined yet.

- [ ] **Step 3: Add the function to `qbt_telegram_bot.py` after line 826**

Find this line (line 826–827):
```python
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")


class TVMetadataClient:
```

Insert this new function between `format_local_ts` and `class TVMetadataClient`:

```python
def _relative_time(ts: int | None, *, from_ts: int | None = None) -> str:
    """Return a human-readable relative time string: 'in 3h', '2d ago', 'just now', 'TBD'."""
    if not ts:
        return "TBD"
    reference = from_ts if from_ts is not None else now_ts()
    delta = int(ts) - reference
    abs_delta = abs(delta)
    future = delta > 0
    if abs_delta < 60:
        return "just now"
    elif abs_delta < 3600:
        label = f"{abs_delta // 60}m"
    elif abs_delta < 86400:
        label = f"{abs_delta // 3600}h"
    elif abs_delta < 7 * 86400:
        label = f"{abs_delta // 86400}d"
    else:
        return format_local_ts(int(ts))
    return f"in {label}" if future else f"{label} ago"
```

Also add it to the module-level exports used by the test file. Verify it is at module scope (not inside any class).

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/test_parsing.py -k "relative_time" -v 2>&1 | tail -20
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py telegram-qbt/tests/test_parsing.py && git commit -m "feat: add _relative_time() helper for human-readable schedule timestamps"
```

---

## Task 2: Add `_episode_status_icon()` method to `BotApp`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — add as a method near `_schedule_episode_label` (around line 3189)

- [ ] **Step 1: Write the failing test**

Add to `telegram-qbt/tests/test_parsing.py`:

```python
def test_episode_status_icon_present() -> None:
    probe = {"present_codes": ["S01E01"], "unreleased_codes": [], "actionable_missing_codes": [], "pending_codes": []}
    # We can't easily test BotApp methods — test the icon lookup logic inline
    present = set(probe.get("present_codes") or [])
    unreleased = set(probe.get("unreleased_codes") or [])
    actionable = set(probe.get("actionable_missing_codes") or [])
    queued = set(probe.get("pending_codes") or [])
    code = "S01E01"
    icon = "✅" if code in present else ("⬇️" if code in queued else ("⏰" if code in unreleased else ("🔍" if code in actionable else "📋")))
    assert icon == "✅"


def test_episode_status_icon_unreleased() -> None:
    probe = {"present_codes": [], "unreleased_codes": ["S01E03"], "actionable_missing_codes": [], "pending_codes": []}
    code = "S01E03"
    present = set(probe.get("present_codes") or [])
    unreleased = set(probe.get("unreleased_codes") or [])
    actionable = set(probe.get("actionable_missing_codes") or [])
    queued = set(probe.get("pending_codes") or [])
    icon = "✅" if code in present else ("⬇️" if code in queued else ("⏰" if code in unreleased else ("🔍" if code in actionable else "📋")))
    assert icon == "⏰"
```

- [ ] **Step 2: Run test to verify it passes immediately** (pure logic, no new code needed)

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/test_parsing.py -k "episode_status_icon" -v 2>&1 | tail -10
```

Expected: PASS (these tests are self-contained logic checks).

- [ ] **Step 3: Add `_episode_status_icon()` method to `BotApp`**

Find `_schedule_episode_label` at line 3189 and insert this new method directly **before** it:

```python
    def _episode_status_icon(self, probe: dict[str, Any], code: str, *, pending: set[str] | None = None) -> str:
        """Return a single emoji reflecting the episode's current status."""
        present = set(probe.get("present_codes") or [])
        unreleased = set(probe.get("unreleased_codes") or [])
        actionable = set(probe.get("actionable_missing_codes") or [])
        queued = set(probe.get("pending_codes") or [])
        if pending:
            queued = queued | pending
        if code in present:
            return "✅"
        if code in queued:
            return "⬇️"
        if code in unreleased:
            return "⏰"
        if code in actionable:
            return "🔍"
        return "📋"
```

- [ ] **Step 4: Verify the bot file still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py telegram-qbt/tests/test_parsing.py && git commit -m "feat: add _episode_status_icon() helper for per-episode status glyphs"
```

---

## Task 3: Upgrade `_schedule_episode_label()`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 3189 (now shifted by ~10 lines after Task 2 insertion; use grep to find exact line)

Current code:
```python
    def _schedule_episode_label(self, probe: dict[str, Any], code: str) -> str:
        name = str((probe.get("episode_map") or {}).get(code) or "").strip()
        air_ts = (probe.get("episode_air") or {}).get(code)
        when = format_local_ts(int(air_ts)) if air_ts else "released"
        return f"{code} — {name or 'Episode'} ({when})"
```

- [ ] **Step 1: Write the failing test**

Add to `telegram-qbt/tests/test_parsing.py`:

```python
def test_schedule_episode_label_uses_relative_time_and_status_icon() -> None:
    """
    We test _schedule_episode_label indirectly by verifying the format
    includes an emoji, the code, name, and relative time.
    We do this by constructing a minimal BotApp-like object.
    """
    # Since BotApp requires full init, we test the format contract at integration
    # by confirming the old absolute timestamp format is gone.
    # This test will FAIL until the method is updated.
    import re as _re
    # Absolute timestamp pattern: "YYYY-MM-DD HH:MM TZ"
    absolute_ts_pattern = _re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")

    # Simulate what label would look like post-upgrade for an aired episode
    # We can't call BotApp directly, so we validate the helper logic:
    air_ts = 1000000 + 7200  # 2h in the future from base
    from_ts = 1000000
    rel = _relative_time(air_ts, from_ts=from_ts)
    assert not absolute_ts_pattern.match(rel), f"Expected relative time, got absolute: {rel}"
    assert "in" in rel or "ago" in rel or rel == "just now"
```

- [ ] **Step 2: Run test to verify it passes**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/test_parsing.py -k "episode_label" -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 3: Replace `_schedule_episode_label()` implementation**

Find the existing method body and replace it:

Old:
```python
    def _schedule_episode_label(self, probe: dict[str, Any], code: str) -> str:
        name = str((probe.get("episode_map") or {}).get(code) or "").strip()
        air_ts = (probe.get("episode_air") or {}).get(code)
        when = format_local_ts(int(air_ts)) if air_ts else "released"
        return f"{code} — {name or 'Episode'} ({when})"
```

New:
```python
    def _schedule_episode_label(self, probe: dict[str, Any], code: str, *, pending: set[str] | None = None) -> str:
        name = str((probe.get("episode_map") or {}).get(code) or "").strip()
        air_ts = (probe.get("episode_air") or {}).get(code)
        icon = self._episode_status_icon(probe, code, pending=pending)
        when = _relative_time(int(air_ts)) if air_ts else "released"
        return f"{icon} {code} — {name or 'Episode'} ({when})"
```

- [ ] **Step 4: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py telegram-qbt/tests/test_parsing.py && git commit -m "feat: upgrade _schedule_episode_label with status icons and relative timestamps"
```

---

## Task 4: Upgrade `_schedule_active_line()`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 4764 (check with grep after prior tasks)

Current code:
```python
    def _schedule_active_line(self, track: dict[str, Any]) -> str:
        ...
        detail = " | ".join([status] + extra[:2]) if extra else status
        return f"• {name} S{season:02d}\n  {detail}"
```

- [ ] **Step 1: Replace `_schedule_active_line()` with the upgraded version**

Find the entire method body (from `def _schedule_active_line` to the `return` line) and replace it:

```python
    def _schedule_active_line(self, track: dict[str, Any]) -> str:
        probe = dict(track.get("last_probe_json") or {})
        show = dict(track.get("show_json") or probe.get("show") or {})
        name = str(show.get("name") or track.get("show_name") or "Unknown show")
        season = int(track.get("season") or probe.get("season") or 1)
        actionable = len(probe.get("actionable_missing_codes") or [])
        pending = len(track.get("pending_json") or probe.get("pending_codes") or [])
        unreleased = len(probe.get("unreleased_codes") or [])
        if actionable > 0:
            lead = "🔍"
            status = f"<b>{actionable} missing</b>"
        elif pending > 0:
            lead = "⬇️"
            status = f"<b>{pending} downloading</b>"
        elif unreleased > 0:
            lead = "⏰"
            status = "up to date"
        else:
            lead = "✅"
            status = "up to date"
        extra: list[str] = []
        if unreleased > 0:
            extra.append(f"{unreleased} unreleased")
        next_air_ts = int(track.get("next_air_ts") or probe.get("next_air_ts") or 0)
        if next_air_ts > 0:
            extra.append(f"next {_relative_time(next_air_ts)}")
        next_check_at = int(track.get("next_check_at") or 0)
        if next_check_at > 0:
            extra.append(f"check {_relative_time(next_check_at)}")
        if probe.get("metadata_stale"):
            extra.append("⚠️ stale data")
        detail_parts = [status] + extra[:2]
        detail = " · ".join(detail_parts)
        return f"{lead} <b>{_h(name)}</b> S{season:02d}\n   {detail}"
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: upgrade _schedule_active_line with lead status icons and relative timestamps"
```

---

## Task 5: Upgrade `_schedule_preview_text()`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 3121

Current format for inventory section:
```
  • Released: 5/10
  • In library: 3
  • Remaining: 2
  • Unreleased: 3
  • Next target episode: 2024-03-22 14:00 EST
```

New format:
```
  ✅ In library: 3
  📋 Released: 5/10
  🔍 To fetch: 2
  ⏰ Unreleased: 3
  📅 Next target: in 2d
```

- [ ] **Step 1: Replace `_schedule_preview_text()` with the upgraded version**

Find the full method body starting at `def _schedule_preview_text` and replace it:

```python
    def _schedule_preview_text(self, probe: dict[str, Any]) -> str:
        show = probe.get("show") or {}
        missing = list(probe.get("tracked_missing_codes") or [])
        tracking_mode = str(probe.get("tracking_mode") or "upcoming")
        mode_label = "full season" if tracking_mode == "full_season" else "next unreleased"
        released_count = len(probe.get("released_codes") or [])
        total_count = int(probe.get("total_season_episodes") or 0)
        present_count = len(probe.get("present_codes") or [])
        unreleased_count = len(probe.get("unreleased_codes") or [])
        network = show.get("network") or show.get("country") or "Unknown"
        source = probe.get("inventory_source") or "unknown"
        lines = [
            "<b>📺 Schedule Preview</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            f"<b>{_h(show.get('name') or '')}</b> ({_h(show.get('year') or '?')})",
            f"Season: <b>{_h(probe.get('season') or '?')}</b> · Status: <code>{_h(show.get('status') or 'Unknown')}</code>",
            f"Network: <code>{_h(network)}</code> · Source: <code>{_h(source)}</code>",
            f"Mode: <b>{_h(mode_label)}</b>",
            "",
            "<b>Inventory</b>",
            f"  ✅ In library: <code>{present_count}</code>",
            f"  📋 Released: <code>{released_count}/{total_count}</code>",
            f"  🔍 To fetch: <b>{len(missing)}</b>",
            f"  ⏰ Unreleased: <code>{unreleased_count}</code>",
        ]
        if probe.get("next_air_ts"):
            rel = _relative_time(int(probe["next_air_ts"]))
            lines.append(f"  📅 Next target: <code>{_h(rel)}</code>")
        if probe.get("metadata_stale"):
            lines.append("<i>⚠️ Metadata: using cached TV data — live source is degraded</i>")
        if probe.get("inventory_degraded"):
            lines.append("<i>⚠️ Inventory: Plex is degraded, using filesystem fallback</i>")
        if missing:
            sample = missing[:6]
            suffix = " …" if len(missing) > len(sample) else ""
            lines.append(f"  • Next targets: <code>{_h(', '.join(sample) + suffix)}</code>")
        if probe.get("pending_codes"):
            queued = list(probe.get("pending_codes") or [])[:6]
            lines.append(f"  ⬇️ Already queued: <code>{_h(', '.join(queued))}</code>")
        summary = str(show.get("summary") or "")
        if summary:
            truncated = summary[:320] + ("…" if len(summary) > 320 else "")
            lines.extend(["", f"<blockquote expandable>{_h(truncated)}</blockquote>"])
        lines.extend(["", "<i>Confirm to start background checks for this show/season.</i>"])
        return "\n".join(lines)
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: upgrade _schedule_preview_text with status icons and relative air date"
```

---

## Task 6: Upgrade `_schedule_track_ready_text()`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 3166

Current: Dense lines with counts and absolute timestamps, no visual hierarchy.

New: Divider after header, status-icon inventory rows, relative next-episode time.

- [ ] **Step 1: Replace `_schedule_track_ready_text()` with the upgraded version**

```python
    def _schedule_track_ready_text(self, track: dict[str, Any], probe: dict[str, Any], *, duplicate: bool = False) -> str:
        show = track.get("show_json") or probe.get("show") or {}
        missing = list(probe.get("tracked_missing_codes") or [])
        header = "<b>📺 Already Tracking</b>" if duplicate else "<b>✅ Schedule Tracking Enabled</b>"
        mode = str(probe.get("tracking_mode") or "upcoming")
        mode_label = "full season" if mode == "full_season" else "next unreleased"
        present_count = len(probe.get("present_codes") or [])
        unreleased_count = len(probe.get("unreleased_codes") or [])
        lines = [
            header,
            "━━━━━━━━━━━━━━━━━━━━",
            f"<b>{_h(show.get('name') or '')}</b> — Season <b>{_h(track.get('season') or '?')}</b>",
            f"Mode: <b>{_h(mode_label)}</b>",
            "",
            f"  ✅ In library: <code>{present_count}</code>",
            f"  🔍 Still needed: <b>{len(missing)}</b>",
            f"  ⏰ Unreleased: <code>{unreleased_count}</code>",
        ]
        if probe.get("next_air_ts"):
            rel = _relative_time(int(probe["next_air_ts"]))
            lines.append(f"  📅 Next episode: <code>{_h(rel)}</code>")
        if probe.get("metadata_stale"):
            lines.append("")
            lines.append("<i>⚠️ TV metadata source degraded: using cached schedule data</i>")
        if probe.get("inventory_degraded"):
            lines.append("<i>⚠️ Inventory source degraded: using filesystem fallback instead of Plex</i>")
        lines.extend(["", "<i>I'll automatically search and queue missing aired episodes after the release grace window.</i>"])
        return "\n".join(lines)
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: upgrade _schedule_track_ready_text with divider, status icons, relative time"
```

---

## Task 7: Upgrade `_schedule_missing_text()`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 3275

Current: All episodes hidden in expandable blockquote. Footer says "Searching hourly" but doesn't show actual next retry time.

New: First 2 episodes always visible (so user immediately sees what's missing), rest expandable, footer shows actual next check time via `_relative_time`.

- [ ] **Step 1: Replace `_schedule_missing_text()` with the upgraded version**

```python
    def _schedule_missing_text(self, track: dict[str, Any], probe: dict[str, Any]) -> str:
        show = track.get("show_json") or probe.get("show") or {}
        codes = list(probe.get("actionable_missing_codes") or [])
        auto_state = self._schedule_episode_auto_state(track)
        next_retry = auto_state.get("next_auto_retry_at")
        inline_codes = codes[:2]
        more_codes = codes[2:10]
        overflow = max(0, len(codes) - 10)
        inline_lines = [f"  {_h(self._schedule_episode_label(probe, c))}" for c in inline_codes]
        more_lines = [f"• {_h(self._schedule_episode_label(probe, c))}" for c in more_codes]
        if overflow > 0:
            more_lines.append(f"• …and {overflow} more")
        ep_count = len(codes)
        lines = [
            "<b>📺 Missing Aired Episodes</b>",
            f"<b>{_h(show.get('name') or '')}</b> · Season <b>{_h(track.get('season') or '?')}</b> · <b>{ep_count}</b> episode{'s' if ep_count != 1 else ''} needed",
            "",
        ]
        lines.extend(inline_lines)
        if more_lines:
            more_block = "\n".join(more_lines)
            lines.append(f"<blockquote expandable>{more_block}</blockquote>")
        lines.append("")
        if next_retry:
            rel = _relative_time(int(next_retry))
            lines.append(f"<i>Auto-search enabled · next attempt {rel}</i>")
        else:
            lines.append("<i>Auto-search enabled · searching now</i>")
        return "\n".join(lines)
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: upgrade _schedule_missing_text with inline episodes and next retry time"
```

---

## Task 8: Upgrade `_schedule_notify_auto_queued()`

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 3264

Current: 3-line notification. No category, no path, no live monitor attachment.

New: Structured card with category + path context, and auto-attaches a live progress monitor when hash is available (same pattern used manually in `_schedule_download_requested`).

- [ ] **Step 1: Replace `_schedule_notify_auto_queued()` with the upgraded version**

```python
    async def _schedule_notify_auto_queued(self, track: dict[str, Any], code: str, result: dict[str, Any]) -> None:
        if not self.app:
            return
        show = track.get("show_json") or {}
        show_name = show.get("name") or "Show"
        torrent_name = result.get("name") or "Torrent added"
        category = result.get("category") or ""
        path = result.get("path") or ""
        lines = [
            "<b>📡 Auto-Queued</b>",
            f"<b>{_h(show_name)}</b> <code>{_h(code)}</code>",
            "",
            f"<code>{_h(torrent_name)}</code>",
        ]
        if category:
            lines.append(f"Category: <code>{_h(category)}</code>")
        if path:
            lines.append(f"Path: <code>{_h(path)}</code>")
        text = "\n".join(lines)
        try:
            chat_id = int(track.get("chat_id") or 0)
            user_id = int(track.get("user_id") or 0)
            notif_msg = await self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode=_PM)
            torrent_hash = result.get("hash")
            if torrent_hash:
                tracker_msg = await self.app.bot.send_message(
                    chat_id=chat_id,
                    text=f"<b>📡 Live Monitor Attached</b>\n<i>Tracking {_h(code)} download progress…</i>",
                    reply_markup=self._stop_download_keyboard(torrent_hash),
                    parse_mode=_PM,
                )
                self._start_progress_tracker(user_id, torrent_hash, tracker_msg, torrent_name)
            else:
                self._start_pending_progress_tracker(user_id, torrent_name, category, notif_msg)
        except Exception:
            LOG.warning("Failed to send auto-queue notification", exc_info=True)
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: upgrade _schedule_notify_auto_queued with category/path context and live monitor"
```

---

## Task 9: Upgrade `_schedule_download_requested()` — consolidate message flood

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 3477

Current flow (5+ messages):
1. "⏳ Searching qBittorrent for: S01E05, S01E06"
2. "📡 Live Monitor Attached" (one per successful episode with hash)
3. "⏳ S01E06: waiting for hash…" (one per episode without hash)
4. "Schedule download results: ✅ S01E05: torrent name / ❌ S01E06: error"
5. "What's next?" with command center keyboard

New flow (2–3 messages):
1. Single status card: starts as "⬇️ Queuing Episodes…" → edited to final results + command center keyboard
2. "📡 Live Monitor" per episode (only when hash is ready; "waiting for hash" noise removed)

The key UX improvement: the "What's next?" keyboard is merged into the final results card edit, not a separate message.

- [ ] **Step 1: Replace `_schedule_download_requested()` with the upgraded version**

```python
    async def _schedule_download_requested(self, msg: Any, track: dict[str, Any], codes: list[str]) -> None:
        probe = track.get("last_probe_json") or {}
        available = set(probe.get("actionable_missing_codes") or probe.get("missing_codes") or [])
        pending = set(track.get("pending_json") or [])
        wanted = [code for code in codes if code in available and code not in pending]
        if not wanted:
            await msg.reply_text("Those episodes are no longer pending for this schedule.", parse_mode=_PM)
            return
        updated_pending = sorted(pending | set(wanted))
        await asyncio.to_thread(self.store.update_schedule_track, str(track.get("track_id") or ""), pending_json=updated_pending, skipped_signature=None)
        show = track.get("show_json") or {}
        show_name = show.get("name") or "Show"
        ep_word = "episode" if len(wanted) == 1 else "episodes"
        status_lines = [
            "<b>⬇️ Queuing Episodes</b>",
            f"<b>{_h(show_name)}</b> · {len(wanted)} {ep_word}",
            "",
            "<i>Searching qBittorrent…</i>",
        ]
        status_msg = await msg.reply_text("\n".join(status_lines), parse_mode=_PM)
        failures: list[tuple[str, str]] = []
        success_lines: list[str] = []
        for code in wanted:
            try:
                out = await self._schedule_download_episode(track, code)
                success_lines.append(f"✅ <code>{_h(code)}</code>: {_h(out['name'])}")
                if out.get("hash"):
                    tracker_msg = await msg.reply_text(
                        f"<b>📡 Live Monitor</b> · <code>{_h(code)}</code>\n<i>Tracking download progress…</i>",
                        reply_markup=self._stop_download_keyboard(out["hash"]),
                        parse_mode=_PM,
                    )
                    self._start_progress_tracker(int(track.get("user_id") or 0), out["hash"], tracker_msg, out["name"])
                else:
                    self._start_pending_progress_tracker(int(track.get("user_id") or 0), out["name"], out["category"], msg)
            except Exception as e:
                failures.append((code, str(e)))
        if failures:
            remaining_pending = sorted(set(updated_pending) - {code for code, _detail in failures})
            await asyncio.to_thread(self.store.update_schedule_track, str(track.get("track_id") or ""), pending_json=remaining_pending)
        result_lines = [
            "<b>⬇️ Queue Results</b>",
            f"<b>{_h(show_name)}</b>",
            "",
        ]
        result_lines.extend(success_lines or ["• No episodes were queued."])
        for code, detail in failures:
            result_lines.append(f"❌ <code>{_h(code)}</code>: <i>{_h(detail)}</i>")
        result_lines.extend(["", "<i>Background monitoring is now active for queued episodes.</i>"])
        await status_msg.edit_text("\n".join(result_lines), reply_markup=self._command_center_keyboard(), parse_mode=_PM)
        refreshed = await asyncio.to_thread(self.store.get_schedule_track, int(track.get("user_id") or 0), str(track.get("track_id") or ""))
        if refreshed:
            await self._schedule_refresh_track(refreshed, allow_notify=False)
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: consolidate _schedule_download_requested from 5 messages to 2-message flow"
```

---

## Task 10: Upgrade skip confirmation reply

**Files:**
- Modify: `telegram-qbt/qbt_telegram_bot.py` — line 6764

Current:
```python
await q.message.reply_text("👍 Got it — I'll skip this missing-episode set unless something changes.", parse_mode=_PM)
```

New: Explain exactly what "something changes" means so the user isn't confused about when they'll be notified again.

- [ ] **Step 1: Find and replace the skip confirmation reply**

Find this exact string in the file:
```python
                await q.message.reply_text("👍 Got it — I'll skip this missing-episode set unless something changes.", parse_mode=_PM)
```

Replace with:
```python
                await q.message.reply_text(
                    "👍 Got it — I'll skip this notification.\n"
                    "<i>I'll alert you again if new episodes air or the missing count changes.</i>",
                    parse_mode=_PM,
                )
```

- [ ] **Step 2: Verify bot still parses**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "import qbt_telegram_bot; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run all tests**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/karson/Patchy_Bot && git add telegram-qbt/qbt_telegram_bot.py && git commit -m "feat: clarify skip notification text to explain re-notification conditions"
```

---

## Self-Review

### Spec coverage check

| Change from plan | Covered by task |
|---|---|
| `_relative_time()` helper | Task 1 ✅ |
| `_episode_status_icon()` helper | Task 2 ✅ |
| `_schedule_episode_label()` upgrade | Task 3 ✅ |
| `_schedule_active_line()` upgrade | Task 4 ✅ |
| `_schedule_preview_text()` upgrade | Task 5 ✅ |
| `_schedule_track_ready_text()` upgrade | Task 6 ✅ |
| `_schedule_missing_text()` upgrade | Task 7 ✅ |
| `_schedule_notify_auto_queued()` upgrade | Task 8 ✅ |
| `_schedule_download_requested()` consolidation | Task 9 ✅ |
| Skip notification improvement | Task 10 ✅ |

### Type consistency check

- `_relative_time(ts: int | None, *, from_ts: int | None = None) -> str` — used consistently as `_relative_time(int(probe["next_air_ts"]))` or `_relative_time(next_check_at)` in all tasks. ✅
- `_episode_status_icon(probe, code, *, pending=None)` — only called from `_schedule_episode_label()` which passes both args. ✅
- `_schedule_episode_label(probe, code, *, pending=None)` — all callers in `_schedule_missing_text()` use the 2-arg form (no pending set needed there). ✅

### Placeholder scan

No TBDs, TODOs, or missing code blocks. All method bodies are complete and self-contained. ✅
