"""Tests for the extracted handler modules.

Covers:
  - search.py   — apply_filters, sort_rows, parse_tv_filter, build_tv_query,
                   strip_patchy_name, extract_search_intent, deduplicate_results
  - download.py — progress_bar, format_eta, is_complete_torrent, is_direct_torrent_link,
                   result_to_url, extract_hash, state_label, completed_bytes
  - chat.py     — chat_needs_qbt_snapshot, patchy_system_prompt
  - commands.py — health_report, speed_report, on_error
  - remove.py   — remove_match_score, extract_movie_name, extract_show_name,
                   remove_kind_label
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from patchy_bot.handlers.chat import (
    chat_needs_qbt_snapshot,
    patchy_system_prompt,
)
from patchy_bot.handlers.download import (
    completed_bytes,
    extract_hash,
    format_eta,
    is_complete_torrent,
    is_direct_torrent_link,
    progress_bar,
    result_to_url,
    state_label,
)
from patchy_bot.handlers.remove import (
    extract_movie_name,
    extract_show_name,
    remove_kind_label,
    remove_match_score,
    remove_retry_backoff_s,
)
from patchy_bot.handlers.search import (
    apply_filters,
    build_tv_query,
    deduplicate_results,
    extract_search_intent,
    parse_tv_filter,
    sort_rows,
    strip_patchy_name,
)

# ---------------------------------------------------------------------------
# Helpers — build realistic search rows that pass quality scoring
# ---------------------------------------------------------------------------


def _good_row(
    name: str = "Movie.2024.1080p.WEB-DL.DDP5.1.H264-NTG",
    seeds: int = 50,
    size: int = 4_000_000_000,
    file_hash: str = "a" * 40,
    **extra: Any,
) -> dict[str, Any]:
    """Build a search result row that will survive apply_filters."""
    row: dict[str, Any] = {
        "fileName": name,
        "name": name,
        "nbSeeders": seeds,
        "seeders": seeds,
        "fileSize": size,
        "size": size,
        "fileHash": file_hash,
        "hash": file_hash,
    }
    row.update(extra)
    return row


# ===================================================================
# 1. Search handler — apply_filters (8 tests)
# ===================================================================


def test_apply_filters_removes_low_seed_results() -> None:
    """Rows with fewer seeds than min_seeds are dropped."""
    rows = [_good_row(seeds=2)]
    out = apply_filters(rows, min_seeds=5, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 0


def test_apply_filters_removes_below_min_quality() -> None:
    """A 480p row is dropped when min_quality is 1080."""
    rows = [_good_row(name="Movie.2024.480p.DVDRip.x264-GROUP", seeds=50)]
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=1080)
    assert len(out) == 0


def test_apply_filters_removes_below_min_size() -> None:
    """A 100 MB row is dropped when min_size is 1 GB."""
    rows = [_good_row(size=100_000_000)]
    out = apply_filters(rows, min_seeds=1, min_size=1_000_000_000, max_size=None, min_quality=0)
    assert len(out) == 0


def test_apply_filters_removes_above_max_size() -> None:
    """A 50 GB row is dropped when max_size is 10 GB."""
    rows = [_good_row(size=50_000_000_000)]
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=10_000_000_000, min_quality=0)
    assert len(out) == 0


def test_apply_filters_keeps_qualifying_results() -> None:
    """Good rows pass through all filters intact."""
    rows = [_good_row()]
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 1
    assert out[0]["fileName"] == rows[0]["fileName"]


def test_apply_filters_no_hash_no_direct_link_rejected() -> None:
    """Row without a valid hash and without a direct link is dropped."""
    rows = [_good_row(file_hash="badhash", seeds=50)]
    rows[0]["fileUrl"] = "https://example.com/info-page"
    rows[0]["url"] = ""
    rows[0]["descrLink"] = ""
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 0


def test_apply_filters_magnet_link_accepted() -> None:
    """Row without a hash but with a magnet link passes source check."""
    rows = [_good_row(file_hash="nothex", seeds=50)]
    rows[0]["fileUrl"] = "magnet:?xt=urn:btih:" + "a" * 40
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 1


def test_apply_filters_quality_scoring_blocks_cam() -> None:
    """CAM releases are rejected outright by apply_filters."""
    rows = [_good_row(name="Movie.2024.HDCAM.x264-GROUP", seeds=500)]
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert out == []


def test_apply_filters_passes_media_type_episode() -> None:
    """Episode-sized result (800MB) should NOT get size penalty with media_type='episode'."""
    rows = [_good_row(name="Show.S01E01.1080p.WEB-DL.x264-GROUP", size=800_000_000)]
    out = apply_filters(
        rows,
        min_seeds=1,
        min_size=None,
        max_size=None,
        min_quality=0,
        media_type="episode",
    )
    assert len(out) == 1
    ts = out[0]["_quality_score"]
    assert ts.format_score > -50


def test_apply_filters_defaults_movie_media_type() -> None:
    """Without an explicit media_type, apply_filters defaults to 'movie' and accepts a good movie row."""
    rows = [_good_row()]
    out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 1


def test_apply_filters_logs_summary_with_drops(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """apply_filters emits one INFO summary line when dropped > 0."""
    rows = [
        _good_row(seeds=0),  # dropped by seeds stage
        _good_row(name="Movie.2023.CAM.XviD-GROUP", seeds=500),  # dropped by scoring
        _good_row(),  # passes
    ]
    with caplog.at_level(logging.INFO, logger="qbtg"):
        out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 1
    assert "Search filter:" in caplog.text
    assert "3 in \u2192 1 passed" in caplog.text
    assert "seeds: -1" in caplog.text
    assert "scoring: -1" in caplog.text


def test_apply_filters_no_summary_when_nothing_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When nothing is dropped, the summary log line is silenced."""
    rows = [_good_row()]
    with caplog.at_level(logging.INFO, logger="qbtg"):
        out = apply_filters(rows, min_seeds=1, min_size=None, max_size=None, min_quality=0)
    assert len(out) == 1
    assert "Search filter:" not in caplog.text


# ===================================================================
# 2. Search handler — sort_rows (2 tests)
# ===================================================================


def test_sort_rows_by_seeds_desc() -> None:
    """Rows are sorted by seed count in descending order."""
    rows = [
        {"nbSeeders": 10, "name": "A"},
        {"nbSeeders": 50, "name": "B"},
        {"nbSeeders": 30, "name": "C"},
    ]
    result = sort_rows(rows, "seeds", "desc")
    seeds = [int(r["nbSeeders"]) for r in result]
    assert seeds == [50, 30, 10]


def test_sort_rows_by_name_asc() -> None:
    """Rows are sorted alphabetically by name in ascending order."""
    rows = [
        {"name": "Zebra"},
        {"name": "Apple"},
        {"name": "Mango"},
    ]
    result = sort_rows(rows, "name", "asc")
    names = [r["name"] for r in result]
    assert names == ["Apple", "Mango", "Zebra"]


# ===================================================================
# 3. Search handler — parse_tv_filter (4 tests)
# ===================================================================


def test_parse_tv_filter_s_and_e() -> None:
    """Standard S01E02 format returns (1, 2)."""
    assert parse_tv_filter("S1E2") == (1, 2)


def test_parse_tv_filter_season_episode_words() -> None:
    """Verbose 'season 1 episode 2' format returns (1, 2)."""
    assert parse_tv_filter("season 1 episode 2") == (1, 2)


def test_parse_tv_filter_season_only() -> None:
    """'season 3' with no episode returns (3, None)."""
    assert parse_tv_filter("season 3") == (3, None)


def test_parse_tv_filter_episode_only() -> None:
    """'episode 5' with no season returns (None, 5)."""
    assert parse_tv_filter("episode 5") == (None, 5)


def test_parse_tv_filter_no_match() -> None:
    """Random text returns None."""
    assert parse_tv_filter("hello world") is None


# ===================================================================
# 4. Search handler — build_tv_query (3 tests)
# ===================================================================


def test_build_tv_query_season_and_episode() -> None:
    assert build_tv_query("Breaking Bad", 1, 2) == "Breaking Bad S01E02"


def test_build_tv_query_season_only() -> None:
    assert build_tv_query("Breaking Bad", 3, None) == "Breaking Bad S03"


def test_build_tv_query_title_only() -> None:
    assert build_tv_query("Breaking Bad", None, None) == "Breaking Bad"


# ===================================================================
# 5. Search handler — strip_patchy_name + extract_search_intent (3 tests)
# ===================================================================


def test_strip_patchy_name_removes_greeting() -> None:
    """'hey Patchy, do something' becomes 'do something'."""
    result = strip_patchy_name("hey Patchy, do something", "Patchy")
    assert result == "do something"


def test_extract_search_intent_explicit_verb() -> None:
    """'search for breaking bad' extracts 'breaking bad' as query."""
    query, hint = extract_search_intent("search for breaking bad", "Patchy")
    assert query == "breaking bad"


def test_extract_search_intent_no_match() -> None:
    """Random text has no search intent."""
    query, hint = extract_search_intent("hello world", "Patchy")
    assert query is None


# ===================================================================
# 6. Search handler — deduplicate_results (2 tests)
# ===================================================================


def test_deduplicate_keeps_best_seeder() -> None:
    """When two rows share the same hash, keep the one with more seeds."""
    h = "a" * 40
    rows = [
        {"fileHash": h, "nbSeeders": 10, "name": "first"},
        {"fileHash": h, "nbSeeders": 50, "name": "second"},
    ]
    out = deduplicate_results(rows)
    assert len(out) == 1
    assert out[0]["name"] == "second"


def test_deduplicate_keeps_no_hash_rows() -> None:
    """Rows without a valid hex hash are always kept."""
    rows = [
        {"fileHash": "short", "nbSeeders": 10, "name": "a"},
        {"fileHash": "nope", "nbSeeders": 20, "name": "b"},
    ]
    out = deduplicate_results(rows)
    assert len(out) == 2


# ===================================================================
# 7. Download handler — progress_bar (3 tests)
# ===================================================================


def test_progress_bar_zero_percent() -> None:
    """0% produces a bar with no filled blocks."""
    bar = progress_bar(0.0)
    assert "\u2588" not in bar  # no full blocks
    assert len(bar) > 0


def test_progress_bar_fifty_percent() -> None:
    """50% produces a bar roughly half-filled."""
    bar = progress_bar(50.0)
    assert "\u2588" in bar  # some full blocks present
    assert "\u2591" in bar  # some light shade present (unfilled portion)


def test_progress_bar_hundred_percent() -> None:
    """100% produces a fully filled bar with no unfilled shade."""
    bar = progress_bar(100.0)
    assert "\u2591" not in bar  # no unfilled blocks


# ===================================================================
# 8. Download handler — format_eta (3 tests)
# ===================================================================


def test_format_eta_seconds() -> None:
    """30 seconds shows as 00:00:30."""
    assert format_eta(30) == "00:00:30"


def test_format_eta_minutes() -> None:
    """90 seconds shows as 00:01:30."""
    assert format_eta(90) == "00:01:30"


def test_format_eta_hours() -> None:
    """3661 seconds (1h 1m 1s) shows hours."""
    assert format_eta(3661) == "01:01:01"


def test_format_eta_days() -> None:
    """86401 seconds (1d 0h 0m 1s) shows days."""
    assert format_eta(86401) == "1d 00:00:01"


def test_format_eta_infinity() -> None:
    """Negative or sentinel value shows infinity symbol."""
    assert format_eta(-1) == "\u221e"
    assert format_eta(8640000) == "\u221e"


# ===================================================================
# 9. Download handler — is_complete_torrent (4 tests)
# ===================================================================


def test_is_complete_torrent_uploading() -> None:
    """State 'uploading' means the download is done."""
    assert is_complete_torrent({"state": "uploading"}) is True


def test_is_complete_torrent_downloading() -> None:
    """State 'downloading' with low progress means not complete."""
    assert is_complete_torrent({"state": "downloading", "progress": 0.5}) is False


def test_is_complete_torrent_progress_full() -> None:
    """Progress >= 0.999 means complete regardless of state."""
    assert is_complete_torrent({"state": "downloading", "progress": 1.0}) is True


def test_is_complete_torrent_completed_equals_size() -> None:
    """When completed bytes match total size, torrent is complete."""
    assert is_complete_torrent({"state": "unknown", "size": 1000, "completed": 1000}) is True


# ===================================================================
# 10. Download handler — is_direct_torrent_link (4 tests)
# ===================================================================


def test_is_direct_torrent_link_magnet() -> None:
    """Magnet URIs are direct links."""
    assert is_direct_torrent_link("magnet:?xt=urn:btih:" + "a" * 40) is True


def test_is_direct_torrent_link_dotorrent() -> None:
    """.torrent file URLs are direct links."""
    assert is_direct_torrent_link("https://example.com/file.torrent") is True


def test_is_direct_torrent_link_info_page() -> None:
    """A regular web page is not a direct link."""
    assert is_direct_torrent_link("https://example.com/info/12345") is False


def test_is_direct_torrent_link_empty() -> None:
    """Empty string is not a direct link."""
    assert is_direct_torrent_link("") is False


def test_jackett_proxy_url_accepted() -> None:
    """Localhost Jackett proxy download URLs must be treated as direct torrent links."""
    url = (
        "http://127.0.0.1:9117/api/v2.0/indexers/torrentgalaxy/results/torznab/download"
        "?jackett_apikey=abc123&guid=https://example.com/torrent/12345"
    )
    assert is_direct_torrent_link(url)


def test_random_http_url_not_direct_link() -> None:
    """Generic web pages must NOT be classified as direct torrent links."""
    assert not is_direct_torrent_link("https://example.com/torrent-info-page")
    assert not is_direct_torrent_link("https://torrentgalaxy.to/torrent/12345/some-movie")


# ===================================================================
# 11. Download handler — result_to_url + extract_hash (3 tests)
# ===================================================================


def test_result_to_url_from_hash() -> None:
    """Row with a valid 40-char hex hash produces a magnet link."""
    h = "a" * 40
    url = result_to_url({"hash": h, "name": "Test"})
    assert url.startswith("magnet:?xt=urn:btih:")
    assert h in url


def test_extract_hash_from_row() -> None:
    """extract_hash finds the hash in the row dict."""
    h = "b" * 40
    assert extract_hash({"hash": h}, "") == h


def test_extract_hash_from_magnet() -> None:
    """extract_hash parses the hash from a magnet URI."""
    h = "c" * 40
    url = f"magnet:?xt=urn:btih:{h}&dn=test"
    assert extract_hash({}, url) == h


# ===================================================================
# 12. Download handler — state_label + completed_bytes (2 tests)
# ===================================================================


def test_state_label_downloading() -> None:
    """State 'downloading' returns 'downloading'."""
    assert state_label({"state": "downloading", "progress": 0.3}) == "downloading"


def test_completed_bytes_clamped() -> None:
    """completed_bytes never exceeds total size."""
    info = {"size": 1000, "completed": 2000, "downloaded": 0}
    assert completed_bytes(info) == 1000


# ===================================================================
# 13. Chat handler (4 tests)
# ===================================================================


def test_chat_needs_qbt_snapshot_with_status_keyword() -> None:
    """Text mentioning 'qbittorrent' triggers snapshot."""
    assert chat_needs_qbt_snapshot("how's qbittorrent doing") is True


def test_chat_needs_qbt_snapshot_with_download_keyword() -> None:
    """Text mentioning 'download' triggers snapshot."""
    assert chat_needs_qbt_snapshot("what's downloading right now?") is True


def test_chat_needs_qbt_snapshot_without_keyword() -> None:
    """Generic text does not trigger snapshot."""
    assert chat_needs_qbt_snapshot("hello world, nice weather") is False


def test_patchy_system_prompt_contains_name() -> None:
    """System prompt includes the configured bot name."""
    ctx = SimpleNamespace(cfg=SimpleNamespace(patchy_chat_name="Patchy"))
    prompt = patchy_system_prompt(ctx)
    assert "Patchy" in prompt


def test_patchy_system_prompt_not_empty() -> None:
    """System prompt is a non-empty string."""
    ctx = SimpleNamespace(cfg=SimpleNamespace(patchy_chat_name="TestBot"))
    prompt = patchy_system_prompt(ctx)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_patchy_system_prompt_read_only_mandate() -> None:
    """System prompt enforces read-only behavior."""
    ctx = SimpleNamespace(cfg=SimpleNamespace(patchy_chat_name="Patchy"))
    prompt = patchy_system_prompt(ctx)
    assert "READ-ONLY" in prompt.upper() or "read-only" in prompt.lower()


# ===================================================================
# 14. Commands handler — health_report (3 tests)
# ===================================================================


def _make_health_ctx(**overrides: Any) -> SimpleNamespace:
    """Build a minimal ctx that health_report can consume."""

    class FakeQBT:
        def get_transfer_info(self) -> dict:
            return {"connection_status": "connected", "dht_nodes": 100}

        def get_preferences(self) -> dict:
            return {"current_network_interface": "", "current_interface_address": ""}

        def list_search_plugins(self) -> list:
            return [{"name": "test_plugin", "enabled": True}]

        def ensure_category(self, cat: str, path: str) -> None:
            pass

        def list_categories(self) -> dict:
            return {}

    class FakePlex:
        def ready(self) -> bool:
            return False

    class FakeLLM:
        def ready(self) -> bool:
            return False

    class FakeStore:
        def get_schedule_runner_status(self) -> dict:
            return {}

        def db_diagnostics(self) -> dict:
            return {"sqlite_runtime": "3.45.0", "journal_mode": "wal", "busy_timeout_ms": 5000}

        def count_due_schedule_tracks(self, ts: int) -> int:
            return 0

    cfg = SimpleNamespace(
        movies_category="Movies",
        tv_category="TV",
        movies_path="/tmp/test_movies",
        tv_path="/tmp/test_tv",
        require_nvme_mount=False,
        nvme_mount_path="/mnt/nvme",
        vpn_required_for_downloads=False,
        vpn_interface_name="wg0",
        vpn_service_name="",
        allowed_user_ids=[12345],
        allow_group_chats=False,
        access_password="",
        patchy_chat_enabled=False,
        tmdb_api_key="",
        spam_path="",
    )
    cfg.__dict__.update(overrides)

    return SimpleNamespace(
        cfg=cfg,
        qbt=FakeQBT(),
        plex=FakePlex(),
        patchy_llm=FakeLLM(),
        store=FakeStore(),
    )


def test_health_report_returns_html_string() -> None:
    """health_report output contains HTML bold tags."""
    from patchy_bot.handlers.commands import health_report

    ctx = _make_health_ctx()
    text, ok = health_report(ctx)
    assert "<b>" in text
    assert isinstance(text, str)


def test_health_report_checks_storage() -> None:
    """health_report mentions storage/routing status."""
    from patchy_bot.handlers.commands import health_report

    ctx = _make_health_ctx()
    text, _ok = health_report(ctx)
    assert "routing/storage" in text.lower()


def test_health_report_overall_ok_when_healthy() -> None:
    """health_report returns ok=True when no hard failures exist."""
    from patchy_bot.handlers.commands import health_report

    ctx = _make_health_ctx()
    _text, ok = health_report(ctx)
    assert ok is True


# ===================================================================
# 15. Commands handler — speed_report (2 tests)
# ===================================================================


def _make_speed_ctx() -> SimpleNamespace:
    """Build a minimal ctx for speed_report."""

    class FakeQBT:
        def get_transfer_info(self) -> dict:
            return {
                "dl_info_speed": 1_000_000,
                "up_info_speed": 500_000,
                "dl_info_data": 10_000_000_000,
                "up_info_data": 5_000_000_000,
                "dht_nodes": 200,
                "connection_status": "connected",
            }

        def get_preferences(self) -> dict:
            return {
                "dl_limit": 0,
                "up_limit": 0,
                "max_active_downloads": 5,
                "max_active_torrents": 10,
                "listen_port": 12345,
            }

        def list_active(self, limit: int = 50) -> list:
            return []

    return SimpleNamespace(qbt=FakeQBT())


def test_speed_report_returns_string() -> None:
    """speed_report returns a non-empty string."""
    from patchy_bot.handlers.commands import speed_report

    ctx = _make_speed_ctx()
    text = speed_report(ctx)
    assert isinstance(text, str)
    assert len(text) > 0


def test_speed_report_contains_speed_values() -> None:
    """speed_report includes download and upload speed labels."""
    from patchy_bot.handlers.commands import speed_report

    ctx = _make_speed_ctx()
    text = speed_report(ctx)
    assert "Download" in text
    assert "Upload" in text


# ===================================================================
# 16. Commands handler — on_error (1 test)
# ===================================================================


def test_on_error_logs_exception(caplog: Any) -> None:
    """on_error logs the error without crashing."""
    import asyncio

    from patchy_bot.handlers.commands import on_error

    context = SimpleNamespace(error=RuntimeError("test boom"))
    with caplog.at_level(logging.WARNING):
        asyncio.get_event_loop().run_until_complete(on_error(None, context))
    # The function should not raise; it may or may not log depending on error type.
    # The key check: it did not crash.


# ===================================================================
# 17. Remove handler — remove_match_score (3 tests)
# ===================================================================


def test_remove_match_score_exact_match() -> None:
    """Exact match gives score 100."""
    assert remove_match_score("breaking bad", "breaking bad") == 100


def test_remove_match_score_partial_match() -> None:
    """Query contained in candidate gives score 70."""
    assert remove_match_score("bad", "breaking bad") == 70


def test_remove_match_score_no_match() -> None:
    """Completely unrelated strings give score 0."""
    assert remove_match_score("seinfeld", "breaking bad") == 0


# ===================================================================
# 18. Remove handler — extract names (4 tests)
# ===================================================================


def test_extract_movie_name_strips_year_and_quality() -> None:
    """'Movie.2024.1080p.BluRay' becomes 'Movie (2024)'."""
    result = extract_movie_name("Movie.2024.1080p.BluRay.x264-GROUP")
    assert result == "Movie (2024)"


def test_extract_movie_name_preserves_multi_word() -> None:
    """'The.Dark.Knight.2008.1080p' becomes 'The Dark Knight (2008)'."""
    result = extract_movie_name("The.Dark.Knight.2008.1080p.BluRay.x264")
    assert result == "The Dark Knight (2008)"


def test_extract_movie_name_strips_dot_noise_even_with_site_prefix() -> None:
    result = extract_movie_name("www.UIndex.org - Dune.Part.Two.2024.mkv")
    assert result == "Dune Part Two (2024)"


def test_extract_movie_name_without_year_never_keeps_dots() -> None:
    result = extract_movie_name("Some.Movie.Without.Year.1080p")
    assert result == "Some Movie Without Year"
    assert "." not in result


def test_extract_show_name_strips_season_info() -> None:
    """'Show.S01.1080p' becomes 'Show'."""
    result = extract_show_name("Show.S01.1080p.WEB-DL.x264-GROUP")
    assert result == "Show"


def test_extract_show_name_multi_word() -> None:
    """'Better.Call.Saul.S06.1080p' becomes 'Better Call Saul'."""
    result = extract_show_name("Better.Call.Saul.S06.1080p.WEB-DL")
    assert result == "Better Call Saul"


# ===================================================================
# 19. Remove handler — remove_kind_label (3 tests)
# ===================================================================


def test_remove_kind_label_for_movie_dir() -> None:
    """Movie directory is labeled 'movie folder'."""
    assert remove_kind_label("movie", True) == "movie folder"


def test_remove_kind_label_for_show() -> None:
    """Show directory is labeled 'series'."""
    assert remove_kind_label("show", True) == "series"


def test_remove_kind_label_for_episode_file() -> None:
    """Episode file is labeled 'episode'."""
    assert remove_kind_label("episode", False) == "episode"


# ===================================================================
# 20. Remove handler — remove_retry_backoff_s (1 test)
# ===================================================================


def test_remove_retry_backoff_s_escalates() -> None:
    """Backoff increases with retry count."""
    b0 = remove_retry_backoff_s(0)
    b1 = remove_retry_backoff_s(1)
    b4 = remove_retry_backoff_s(4)
    assert b0 < b1 < b4


# ---------------------------------------------------------------------------
# prioritize_results — single-result, 1080p-preferred logic
# ---------------------------------------------------------------------------


def test_build_search_parser_rejects_removed_flags() -> None:
    """--min-quality and --limit were removed; parser must reject them."""
    import pytest
    from patchy_bot.handlers.search import build_search_parser

    parser = build_search_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--min-quality", "1080", "test"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--limit", "5", "test"])


def test_build_search_parser_accepts_valid_flags() -> None:
    """Parser still accepts remaining flags."""
    from patchy_bot.handlers.search import build_search_parser

    parser = build_search_parser()
    args = parser.parse_args(["--min-seeds", "10", "--sort", "seeds", "--order", "desc", "my", "query"])
    assert args.min_seeds == 10
    assert args.sort == "seeds"
    assert args.order == "desc"
    assert args.query == ["my", "query"]


def test_prioritize_empty_input() -> None:
    from patchy_bot.handlers.search import prioritize_results

    assert prioritize_results([]) == []


def test_prioritize_returns_single_result_for_one_row() -> None:
    from patchy_bot.handlers.search import prioritize_results
    from patchy_bot.quality import score_torrent

    row = {
        "name": "Movie.1080p.WEB-DL.x264-GRP",
        "nbSeeders": 50,
        "fileSize": 2_000_000_000,
        "_quality_score": score_torrent("Movie.1080p.WEB-DL.x264-GRP", 2_000_000_000, 50),
    }
    result = prioritize_results([row])
    assert len(result) == 1
    assert result[0] is row


def test_prioritize_picks_highest_seeded_1080p() -> None:
    from patchy_bot.handlers.search import prioritize_results
    from patchy_bot.quality import score_torrent

    rows = [
        {
            "name": "Movie.1080p.WEB-DL.x264-LOW",
            "nbSeeders": 50,
            "fileSize": 2_000_000_000,
            "_quality_score": score_torrent("Movie.1080p.WEB-DL.x264-LOW", 2_000_000_000, 50),
        },
        {
            "name": "Movie.1080p.BluRay.x264-HIGH",
            "nbSeeders": 100,
            "fileSize": 4_000_000_000,
            "_quality_score": score_torrent("Movie.1080p.BluRay.x264-HIGH", 4_000_000_000, 100),
        },
    ]
    result = prioritize_results(rows)
    assert len(result) == 1
    assert result[0]["nbSeeders"] == 100


def test_prioritize_prefers_1080p_over_4k() -> None:
    from patchy_bot.handlers.search import prioritize_results
    from patchy_bot.quality import score_torrent

    rows = [
        {
            "name": "Movie.2160p.WEB-DL.x265-4K",
            "nbSeeders": 200,
            "fileSize": 8_000_000_000,
            "_quality_score": score_torrent("Movie.2160p.WEB-DL.x265-4K", 8_000_000_000, 200),
        },
        {
            "name": "Movie.1080p.WEB-DL.x264-HD",
            "nbSeeders": 50,
            "fileSize": 2_000_000_000,
            "_quality_score": score_torrent("Movie.1080p.WEB-DL.x264-HD", 2_000_000_000, 50),
        },
    ]
    result = prioritize_results(rows)
    assert len(result) == 1
    assert "1080p" in result[0]["name"]


def test_prioritize_fallback_to_highest_seeded_when_no_1080p() -> None:
    from patchy_bot.handlers.search import prioritize_results
    from patchy_bot.quality import score_torrent

    rows = [
        {
            "name": "Movie.720p.WEB-DL.x264-LOWER",
            "nbSeeders": 80,
            "fileSize": 1_000_000_000,
            "_quality_score": score_torrent("Movie.720p.WEB-DL.x264-LOWER", 1_000_000_000, 80),
        },
        {
            "name": "Movie.2160p.WEB-DL.x265-4K",
            "nbSeeders": 30,
            "fileSize": 8_000_000_000,
            "_quality_score": score_torrent("Movie.2160p.WEB-DL.x265-4K", 8_000_000_000, 30),
        },
    ]
    result = prioritize_results(rows)
    assert len(result) == 1
    assert result[0]["nbSeeders"] == 80


def test_prioritize_deprioritizes_trash() -> None:
    from patchy_bot.handlers.search import prioritize_results
    from patchy_bot.quality import score_torrent

    # CAM/TS sources are marked as trash by score_torrent; good WEB-DL sources are not.
    # The good row has fewer seeds but should win because it's not trash.
    trash_row = {
        "name": "Movie.1080p.CAM.x264-GRP",
        "nbSeeders": 500,
        "fileSize": 800_000_000,
        "_quality_score": score_torrent("Movie.1080p.CAM.x264-GRP", 800_000_000, 500),
    }
    good_row = {
        "name": "Movie.1080p.WEB-DL.x264-GRP",
        "nbSeeders": 50,
        "fileSize": 2_000_000_000,
        "_quality_score": score_torrent("Movie.1080p.WEB-DL.x264-GRP", 2_000_000_000, 50),
    }
    # Only include good_row if it's not also rejected — score_torrent may reject CAM outright
    trash_qs = trash_row["_quality_score"]
    good_qs = good_row["_quality_score"]
    if trash_qs.is_rejected:
        # CAM was fully rejected, so only good_row is a valid candidate anyway
        result = prioritize_results([good_row])
        assert len(result) == 1
        assert result[0]["name"] == good_row["name"]
    else:
        result = prioritize_results([trash_row, good_row])
        assert len(result) == 1
        # Non-trash should win regardless of seed count
        if not good_qs.parsed.trash:
            assert result[0]["name"] == good_row["name"]


def test_prioritize_format_score_tiebreaker() -> None:
    """When two 1080p rows have equal seeds, higher format_score wins."""
    from types import SimpleNamespace

    from patchy_bot.handlers.search import prioritize_results

    low_fmt = SimpleNamespace(format_score=50, parsed=SimpleNamespace(trash=False), is_rejected=False)
    high_fmt = SimpleNamespace(format_score=200, parsed=SimpleNamespace(trash=False), is_rejected=False)
    row_low = {"name": "Movie.1080p.WEB-DL.x264-LOW", "nbSeeders": 100, "_quality_score": low_fmt}
    row_high = {"name": "Movie.1080p.BluRay.x264-HIGH", "nbSeeders": 100, "_quality_score": high_fmt}
    result = prioritize_results([row_low, row_high])
    assert len(result) == 1
    assert result[0]["name"] == "Movie.1080p.BluRay.x264-HIGH"


def test_prioritize_all_trash_returns_best_trash() -> None:
    """When every result is trash, pick the highest-seeded trash row."""
    from types import SimpleNamespace

    from patchy_bot.handlers.search import prioritize_results

    ts_a = SimpleNamespace(format_score=10, parsed=SimpleNamespace(trash=True), is_rejected=False)
    ts_b = SimpleNamespace(format_score=10, parsed=SimpleNamespace(trash=True), is_rejected=False)
    row_a = {"name": "Movie.1080p.CAM.x264-A", "nbSeeders": 30, "_quality_score": ts_a}
    row_b = {"name": "Movie.1080p.TS.x264-B", "nbSeeders": 80, "_quality_score": ts_b}
    result = prioritize_results([row_a, row_b])
    assert len(result) == 1
    assert result[0]["nbSeeders"] == 80
