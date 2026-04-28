# Plex Section Fallback Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a `/remove` deletion can't match the deleted file to a specific Plex library section, fall back to refreshing all sections of the matching type so the Plex library is always updated after every removal.

**Architecture:** Two targeted changes to `PlexInventoryClient` in `patchy_bot/clients/plex.py`. (1) A new `refresh_all_by_type` method that iterates all Plex sections and triggers refresh+wait+emptyTrash on each matching section type. (2) Fix `verify_remove_identity_absent` to scan all sections instead of returning an error when `section_key` is missing. One change to `_remove_attempt_plex_cleanup` in `BotApp` (`patchy_bot/bot.py`) to call the new fallback when `section_key` is empty.

**Tech Stack:** Python 3.12, `patchy_bot/` package <!-- pre-decomposition: was single-file `qbt_telegram_bot.py` monolith -->, pytest, `unittest.mock`

---

## Background

When a user deletes a file through `/remove`, the bot calls `resolve_remove_identity` to find which Plex section covers the file path. If that lookup fails (e.g. the file lives in a path not registered in any Plex library location), `identity` is `None` and the remove job is created with no `plex_section_key`. In `_remove_attempt_plex_cleanup` the refresh is silently skipped (line 4079: `if section_key:`). In `verify_remove_identity_absent` the check immediately returns `(False, "Missing Plex section key for {title}")` (line 1348). The user sees ⚠️ "Plex cleanup pending: Missing Plex section key" and the deleted item remains visible in Plex until the next scheduled scan.

---

## Files Modified

- **Modify:** `telegram-qbt/patchy_bot/clients/plex.py`
  - Add `PlexInventoryClient.refresh_all_by_type` method (after `purge_deleted_path`)
  - Fix `PlexInventoryClient.verify_remove_identity_absent` — replace hard error with cross-section path scan
- **Modify:** `telegram-qbt/patchy_bot/bot.py`
  - Fix `BotApp._remove_attempt_plex_cleanup` — add `else` branch for missing `section_key`
- **Modify:** `telegram-qbt/tests/test_parsing.py`
  - Add 3 new tests covering each code path above

---

## Task 1: Add `PlexInventoryClient.refresh_all_by_type`

**Files:**
- Modify: `telegram-qbt/patchy_bot/clients/plex.py` (after `purge_deleted_path`)
- Test: `telegram-qbt/tests/test_parsing.py`

### Step 1: Write the failing test

In `tests/test_parsing.py`, add after the last PlexInventoryClient test:

```python
def test_plex_refresh_all_by_type_calls_refresh_and_empty_trash_for_matching_sections(monkeypatch) -> None:
    from unittest.mock import call
    from patchy_bot.clients.plex import PlexInventoryClient

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = 200
            self.text = ""

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []

        def request(self, method: str, url: str, *, params: dict | None = None, timeout: int | None = None) -> FakeResponse:
            self.calls.append((method, url, dict(params or {})))
            return FakeResponse()

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")
    fake_session = FakeSession()
    client.session = fake_session  # type: ignore[assignment]
    monkeypatch.setattr("patchy_bot.clients.plex.time.sleep", lambda _: None)

    # Two movie sections, one show section — only movie sections should be refreshed
    section_calls = [
        [
            {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
            {"key": "2", "title": "4K Movies", "type": "movie", "locations": ["/mnt/4k"], "refreshing": False},
            {"key": "3", "title": "TV Shows", "type": "show", "locations": ["/mnt/tv"], "refreshing": False},
        ]
    ] * 10  # repeated to cover _wait_for_section_idle polls

    def fake_sections() -> list[dict]:
        return section_calls[0] if section_calls else []

    client._sections = fake_sections  # type: ignore[method-assign]

    titles = client.refresh_all_by_type(["movie"])

    assert titles == ["Movies", "4K Movies"]
    # Each movie section must have had a POST refresh and PUT emptyTrash
    post_urls = [url for method, url, _ in fake_session.calls if method == "POST"]
    put_urls  = [url for method, url, _ in fake_session.calls if method == "PUT"]
    assert "http://plex.local:32400/library/sections/1/refresh" in post_urls
    assert "http://plex.local:32400/library/sections/2/refresh" in post_urls
    assert "http://plex.local:32400/library/sections/3/refresh" not in post_urls
    assert "http://plex.local:32400/library/sections/1/emptyTrash" in put_urls
    assert "http://plex.local:32400/library/sections/2/emptyTrash" in put_urls
    assert "http://plex.local:32400/library/sections/3/emptyTrash" not in put_urls
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/test_parsing.py::test_plex_refresh_all_by_type_calls_refresh_and_empty_trash_for_matching_sections -v
```
Expected: `FAILED` — `AttributeError: 'PlexInventoryClient' object has no attribute 'refresh_all_by_type'`

- [ ] **Step 3: Implement `refresh_all_by_type`**

In `patchy_bot/clients/plex.py`, insert this method directly after `purge_deleted_path`:

```python
def refresh_all_by_type(self, section_types: list[str]) -> list[str]:
    """Refresh + emptyTrash on every Plex section whose type matches section_types.

    Used as a fallback when the target path cannot be matched to a specific
    section. Returns a list of section titles that were refreshed.
    """
    types = {str(t).lower() for t in section_types}
    refreshed: list[str] = []
    for section in self._sections():
        if str(section.get("type") or "").lower() not in types:
            continue
        key = str(section.get("key") or "").strip()
        if not key:
            continue
        title = str(section.get("title") or key)
        self._request("POST", f"/library/sections/{key}/refresh")
        self._wait_for_section_idle(key, timeout_s=30, min_wait_s=3.0)
        self._request("PUT", f"/library/sections/{key}/emptyTrash")
        refreshed.append(title)
    return refreshed
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/test_parsing.py::test_plex_refresh_all_by_type_calls_refresh_and_empty_trash_for_matching_sections -v
```
Expected: `PASSED`

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/ -q
```
Expected: all existing tests + 1 new = 94 passed, 0 failed

- [ ] **Step 6: Commit**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
git add patchy_bot/clients/plex.py tests/test_parsing.py
git commit -m "feat(plex): add refresh_all_by_type fallback for unmatched section paths"
```

---

## Task 2: Fix `verify_remove_identity_absent` to scan all sections when `section_key` is missing

**Files:**
- Modify: `telegram-qbt/patchy_bot/clients/plex.py`
- Test: `telegram-qbt/tests/test_parsing.py`

The current code at lines 1346–1348 returns `(False, "Missing Plex section key for {title}")` immediately when `section_key` is empty. This means verification always fails when section_key wasn't resolved, causing the cleanup job to remain in `plex_pending` forever.

The fix: when `section_key` is empty, iterate **all** sections and check all movie + show entries for the target_path. If not found in any section → verified.

### Step 1: Write the failing test

In `tests/test_parsing.py`, add:

```python
def test_plex_verify_remove_identity_absent_scans_all_sections_when_no_section_key() -> None:
    from patchy_bot.clients.plex import PlexInventoryClient

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")

    # Simulate two movie sections — target_path not present in either
    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
        {"key": "2", "title": "4K Movies", "type": "movie", "locations": ["/mnt/4k"], "refreshing": False},
    ]
    # Both sections return empty XML (no media)
    client._get_xml = lambda path, params=None: __import__("xml.etree.ElementTree", fromlist=["ElementTree"]).fromstring("<MediaContainer />")  # type: ignore[method-assign]

    ok, detail = client.verify_remove_identity_absent(
        "/mnt/movies/Tires (2023)",
        "movie",
        {"verification_mode": "path_fallback", "title": "Tires"},
    )

    assert ok is True
    assert "Tires" in detail


def test_plex_verify_remove_identity_absent_fails_when_path_still_in_any_section() -> None:
    import xml.etree.ElementTree as ET
    from patchy_bot.clients.plex import PlexInventoryClient

    target = "/mnt/movies/Tires (2023)"

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")
    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
    ]

    # Section returns an entry whose Part file matches the target path
    def fake_get_xml(path: str, *, params: dict | None = None) -> ET.Element:
        if "/all" in path:
            xml = f"""<MediaContainer>
              <Video ratingKey="99" title="Tires" type="movie">
                <Media><Part file="{target}" /></Media>
              </Video>
            </MediaContainer>"""
            return ET.fromstring(xml)
        return ET.fromstring("<MediaContainer />")

    client._get_xml = fake_get_xml  # type: ignore[method-assign]

    ok, detail = client.verify_remove_identity_absent(
        target,
        "movie",
        {"verification_mode": "path_fallback", "title": "Tires"},
    )

    assert ok is False
    assert "Tires" in detail
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/test_parsing.py::test_plex_verify_remove_identity_absent_scans_all_sections_when_no_section_key tests/test_parsing.py::test_plex_verify_remove_identity_absent_fails_when_path_still_in_any_section -v
```
Expected: both `FAILED` — first returns `ok=False` with "Missing Plex section key", second returns `ok=False` but for the wrong reason.

- [ ] **Step 3: Implement the fix**

In `patchy_bot/clients/plex.py`, find `verify_remove_identity_absent`. Replace these two lines:

**OLD (lines 1346–1348):**
```python
        section_key = str(data.get("section_key") or "").strip()
        if not section_key:
            return False, f"Missing Plex section key for {title}"
```

**NEW:**
```python
        section_key = str(data.get("section_key") or "").strip()
        if not section_key:
            # No section key — scan all movie and show sections for the target path.
            for section in self._sections():
                sec_key = str(section.get("key") or "").strip()
                sec_type = str(section.get("type") or "").strip().lower()
                if not sec_key:
                    continue
                if sec_type == "movie":
                    root = self._get_xml(f"/library/sections/{sec_key}/all", params={"type": 1})
                    for meta in root.findall(".//*[@ratingKey]"):
                        if any(self._path_matches_remove_target(p, target_path, remove_kind) for p in self._parts_for_meta(meta)):
                            return False, f"Plex still has media parts for {title}"
                elif sec_type == "show":
                    root = self._get_xml(f"/library/sections/{sec_key}/all", params={"type": 2})
                    for meta in root.findall(".//*[@ratingKey]"):
                        show_rk = str(meta.attrib.get("ratingKey") or "").strip()
                        if not show_rk:
                            continue
                        leaves = self._get_xml(f"/library/metadata/{show_rk}/allLeaves")
                        for leaf in leaves.findall(".//*[@ratingKey]"):
                            if any(self._path_matches_remove_target(p, target_path, remove_kind) for p in self._parts_for_meta(leaf)):
                                return False, f"Plex still has media parts for {title}"
            return True, f"Plex media parts removed for {title} (all-section scan)"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/test_parsing.py::test_plex_verify_remove_identity_absent_scans_all_sections_when_no_section_key tests/test_parsing.py::test_plex_verify_remove_identity_absent_fails_when_path_still_in_any_section -v
```
Expected: both `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/ -q
```
Expected: 96 passed, 0 failed

- [ ] **Step 6: Commit**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
git add patchy_bot/clients/plex.py tests/test_parsing.py
git commit -m "fix(plex): scan all sections in verify_remove_identity_absent when section_key is missing"
```

---

## Task 3: Update `_remove_attempt_plex_cleanup` to use the fallback when `section_key` is empty

**Files:**
- Modify: `telegram-qbt/patchy_bot/bot.py`
- Test: `telegram-qbt/tests/test_parsing.py`

Currently when `section_key` is empty the `if section_key:` block is skipped entirely — no refresh, no emptyTrash. Add an `else` branch that calls `refresh_all_by_type` with the section type inferred from `remove_kind`.

### Step 1: Write the failing test

In `tests/test_parsing.py`, add:

```python
def test_remove_attempt_plex_cleanup_falls_back_to_refresh_all_when_section_key_missing(monkeypatch) -> None:
    from unittest.mock import MagicMock
    from patchy_bot.bot import BotApp
    from patchy_bot.clients.plex import PlexInventoryClient

    refresh_calls: list[list[str]] = []

    def fake_refresh_all_by_type(section_types: list[str]) -> list[str]:
        refresh_calls.append(list(section_types))
        return ["Movies"]

    def fake_verify_absent(target_path: str, remove_kind: str, verification: dict | None) -> tuple[bool, str]:
        return True, "Plex media parts removed for Tires (all-section scan)"

    plex = MagicMock(spec=PlexInventoryClient)
    plex.refresh_all_by_type = fake_refresh_all_by_type
    plex.verify_remove_identity_absent = fake_verify_absent

    store = MagicMock()
    store.update_remove_job.return_value = None

    bot = MagicMock(spec=BotApp)
    bot.plex = plex
    bot.store = store

    job = {
        "job_id": "test-job-1",
        "plex_section_key": "",          # <-- empty: triggers fallback
        "scan_path": "",
        "target_path": "/mnt/movies/Tires (2023)",
        "remove_kind": "movie",
        "plex_title": "Tires",
        "item_name": "Tires",
        "verification_json": {},
        "retry_count": 0,
    }

    result = BotApp._remove_attempt_plex_cleanup(bot, job, inline_timeout_s=10)

    assert result["status"] == "verified"
    assert refresh_calls == [["movie"]]  # fallback was called with "movie" type


def test_remove_attempt_plex_cleanup_falls_back_to_show_type_for_episode_remove_kind(monkeypatch) -> None:
    from unittest.mock import MagicMock
    from patchy_bot.bot import BotApp
    from patchy_bot.clients.plex import PlexInventoryClient

    refresh_calls: list[list[str]] = []

    def fake_refresh_all_by_type(section_types: list[str]) -> list[str]:
        refresh_calls.append(list(section_types))
        return ["TV Shows"]

    def fake_verify_absent(target_path: str, remove_kind: str, verification: dict | None) -> tuple[bool, str]:
        return True, "Plex media parts removed (all-section scan)"

    plex = MagicMock(spec=PlexInventoryClient)
    plex.refresh_all_by_type = fake_refresh_all_by_type
    plex.verify_remove_identity_absent = fake_verify_absent

    store = MagicMock()
    store.update_remove_job.return_value = None

    bot = MagicMock(spec=BotApp)
    bot.plex = plex
    bot.store = store

    job = {
        "job_id": "test-job-2",
        "plex_section_key": "",
        "scan_path": "",
        "target_path": "/mnt/tv/Tires/Season 01/Tires.S01E01.mkv",
        "remove_kind": "episode",         # non-movie remove_kind → show type
        "plex_title": "Tires S01E01",
        "item_name": "Tires S01E01",
        "verification_json": {},
        "retry_count": 0,
    }

    result = BotApp._remove_attempt_plex_cleanup(bot, job, inline_timeout_s=10)

    assert result["status"] == "verified"
    assert refresh_calls == [["show"]]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/test_parsing.py::test_remove_attempt_plex_cleanup_falls_back_to_refresh_all_when_section_key_missing tests/test_parsing.py::test_remove_attempt_plex_cleanup_falls_back_to_show_type_for_episode_remove_kind -v
```
Expected: both `FAILED` — the fallback doesn't exist yet, so `refresh_all_by_type` is never called.

- [ ] **Step 3: Implement the fallback in `_remove_attempt_plex_cleanup`**

In `patchy_bot/bot.py`, find `_remove_attempt_plex_cleanup`. Replace this block:

**OLD:**
```python
                if section_key:
                    self.plex._request("POST", f"/library/sections/{section_key}/refresh", params={"path": scan_path})
                    self.plex._wait_for_section_idle(section_key, timeout_s=min(30, inline_timeout_s), min_wait_s=3.0)
                    self.plex._request("PUT", f"/library/sections/{section_key}/emptyTrash")
```

**NEW:**
```python
                if section_key:
                    self.plex._request("POST", f"/library/sections/{section_key}/refresh", params={"path": scan_path})
                    self.plex._wait_for_section_idle(section_key, timeout_s=min(30, inline_timeout_s), min_wait_s=3.0)
                    self.plex._request("PUT", f"/library/sections/{section_key}/emptyTrash")
                else:
                    # Path didn't match a known Plex section — refresh all sections of the
                    # matching content type so the deletion always surfaces in Plex.
                    fallback_types = ["movie"] if remove_kind == "movie" else ["show"]
                    self.plex.refresh_all_by_type(fallback_types)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/test_parsing.py::test_remove_attempt_plex_cleanup_falls_back_to_refresh_all_when_section_key_missing tests/test_parsing.py::test_remove_attempt_plex_cleanup_falls_back_to_show_type_for_episode_remove_kind -v
```
Expected: both `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
.venv/bin/python -m pytest tests/ -q
```
Expected: 98 passed, 0 failed

- [ ] **Step 6: Commit**

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
git add patchy_bot/bot.py tests/test_parsing.py
git commit -m "fix(plex): fall back to full-type section refresh when section_key is missing on delete"
```

---

## Task 4: Restart the bot and verify the fix is live

- [ ] **Step 1: Restart the bot service**

```bash
sudo systemctl restart telegram-qbt-bot.service && sleep 3 && systemctl is-active telegram-qbt-bot.service
```
Expected output: `active`

- [ ] **Step 2: Verify with a test deletion**

In Telegram, delete any movie or TV item. The confirmation message should now show either:
- `✅ Batch delete verified` — Plex confirmed removal
- The old `⚠️ Plex cleanup pending: Missing Plex section key` error should **never appear again**

- [ ] **Step 3: Manually fix the "Tires" Plex entry still stuck in the library**

The Tires entry (shown in the screenshot) is already deleted from disk but still appears in Plex. Trigger a manual library scan from the Plex dashboard → Movies library → Scan Library Files. This is a one-time cleanup for this specific stuck entry — future deletions will handle it automatically.

---

## Acceptance Criteria

- `PlexInventoryClient.refresh_all_by_type(["movie"])` calls POST + wait + PUT emptyTrash on all movie sections and skips TV sections
- `verify_remove_identity_absent` with no `section_key` scans all sections rather than returning an error
- `_remove_attempt_plex_cleanup` calls `refresh_all_by_type` when `section_key` is empty, using `["movie"]` for movies and `["show"]` for all TV remove kinds (show/season/episode)
- 98 tests pass, 0 fail
- "Missing Plex section key" error never appears in removal confirmations again
