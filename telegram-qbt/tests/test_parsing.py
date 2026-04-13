import asyncio
import io
import os
from types import SimpleNamespace

from telegram.error import TelegramError

from qbt_telegram_bot import (
    BotApp,
    PlexInventoryClient,
    RateLimiter,
    Store,
    _relative_time,
    extract_episode_codes,
    format_remove_episode_label,
    format_remove_season_label,
    is_remove_media_file,
    normalize_title,
    now_ts,
)


def test_normalize_title_removes_articles_only_at_word_boundaries() -> None:
    assert normalize_title("The Last of Us (2023)") == "last of us"
    assert normalize_title("Thematic The Movie") == "thematic movie"


def test_extract_episode_codes_supports_sxe_and_x_formats() -> None:
    assert extract_episode_codes("Show.S01E02.1080p") == {"S01E02"}
    assert extract_episode_codes("Show 1x02 2x03") == {"S01E02", "S02E03"}


def test_extract_episode_codes_ignores_noise_without_episode_markers() -> None:
    assert extract_episode_codes("Show Season 1 1080p") == set()


def test_schedule_refresh_degrades_cleanly_when_metadata_lookup_fails(monkeypatch) -> None:
    import patchy_bot.handlers.schedule as _sch

    monkeypatch.setattr(
        _sch,
        "schedule_probe_track",
        lambda ctx, t, season=None: (_ for _ in ()).throw(RuntimeError("tv metadata offline")),
    )

    class DummyStore:
        def __init__(self) -> None:
            self.updated: dict[str, object] = {}

        def update_schedule_track(self, track_id: str, **fields: object) -> None:
            self.updated = {"track_id": track_id, **fields}

        def get_schedule_track_any(self, track_id: str) -> dict[str, object]:
            return {
                "track_id": track_id,
                "last_probe_json": self.updated.get("last_probe_json", {}),
                "last_probe_at": self.updated.get("last_probe_at"),
                "next_check_at": self.updated.get("next_check_at"),
            }

    class DummyBot:
        def __init__(self) -> None:
            self.store = DummyStore()
            self.schedule_source_state_lock = __import__("threading").Lock()
            self.schedule_source_state: dict[str, dict] = {
                "metadata": {
                    "status": "unknown",
                    "consecutive_failures": 0,
                    "backoff_until": 0,
                    "last_error": None,
                    "last_success_at": None,
                },
                "inventory": {
                    "status": "unknown",
                    "consecutive_failures": 0,
                    "backoff_until": 0,
                    "last_error": None,
                    "last_success_at": None,
                    "effective_source": "unknown",
                },
            }
            self._ctx = self

    track = {"track_id": "track-1", "last_probe_json": {"show": {"name": "Example Show"}}}
    updated, probe = asyncio.run(BotApp._schedule_refresh_track(DummyBot(), track))  # pyright: ignore[reportArgumentType]

    assert probe["metadata_error"] == "tv metadata offline"
    assert updated["track_id"] == "track-1"
    assert updated["last_probe_json"]["metadata_error"] == "tv metadata offline"
    assert int(updated["next_check_at"] or 0) > int(updated["last_probe_at"] or 0)


def test_schedule_qbt_codes_honors_path_equivalent_category_aliases() -> None:
    class DummyQbt:
        def list_categories(self) -> dict[str, dict[str, str]]:
            return {
                "TV": {"savePath": "/srv/tv"},
                "Shows": {"savePath": "/srv/tv"},
                "Movies": {"savePath": "/srv/movies"},
            }

        def list_torrents(self, **_kwargs: object) -> list[dict[str, str]]:
            return [
                {"category": "Shows", "name": "Example.Show.S01E02.1080p"},
                {"category": "Movies", "name": "Example Movie 2024"},
            ]

    class DummyCfg:
        tv_category = "TV"
        tv_path = "/srv/tv"

    class DummyBot:
        def __init__(self) -> None:
            self.qbt = DummyQbt()
            self.cfg = DummyCfg()

        _norm_path = staticmethod(BotApp._norm_path)

        def _qbt_category_aliases(self, primary_category: str, save_path: str) -> set[str]:
            return BotApp._qbt_category_aliases(self, primary_category, save_path)  # pyright: ignore[reportArgumentType]

    codes = BotApp._schedule_qbt_codes_for_show(DummyBot(), "Example Show", 1)  # pyright: ignore[reportArgumentType]
    assert codes == {"S01E02"}


def test_schedule_next_check_ignores_stale_retry_and_uses_future_release_window(monkeypatch) -> None:
    class DummyBot:
        _schedule_release_grace_s = BotApp._schedule_release_grace_s
        _schedule_sanitize_auto_state = BotApp._schedule_sanitize_auto_state
        _schedule_next_check_at = BotApp._schedule_next_check_at

    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 1_700_000_000)

    air_ts = 1_700_000_000 + (8 * 24 * 3600)
    next_check = BotApp._schedule_next_check_at(
        DummyBot(),  # pyright: ignore[reportArgumentType]
        air_ts,
        has_actionable_missing=False,
        auto_state={"next_auto_retry_at": 1_699_000_000},
    )

    assert next_check == air_ts + BotApp._schedule_release_grace_s(DummyBot())  # pyright: ignore[reportArgumentType]


def test_schedule_next_check_uses_future_retry_for_actionable_missing(monkeypatch) -> None:
    class DummyBot:
        _schedule_sanitize_auto_state = BotApp._schedule_sanitize_auto_state
        _schedule_next_check_at = BotApp._schedule_next_check_at

    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 1_700_000_000)

    next_check = BotApp._schedule_next_check_at(
        DummyBot(),  # pyright: ignore[reportArgumentType]
        None,
        has_actionable_missing=True,
        auto_state={"next_auto_retry_at": 1_700_000_900},
    )

    assert next_check == 1_700_000_900


def test_schedule_repair_track_state_clears_stale_retry(monkeypatch) -> None:
    class DummyStore:
        def __init__(self) -> None:
            self.updated: dict[str, object] | None = None

        def update_schedule_track(self, track_id: str, **fields: object) -> None:
            self.updated = {"track_id": track_id, **fields}

    class DummyBot:
        def __init__(self) -> None:
            self.store = DummyStore()

        _schedule_release_grace_s = BotApp._schedule_release_grace_s
        _schedule_sanitize_auto_state = BotApp._schedule_sanitize_auto_state
        _schedule_next_check_at = BotApp._schedule_next_check_at

    monkeypatch.setattr("patchy_bot.bot.now_ts", lambda: 1_700_000_000)

    track = {
        "track_id": "track-1",
        "auto_state_json": {"enabled": True, "next_auto_retry_at": 1_699_000_000, "tracking_mode": "upcoming"},
        "last_probe_json": {"actionable_missing_codes": [], "next_air_ts": 1_700_200_000},
        "next_air_ts": 1_700_200_000,
        "next_check_at": 1_699_000_000,
    }

    bot = DummyBot()
    BotApp._schedule_repair_track_state(bot, track)  # pyright: ignore[reportArgumentType]

    assert bot.store.updated is not None
    assert bot.store.updated["auto_state_json"]["next_auto_retry_at"] is None  # pyright: ignore[reportIndexIssue]
    assert int(bot.store.updated["next_check_at"]) > 1_700_000_000  # pyright: ignore[reportArgumentType]


def test_qbt_transport_status_flags_missing_bound_interface(monkeypatch) -> None:
    class DummyQbt:
        def get_transfer_info(self) -> dict[str, object]:
            return {"connection_status": "connected", "dht_nodes": 42}

        def get_preferences(self) -> dict[str, object]:
            return {"current_network_interface": "surfshark_wg", "current_interface_address": ""}

    class DummyBot:
        def __init__(self) -> None:
            self.qbt = DummyQbt()

    monkeypatch.setattr("os.path.exists", lambda path: False)

    ok, reason = BotApp._qbt_transport_status(DummyBot())  # pyright: ignore[reportArgumentType]
    assert ok is False
    assert "bound interface missing: surfshark_wg" == reason


def test_qbt_transport_status_flags_disconnected_client(monkeypatch) -> None:
    class DummyQbt:
        def get_transfer_info(self) -> dict[str, object]:
            return {"connection_status": "disconnected", "dht_nodes": 0}

        def get_preferences(self) -> dict[str, object]:
            return {"current_network_interface": "enp4s0", "current_interface_address": ""}

    class DummyBot:
        def __init__(self) -> None:
            self.qbt = DummyQbt()

    monkeypatch.setattr("os.path.exists", lambda path: path == "/sys/class/net/enp4s0")
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: io.StringIO("up\n"))

    ok, reason = BotApp._qbt_transport_status(DummyBot())  # pyright: ignore[reportArgumentType]
    assert ok is False
    assert "connection_status=disconnected via enp4s0 (up), dht_nodes=0" == reason


def test_qbt_transport_status_accepts_connected_client(monkeypatch) -> None:
    class DummyQbt:
        def get_transfer_info(self) -> dict[str, object]:
            return {"connection_status": "connected", "dht_nodes": 304}

        def get_preferences(self) -> dict[str, object]:
            return {"current_network_interface": "enp4s0", "current_interface_address": ""}

    class DummyBot:
        def __init__(self) -> None:
            self.qbt = DummyQbt()

    monkeypatch.setattr("os.path.exists", lambda path: path == "/sys/class/net/enp4s0")
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: io.StringIO("up\n"))

    ok, reason = BotApp._qbt_transport_status(DummyBot())  # pyright: ignore[reportArgumentType]
    assert ok is True
    assert "connection_status=connected via enp4s0 (up), dht_nodes=304" == reason


def test_targets_only_include_movies_and_tv() -> None:
    class DummyCfg:
        movies_category = "Movies"
        movies_path = "/srv/movies"
        tv_category = "TV"
        tv_path = "/srv/tv"

    class DummyBot:
        def __init__(self) -> None:
            self.cfg = DummyCfg()

    targets = BotApp._targets(DummyBot())  # pyright: ignore[reportArgumentType]

    assert set(targets) == {"movies", "tv"}
    assert targets["movies"]["path"] == "/srv/movies"
    assert targets["tv"]["path"] == "/srv/tv"


def test_storage_status_no_longer_depends_on_spam_path(monkeypatch) -> None:
    class DummyCfg:
        require_nvme_mount = False
        nvme_mount_path = "/mnt/nvme"
        movies_category = "Movies"
        movies_path = "/srv/movies"
        tv_category = "TV"
        tv_path = "/srv/tv"
        spam_path = "/srv/spam"

    class DummyBot:
        def __init__(self) -> None:
            self.cfg = DummyCfg()

        def _targets(self) -> dict[str, dict[str, str]]:
            return BotApp._targets(self)  # pyright: ignore[reportArgumentType]

    mkdir_calls: list[str] = []

    monkeypatch.setattr("os.makedirs", lambda path, exist_ok=False: mkdir_calls.append(path))
    monkeypatch.setattr("os.path.isdir", lambda path: path in {"/srv/movies", "/srv/tv"})

    ok, reason = BotApp._storage_status(DummyBot())  # pyright: ignore[reportArgumentType]

    assert ok is True
    assert reason == "ready"
    assert "/srv/spam" not in mkdir_calls


def test_storage_probe_paths_prefer_media_paths_before_nvme_mount() -> None:
    class DummyCfg:
        movies_path = "/srv/plex/movies"
        tv_path = "/srv/plex/tv"
        nvme_mount_path = "/mnt/workstation"

    class DummyBot:
        def __init__(self) -> None:
            self.cfg = DummyCfg()

    paths = BotApp._storage_probe_paths(DummyBot())  # pyright: ignore[reportArgumentType]

    assert paths == ["/srv/plex/movies", "/srv/plex/tv", "/mnt/workstation"]


def test_plex_storage_display_uses_media_path_even_if_nvme_mount_differs(monkeypatch) -> None:
    class DummyCfg:
        movies_path = "/srv/plex/movies"
        tv_path = "/srv/plex/tv"
        nvme_mount_path = "/mnt/workstation"

    class DummyBot:
        def __init__(self) -> None:
            self.cfg = DummyCfg()

        _storage_probe_paths = BotApp._storage_probe_paths

        @staticmethod
        def _progress_bar(_pct: float, width: int = 14) -> str:
            return "#" * width

    stat_targets: list[str] = []

    monkeypatch.setattr("os.path.realpath", lambda path: path)
    monkeypatch.setattr("os.path.exists", lambda path: path in {"/srv/plex/movies", "/srv/plex/tv"})
    monkeypatch.setattr("os.path.isdir", lambda path: path in {"/srv/plex/movies", "/srv/plex/tv"})

    def fake_statvfs(path: str) -> SimpleNamespace:
        stat_targets.append(path)
        if path != "/srv/plex/movies":
            raise AssertionError(f"unexpected statvfs path: {path}")
        gib = 1024**3
        return SimpleNamespace(f_frsize=1, f_blocks=100 * gib, f_bfree=40 * gib)

    monkeypatch.setattr("os.statvfs", fake_statvfs)

    text = BotApp._plex_storage_display(DummyBot())  # pyright: ignore[reportArgumentType]

    assert stat_targets == ["/srv/plex/movies"]
    assert "💾 Plex storage:" in text
    assert "60.0%" in text
    assert "43GB" in text


def test_format_remove_season_label_normalizes_season_folder_names() -> None:
    assert format_remove_season_label("Season 01") == "Season 1"
    assert format_remove_season_label("S02") == "Season 2"


def test_format_remove_episode_label_prefers_clean_season_episode_labels() -> None:
    assert format_remove_episode_label("Show.Name.S01E02.1080p.mkv") == "S1 Episode 2"
    assert format_remove_episode_label("Episode 07.mkv", 3) == "S3 Episode 7"


def test_is_remove_media_file_filters_out_release_junk() -> None:
    assert is_remove_media_file("Show.Name.S01E02.1080p.mkv") is True
    assert is_remove_media_file("Downloaded from torrentgalaxy.to.txt") is False
    assert is_remove_media_file("poster.jpg") is False


def test_store_uses_schedule_due_index(tmp_path) -> None:
    import sqlite3 as _sqlite3

    db_path = str(tmp_path / "state.sqlite3")
    Store(db_path)  # creates schema as side effect

    conn = _sqlite3.connect(db_path)
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM schedule_tracks WHERE enabled = 1 AND next_check_at <= ? ORDER BY next_check_at ASC LIMIT ?",
        (0, 5),
    ).fetchall()
    conn.close()

    plan_text = " ".join(str(part) for row in plan for part in row)
    assert "idx_schedule_due" in plan_text


def test_store_schedule_runner_status_round_trip(tmp_path) -> None:
    store = Store(str(tmp_path / "state.sqlite3"))
    store.update_schedule_runner_status(
        last_due_count=2,
        last_processed_count=1,
        metadata_source_health_json={"status": "healthy"},
        inventory_source_health_json={"status": "degraded"},
    )

    status = store.get_schedule_runner_status()

    assert status["last_due_count"] == 2
    assert status["last_processed_count"] == 1
    assert status["metadata_source_health_json"]["status"] == "healthy"
    assert status["inventory_source_health_json"]["status"] == "degraded"


def test_remove_toggle_label_omits_empty_checkbox_prefix() -> None:
    from patchy_bot.handlers.remove import remove_toggle_label

    candidate = {"name": "Season 1", "path": "/srv/tv/Show/Season 1"}

    unselected = remove_toggle_label(candidate, set())
    selected = remove_toggle_label(candidate, {"/srv/tv/Show/Season 1"})

    assert unselected == "Season 1"
    assert selected == "✅ Season 1"


def test_remove_toggle_label_tv_show_uses_show_name() -> None:
    from patchy_bot.handlers.remove import remove_toggle_label

    candidate = {
        "name": "Daredevil.Born.Again.S02E01.1080p.WEB.h264-ETHEL",
        "remove_kind": "show",
        "show_name": "Daredevil Born Again",
        "path": "/srv/tv/Daredevil Born Again",
    }

    assert remove_toggle_label(candidate, set()) == "Daredevil Born Again"


def test_remove_toggle_label_tv_show_no_raw_release_name() -> None:
    from patchy_bot.handlers.remove import remove_toggle_label

    candidate = {
        "name": "Better.Call.Saul.S06E01.1080p.WEB-DL",
        "remove_kind": "show",
        "show_name": None,
        "path": "/srv/tv/Better.Call.Saul.S06E01.1080p.WEB-DL",
    }

    result = remove_toggle_label(candidate, set())

    assert "." not in result
    assert "1080p" not in result
    assert "WEB" not in result


def test_remove_toggle_label_season_multiseason() -> None:
    from patchy_bot.handlers.remove import remove_toggle_label

    candidate = {
        "name": "Season 2",
        "remove_kind": "season",
        "show_name": "Daredevil Born Again",
        "season_number": 2,
        "path": "/srv/tv/Daredevil Born Again/Season 2",
    }

    assert remove_toggle_label(candidate, set()) == "Daredevil Born Again Season 2"


def test_remove_toggle_label_season_selected_prefix() -> None:
    from patchy_bot.handlers.remove import remove_toggle_label

    path = "/srv/tv/Daredevil Born Again/Season 2"
    candidate = {
        "name": "Season 2",
        "remove_kind": "season",
        "show_name": "Daredevil Born Again",
        "season_number": 2,
        "path": path,
    }

    assert remove_toggle_label(candidate, {path}).startswith("✅")


def test_remove_candidate_text_tv_show_no_raw_release_name() -> None:
    from patchy_bot.handlers.remove import remove_candidate_text

    candidate = {
        "name": "Daredevil.Born.Again.S02.1080p",
        "remove_kind": "show",
        "show_name": "Daredevil Born Again",
        "is_dir": True,
        "root_label": "TV",
        "path": "/srv/tv/Daredevil Born Again",
        "size_bytes": 8_000_000_000,
    }

    text = remove_candidate_text(candidate)

    assert "Daredevil Born Again" in text
    assert "Daredevil.Born" not in text
    assert "1080p" not in text


def test_remove_candidate_text_movie_format() -> None:
    from patchy_bot.handlers.remove import remove_candidate_text

    candidate = {
        "name": "The.Dark.Knight.2008.1080p.BluRay",
        "remove_kind": "movie",
        "is_dir": True,
        "root_label": "Movies",
        "path": "/srv/movies/TDK",
        "size_bytes": 10_000_000_000,
    }

    text = remove_candidate_text(candidate)

    assert "The Dark Knight (2008)" in text


def test_extract_movie_name_no_trailing_dots() -> None:
    from patchy_bot.handlers.remove import extract_movie_name

    inputs = [
        "The.Dark.Knight.2008.1080p",
        "Dune.Part.Two.2024.2160p.IMAX",
        "Some.Movie.Without.Year.1080p",
        "www.UIndex.org - Dune.Part.Two.2024.mkv",
    ]

    for value in inputs:
        result = extract_movie_name(value)
        assert "." not in result, f"Dots found in: {result!r} (input: {value!r})"


def test_remove_confirm_keyboard_compacts_small_action_sets_into_two_columns() -> None:
    class DummyBot:
        _nav_footer = BotApp._nav_footer
        _compact_action_rows = staticmethod(BotApp._compact_action_rows)

    keyboard = BotApp._remove_confirm_keyboard(DummyBot(), 1).inline_keyboard  # pyright: ignore[reportArgumentType]

    assert [[button.text for button in row] for row in keyboard] == [
        ["✅ Confirm Delete (1)", "🧹 Clear Selection"],
        ["🏠 Home"],
    ]


def test_home_only_keyboard_contains_home_button() -> None:
    class DummyBot:
        _nav_footer = BotApp._nav_footer

    keyboard = BotApp._home_only_keyboard(DummyBot()).inline_keyboard  # pyright: ignore[reportArgumentType]

    assert [[button.text for button in row] for row in keyboard] == [["🏠 Home"]]


def test_nav_footer_can_omit_home() -> None:
    class DummyBot:
        _nav_footer = BotApp._nav_footer

    rows = BotApp._nav_footer(DummyBot(), back_data="go:back", include_home=False)  # pyright: ignore[reportArgumentType]

    assert [[button.text for button in row] for row in rows] == [["⬅️ Back"]]


def test_remove_prompt_keyboard_compacts_when_five_or_fewer_buttons_are_visible() -> None:
    class DummyBot:
        _nav_footer = BotApp._nav_footer
        _compact_action_rows = staticmethod(BotApp._compact_action_rows)

    keyboard = BotApp._remove_prompt_keyboard(DummyBot(), 1).inline_keyboard  # pyright: ignore[reportArgumentType]

    assert [[button.text for button in row] for row in keyboard] == [
        ["📚 Browse Plex Library", "🧾 Review Selection (1)"],
        ["🧹 Clear Selection", "🏠 Home"],
    ]


def test_remove_season_action_keyboard_keeps_stacked_layout_when_more_than_five_buttons() -> None:
    class DummyBot:
        _nav_footer = BotApp._nav_footer
        _compact_action_rows = staticmethod(BotApp._compact_action_rows)

    keyboard = BotApp._remove_season_action_keyboard(DummyBot(), False, 1).inline_keyboard  # pyright: ignore[reportArgumentType]

    assert [[button.text for button in row] for row in keyboard] == [
        ["🗑 Select Entire Season", "🎞 Browse Episodes"],
        ["🧾 Review Selection (1)"],
        ["🧹 Clear Selection"],
        ["⬅️ Back to Series"],
        ["🏠 Home"],
    ]


def test_remove_show_action_screen_displays_series_selected_in_text_not_button(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_show_action_keyboard, remove_show_actions_text

    show_dir = tmp_path / "Silicon Valley"
    show_dir.mkdir()

    candidate = {
        "name": "Silicon Valley",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
        "is_dir": True,
        "remove_kind": "show",
        "size_bytes": 0,
    }

    text = remove_show_actions_text(candidate, True)
    selected_keyboard = remove_show_action_keyboard(True, 1).inline_keyboard
    unselected_keyboard = remove_show_action_keyboard(False, 1).inline_keyboard

    assert "Entire series is selected for deletion" in text
    assert [[button.text for button in row] for row in selected_keyboard] == [
        ["🧾 Review Selection (1)", "🧹 Clear Selection"],
        ["⬅️ Back", "🏠 Home"],
    ]
    assert [[button.text for button in row] for row in unselected_keyboard] == [
        ["🗑 Select Entire Series", "📂 Browse Seasons"],
        ["🧾 Review Selection (1)"],
        ["🧹 Clear Selection"],
        ["⬅️ Back", "🏠 Home"],
    ]


def test_remove_season_detail_keyboard_uses_back_and_home(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_season_detail_keyboard

    season_dir = tmp_path / "Example Show" / "Season 2"
    season_dir.mkdir(parents=True)
    candidate = {
        "name": "Season 2",
        "remove_kind": "season",
        "show_name": "Example Show",
        "season_number": 2,
        "path": str(season_dir),
    }

    keyboard = remove_season_detail_keyboard(candidate, set(), 0).inline_keyboard

    assert [[button.text for button in row] for row in keyboard] == [
        ["🗑 Delete Season 2"],
        ["📋 Select Episodes"],
        ["◀️ Back", "🏠 Home"],
    ]


def test_remove_season_actions_text_uses_show_and_season_in_header() -> None:
    from patchy_bot.handlers.remove import remove_season_actions_text

    text = remove_season_actions_text(
        {
            "name": "Season 2",
            "remove_kind": "season",
            "show_name": "Example Show",
            "season_number": 2,
            "path": "/tmp/example-show/Season 2",
            "size_bytes": 0,
            "root_label": "TV",
            "is_dir": True,
        }
    )

    assert "<b>📂 Example Show Season 2</b>" in text


def test_remove_browse_movie_list_compacts_footer_without_changing_item_rows(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_paginated_keyboard

    items = [
        {
            "name": f"Movie {idx}",
            "path": str(tmp_path / f"movie-{idx}.mkv"),
            "remove_kind": "movie",
        }
        for idx in range(9)
    ]

    keyboard = remove_paginated_keyboard(
        items,
        0,
        item_prefix="rm:pick",
        nav_prefix="rm:bpage",
        back_callback="rm:browse",
        selected_paths=set(),
        compact_browse_footer=True,
    ).inline_keyboard

    assert [[button.text for button in row] for row in keyboard[-2:]] == [
        ["⬅️ Back", "Next ➡️"],
        ["🏠 Home"],
    ]


def test_remove_browse_movie_list_keeps_selected_footer_actions_available(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_paginated_keyboard

    selected_path = str(tmp_path / "movie-0.mkv")
    items = [
        {
            "name": f"Movie {idx}",
            "path": str(tmp_path / f"movie-{idx}.mkv"),
            "remove_kind": "movie",
        }
        for idx in range(9)
    ]

    keyboard = remove_paginated_keyboard(
        items,
        0,
        item_prefix="rm:pick",
        nav_prefix="rm:bpage",
        back_callback="rm:browse",
        selected_paths={selected_path},
        compact_browse_footer=True,
    ).inline_keyboard

    assert [[button.text for button in row] for row in keyboard[-5:]] == [
        ["Next ➡️"],
        ["🧾 Review Selection (1)"],
        ["🧹 Clear Selection"],
        ["⬅️ Back"],
        ["🏠 Home"],
    ]
    assert keyboard[-2][0].text == "⬅️ Back"
    assert keyboard[-2][0].callback_data == "rm:browse"
    assert keyboard[-1][0].text == "🏠 Home"


def test_remove_show_action_screen_defaults_to_unselected_series_state(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_show_actions_text

    show_dir = tmp_path / "Silicon Valley"
    show_dir.mkdir()

    candidate = {
        "name": "Silicon Valley",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
        "is_dir": True,
        "remove_kind": "show",
        "size_bytes": 0,
    }

    text = remove_show_actions_text(candidate, False)

    assert "Entire series is not currently selected" in text


def test_remove_child_builders_use_clean_season_and_episode_names(tmp_path) -> None:
    show_dir = tmp_path / "Example Show"
    season_dir = show_dir / "Season 02"
    season_dir.mkdir(parents=True)
    (show_dir / "Subs").mkdir()
    (show_dir / "Downloaded from torrentgalaxy.to.txt").write_text("junk")
    (show_dir / "Example.Show.S04E01.1080p.mkv").write_text("x")
    episode_path = season_dir / "Example.Show.S02E03.1080p.mkv"
    episode_path.write_text("x")
    (season_dir / "RARBG.txt").write_text("junk")

    class DummyBot:
        pass

    show_candidate = {
        "name": "Example Show",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
    }

    season_items = BotApp._remove_show_children(DummyBot(), show_candidate)  # pyright: ignore[reportArgumentType]
    assert [item["name"] for item in season_items] == ["Season 2", "Season 4"]
    assert season_items[0]["season_number"] == 2
    assert season_items[1]["is_virtual"] is True
    assert all(item["name"] != "Subs" for item in season_items)

    episode_items = BotApp._remove_season_children(DummyBot(), season_items[0])  # pyright: ignore[reportArgumentType]
    assert len(episode_items) == 1
    assert episode_items[0]["name"] == "S2 Episode 3"
    assert BotApp._remove_season_children(DummyBot(), season_items[1])[0]["name"] == "S4 Episode 1"  # pyright: ignore[reportArgumentType]
    assert all("txt" not in item["name"].lower() for item in episode_items)


def test_remove_show_children_groups_loose_episodes_into_season_buckets(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_season_children, remove_show_children

    show_dir = tmp_path / "Daredevil Born Again"
    season_dir = show_dir / "Season 1"
    season_dir.mkdir(parents=True)
    (show_dir / "www.UIndex.org - Daredevil.Born.Again.S01E02.1080p.mkv").write_text("x")
    (show_dir / "www.UIndex.org - Daredevil.Born.Again.S02E01.1080p.mkv").write_text("x")
    (show_dir / "Daredevil.Born.Again.E05.1080p.mkv").write_text("x")

    show_candidate = {
        "name": "Daredevil Born Again",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
    }

    season_items = remove_show_children(show_candidate)

    assert [item["name"] for item in season_items] == ["Season 1", "Season 2", "Unsorted Episodes"]
    assert season_items[0]["is_virtual"] is False
    assert [item["name"] for item in season_items[0]["extra_episode_items"]] == ["S1 Episode 2"]
    assert season_items[1]["is_virtual"] is True
    assert [item["name"] for item in remove_season_children(season_items[1])] == ["S2 Episode 1"]
    assert [item["name"] for item in remove_season_children(season_items[2])] == ["Episode 5"]


def test_remove_show_group_children_groups_loose_files_without_raw_names(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_season_children, remove_show_group_children

    episode_path = tmp_path / "www.UIndex.org - Daredevil.Born.Again.S02E01.1080p.mkv"
    episode_path.write_text("x")
    unsorted_path = tmp_path / "Daredevil.Born.Again.Special.1080p.mkv"
    unsorted_path.write_text("x")

    group_items = [
        {
            "name": "Daredevil Born Again",
            "source_name": episode_path.name,
            "path": str(episode_path),
            "root_key": "tv",
            "root_label": "TV",
            "root_path": str(tmp_path),
            "is_dir": False,
            "size_bytes": None,
            "remove_kind": "episode",
            "show_name": "Daredevil Born Again",
            "season_number": 2,
        },
        {
            "name": "Daredevil Born Again",
            "source_name": unsorted_path.name,
            "path": str(unsorted_path),
            "root_key": "tv",
            "root_label": "TV",
            "root_path": str(tmp_path),
            "is_dir": False,
            "size_bytes": None,
            "remove_kind": "episode",
            "show_name": "Daredevil Born Again",
            "season_number": None,
        },
    ]

    season_items = remove_show_group_children(group_items)

    assert [item["name"] for item in season_items] == ["Season 2", "Unsorted Episodes"]
    assert [item["name"] for item in remove_season_children(season_items[0])] == ["S2 Episode 1"]
    assert "UIndex" not in remove_season_children(season_items[0])[0]["name"]


def test_remove_confirm_text_uses_explicit_tv_scope_labels() -> None:
    from patchy_bot.handlers.remove import remove_confirm_name

    assert (
        remove_confirm_name(
            {
                "name": "Daredevil Born Again",
                "remove_kind": "show",
                "show_name": "Daredevil Born Again",
            }
        )
        == "Daredevil Born Again Full Series"
    )
    assert (
        remove_confirm_name(
            {
                "name": "Season 1",
                "remove_kind": "season",
                "show_name": "Daredevil Born Again",
                "season_number": 1,
            }
        )
        == "Daredevil Born Again Season 1"
    )
    assert (
        remove_confirm_name(
            {
                "name": "S1 Episode 2",
                "source_name": "Daredevil.Born.Again.S01E02.1080p.mkv",
                "remove_kind": "episode",
                "show_name": "Daredevil Born Again",
                "season_number": 1,
            }
        )
        == "Daredevil Born Again S01E02"
    )


def test_remove_confirm_text_collapses_duplicate_show_folders_into_one_full_series_entry(tmp_path) -> None:
    from patchy_bot.handlers.remove import (
        remove_confirm_summary_items,
        remove_confirm_text,
        remove_selected_show_candidate,
        remove_selection_count,
    )

    first = tmp_path / "Daredevil Born Again"
    second = tmp_path / "www.UIndex.org - Daredevil Born Again"
    third = tmp_path / "Daredevil Born Again Alt"
    first.mkdir()
    second.mkdir()
    third.mkdir()

    candidates = [
        {
            "name": "Daredevil Born Again",
            "path": str(first),
            "root_key": "tv",
            "root_label": "TV",
            "root_path": str(tmp_path),
            "is_dir": True,
            "remove_kind": "show",
            "show_name": "Daredevil Born Again",
            "size_bytes": 10,
        },
        {
            "name": "www.UIndex.org - Daredevil Born Again",
            "path": str(second),
            "root_key": "tv",
            "root_label": "TV",
            "root_path": str(tmp_path),
            "is_dir": True,
            "remove_kind": "show",
            "show_name": "Daredevil Born Again",
            "size_bytes": 20,
        },
        {
            "name": "Daredevil Born Again Alt",
            "path": str(third),
            "root_key": "tv",
            "root_label": "TV",
            "root_path": str(tmp_path),
            "is_dir": True,
            "remove_kind": "show",
            "show_name": "Daredevil Born Again",
            "size_bytes": 30,
        },
    ]

    summary = remove_confirm_summary_items(candidates)
    text = remove_confirm_text(candidates)

    assert len(summary) == 1
    assert summary[0]["name"] == "Daredevil Born Again Full Series"
    assert summary[0]["size_bytes"] == 60
    assert "Selected <b>1</b> item(s)" in text
    assert text.count("Daredevil Born Again Full Series") == 2
    assert remove_selection_count({"selected_items": candidates}) == 1
    assert remove_selected_show_candidate({"selected": candidates[0]}) is not None
    assert remove_selected_show_candidate({"selected": {"remove_kind": "movie"}}) is None


def test_remove_virtual_season_toggle_selects_underlying_episode_files(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_selection_items, remove_show_children, remove_toggle_candidate

    show_dir = tmp_path / "Example Show"
    show_dir.mkdir()
    first = show_dir / "Example.Show.S02E01.1080p.mkv"
    second = show_dir / "Example.Show.S02E02.1080p.mkv"
    first.write_text("x")
    second.write_text("x")

    show_candidate = {
        "name": "Example Show",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
    }
    virtual_season = remove_show_children(show_candidate)[0]
    flow = {"selected_items": []}

    assert remove_toggle_candidate(flow, virtual_season) is True
    assert sorted(item["path"] for item in remove_selection_items(flow)) == sorted([str(first), str(second)])
    assert remove_toggle_candidate(flow, virtual_season) is False
    assert remove_selection_items(flow) == []


def test_remove_season_detail_keyboard_marks_virtual_season_selected(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_season_detail_keyboard, remove_show_children, remove_toggle_candidate

    show_dir = tmp_path / "Example Show"
    show_dir.mkdir()
    episode_path = show_dir / "Example.Show.S02E03.1080p.mkv"
    episode_path.write_text("x")

    show_candidate = {
        "name": "Example Show",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
    }
    virtual_season = remove_show_children(show_candidate)[0]
    flow = {"selected_items": []}
    remove_toggle_candidate(flow, virtual_season)

    keyboard = remove_season_detail_keyboard(virtual_season, {str(episode_path)}, 0).inline_keyboard

    assert keyboard[0][0].text == "✅ Season 2 Selected"


def test_plex_refresh_for_path_uses_post_with_path_parameter(tmp_path) -> None:
    class FakeResponse:
        def __init__(self, status_code: int = 200, text: str = "") -> None:
            self.status_code = status_code
            self.text = text

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, object], dict[str, str]]] = []

        def request(
            self,
            method: str,
            url: str,
            *,
            params: dict[str, object] | None = None,
            headers: dict[str, str] | None = None,
            timeout: int | None = None,
        ) -> FakeResponse:
            self.calls.append((method, url, dict(params or {}), dict(headers or {})))
            return FakeResponse()

    movies_root = tmp_path / "Movies"
    movie_dir = movies_root / "Example Movie (2024)"
    movie_dir.mkdir(parents=True)

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")
    fake_session = FakeSession()
    client.session = fake_session  # type: ignore[assignment]
    client._sections = lambda: [  # type: ignore[method-assign]
        {
            "key": "2",
            "title": "Movies",
            "type": "movie",
            "locations": [str(movies_root)],
            "refreshing": False,
        }
    ]

    msg = client.refresh_for_path(str(movie_dir))

    assert msg == "Plex scan triggered for Movies"
    assert len(fake_session.calls) == 1
    method, url, params, headers = fake_session.calls[0]
    assert method == "POST"
    assert url == "http://plex.local:32400/library/sections/2/refresh"
    assert params == {"path": str(movie_dir)}
    assert headers.get("X-Plex-Token") == "token-123"  # pyright: ignore[reportOptionalMemberAccess]


def test_plex_purge_deleted_path_refreshes_parent_then_empties_trash(tmp_path, monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, status_code: int = 200, text: str = "") -> None:
            self.status_code = status_code
            self.text = text

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, object], dict[str, str]]] = []

        def request(
            self,
            method: str,
            url: str,
            *,
            params: dict[str, object] | None = None,
            headers: dict[str, str] | None = None,
            timeout: int | None = None,
        ) -> FakeResponse:
            self.calls.append((method, url, dict(params or {}), dict(headers or {})))
            return FakeResponse()

    tv_root = tmp_path / "TV"
    season_dir = tv_root / "Example Show" / "Season 01"
    season_dir.mkdir(parents=True)
    deleted_episode = season_dir / "Example.Show.S01E02.1080p.mkv"

    client = PlexInventoryClient("http://plex.local:32400", "token-123", str(tv_root))
    fake_session = FakeSession()
    client.session = fake_session  # type: ignore[assignment]
    monkeypatch.setattr("patchy_bot.clients.plex.time.sleep", lambda _seconds: None)

    sections = [
        [
            {
                "key": "5",
                "title": "TV Shows",
                "type": "show",
                "locations": [str(tv_root)],
                "refreshing": False,
            }
        ],
        [
            {
                "key": "5",
                "title": "TV Shows",
                "type": "show",
                "locations": [str(tv_root)],
                "refreshing": True,
            }
        ],
        [
            {
                "key": "5",
                "title": "TV Shows",
                "type": "show",
                "locations": [str(tv_root)],
                "refreshing": False,
            }
        ],
    ]

    def fake_sections() -> list[dict[str, object]]:
        if sections:
            return sections.pop(0)
        return [
            {
                "key": "5",
                "title": "TV Shows",
                "type": "show",
                "locations": [str(tv_root)],
                "refreshing": False,
            }
        ]

    client._sections = fake_sections  # type: ignore[method-assign]

    msg = client.purge_deleted_path(str(deleted_episode))

    assert msg == "Plex scan and trash empty completed for TV Shows"
    assert len(fake_session.calls) == 2
    # Verify refresh call
    method, url, params, headers = fake_session.calls[0]
    assert method == "POST"
    assert url == "http://plex.local:32400/library/sections/5/refresh"
    assert params == {"path": str(season_dir)}
    assert headers.get("X-Plex-Token") == "token-123"  # pyright: ignore[reportOptionalMemberAccess]
    # Verify emptyTrash call
    method, url, params, headers = fake_session.calls[1]
    assert method == "PUT"
    assert url == "http://plex.local:32400/library/sections/5/emptyTrash"
    assert headers.get("X-Plex-Token") == "token-123"  # pyright: ignore[reportOptionalMemberAccess]


def test_plex_verify_remove_identity_absent_for_show_requires_show_metadata_to_disappear() -> None:
    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")
    client._metadata_exists = lambda rating_key: rating_key == "show-1"  # type: ignore[method-assign]

    ok, detail = client.verify_remove_identity_absent(
        "/srv/tv/Example Show",
        "show",
        {
            "verification_mode": "show",
            "rating_keys": ["show-1"],
            "title": "Example Show",
            "section_key": "5",
        },
    )

    assert ok is False
    assert detail == "Plex still has show metadata for Example Show"


def test_remove_show_children_sorts_seasons_by_parsed_number(tmp_path) -> None:
    show_dir = tmp_path / "Game of Thrones"
    show_dir.mkdir()
    (show_dir / "Season 1").mkdir()
    (show_dir / "Season 2").mkdir()
    (show_dir / "S04").mkdir()
    (show_dir / "Season.3").mkdir()

    class DummyBot:
        pass

    show_candidate = {
        "name": "Game of Thrones",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
    }

    season_items = BotApp._remove_show_children(DummyBot(), show_candidate)  # pyright: ignore[reportArgumentType]

    assert [item["name"] for item in season_items] == ["Season 1", "Season 2", "Season 3", "Season 4"]


def test_remove_candidate_keyboard_single_season_no_season_suffix(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_candidate_keyboard

    show_dir = tmp_path / "Severance"
    season_dir = show_dir / "Season 1"
    season_dir.mkdir(parents=True)
    (season_dir / "Severance.S01E01.1080p.mkv").write_text("x")

    candidate = {
        "name": "Severance",
        "remove_kind": "show",
        "show_name": "Severance",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
        "is_dir": True,
        "size_bytes": None,
    }

    markup = remove_candidate_keyboard([candidate], set())
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert any(label == "Severance" for label in labels), f"Expected plain show name button, got: {labels}"
    assert not any(label == "Severance Season 1" for label in labels)


def test_remove_candidate_keyboard_multi_season_has_season_suffix(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_candidate_keyboard

    show_dir = tmp_path / "Breaking Bad"
    for number in [1, 2, 3]:
        season_dir = show_dir / f"Season {number}"
        season_dir.mkdir(parents=True)
        (season_dir / f"BreakingBad.S0{number}E01.mkv").write_text("x")

    candidate = {
        "name": "Breaking Bad",
        "remove_kind": "show",
        "show_name": "Breaking Bad",
        "path": str(show_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
        "is_dir": True,
        "size_bytes": None,
    }

    markup = remove_candidate_keyboard([candidate], set())
    labels = [button.text for row in markup.inline_keyboard for button in row]

    assert any("Season 1" in label for label in labels)
    assert any("Season 2" in label for label in labels)
    assert any("Season 3" in label for label in labels)


def test_store_remove_job_round_trip(tmp_path) -> None:
    store = Store(str(tmp_path / "state.sqlite3"))

    created = store.create_remove_job(
        user_id=77,
        chat_id=88,
        item_name="Example Show",
        root_key="tv",
        root_label="TV",
        remove_kind="show",
        target_path="/srv/tv/Example Show",
        root_path="/srv/tv",
        scan_path="/srv/tv",
        plex_section_key="5",
        plex_rating_key="show-1",
        plex_title="Example Show",
        verification_json={"rating_keys": ["show-1"], "verification_mode": "show"},
        status="plex_pending",
        disk_deleted_at=1_700_000_000,
        next_retry_at=1_700_000_030,
    )

    fetched = store.get_remove_job(created["job_id"])

    assert fetched is not None
    assert fetched["item_name"] == "Example Show"
    assert fetched["verification_json"]["rating_keys"] == ["show-1"]
    assert fetched["status"] == "plex_pending"


def test_delete_remove_candidates_surfaces_pending_plex_cleanup(monkeypatch) -> None:
    import patchy_bot.handlers.remove as _rm

    def fake_delete(ctx, candidate, *, user_id=None, chat_id=None):
        return {
            "name": str(candidate["name"]),
            "root_label": str(candidate["root_label"]),
            "size_bytes": int(candidate["size_bytes"]),
            "path": str(candidate["path"]),
            "disk_status": "deleted",
            "plex_status": "plex_pending",
            "plex_note": "Plex cleanup still pending for Example Show",
            "remove_kind": str(candidate["remove_kind"]),
        }

    monkeypatch.setattr(_rm, "delete_remove_candidate", fake_delete)

    ctx = SimpleNamespace()

    text = _rm.delete_remove_candidates(
        ctx,  # pyright: ignore[reportArgumentType]
        [
            {
                "name": "Example Show",
                "root_label": "TV",
                "size_bytes": 123,
                "path": "/srv/tv/Example Show",
                "remove_kind": "show",
            }
        ],
    )

    assert text.startswith("⚠️ Batch delete completed with follow-up")
    assert "Disk deleted: 1/1 item(s)" in text
    assert "Plex cleanup pending:" in text
    assert "Example Show: Plex cleanup still pending for Example Show" in text


def test_remove_season_children_sorts_episode_numbers_numerically(tmp_path) -> None:
    season_dir = tmp_path / "Season 01"
    season_dir.mkdir()
    (season_dir / "Show.S01E10.1080p.mkv").write_text("x")
    (season_dir / "Show.S01E02.1080p.mkv").write_text("x")
    (season_dir / "Show.S01E01.1080p.mkv").write_text("x")

    class DummyBot:
        pass

    season_candidate = {
        "name": "Season 1",
        "path": str(season_dir),
        "root_key": "tv",
        "root_label": "TV",
        "root_path": str(tmp_path),
        "show_name": "Example Show",
        "show_path": str(tmp_path / "Example Show"),
        "season_number": 1,
    }

    episode_items = BotApp._remove_season_children(DummyBot(), season_candidate)  # pyright: ignore[reportArgumentType]

    assert [item["name"] for item in episode_items] == ["S1 Episode 1", "S1 Episode 2", "S1 Episode 10"]


def test_remove_library_and_search_candidates_skip_non_media_files(tmp_path) -> None:
    movies_dir = tmp_path / "movies"
    tv_dir = tmp_path / "tv"
    movies_dir.mkdir()
    tv_dir.mkdir()
    (movies_dir / "Movie.One.2024.mkv").write_text("x")
    (movies_dir / "Movie.One.2024.txt").write_text("junk")
    (tv_dir / "Show.Name.S01E02.1080p.mkv").write_text("x")
    (tv_dir / "Show.Name.readme.txt").write_text("junk")

    cfg = SimpleNamespace(
        movies_path=str(movies_dir),
        tv_path=str(tv_dir),
        spam_path="",
    )

    class DummyBot:
        _remove_library_items = BotApp._remove_library_items
        _find_remove_candidates = BotApp._find_remove_candidates
        _ctx = SimpleNamespace(cfg=cfg)

    bot = DummyBot()
    movie_items = BotApp._remove_library_items(bot, "movies")  # pyright: ignore[reportArgumentType]
    tv_items = BotApp._remove_library_items(bot, "tv")  # pyright: ignore[reportArgumentType]
    search_items = BotApp._find_remove_candidates(bot, "Show Name")  # pyright: ignore[reportArgumentType]

    assert [item["name"] for item in movie_items] == ["Movie.One.2024.mkv"]
    assert [item["name"] for item in tv_items] == ["S1 Episode 2"]
    assert [item["name"] for item in search_items] == ["S1 Episode 2"]


def test_find_remove_candidates_groups_duplicate_tv_show_dirs(tmp_path) -> None:
    tv_dir = tmp_path / "tv"
    tv_dir.mkdir()
    primary_show = tv_dir / "Daredevil Born Again"
    pack_one = tv_dir / "Daredevil.Born.Again.S01.1080p"
    pack_two = tv_dir / "Daredevil.Born.Again.S02.1080p"
    (primary_show / "Season 1").mkdir(parents=True)
    (primary_show / "Season 2").mkdir(parents=True)
    pack_one.mkdir()
    pack_two.mkdir()
    (primary_show / "Season 1" / "ep1.mkv").write_text("a" * 10)
    (primary_show / "Season 2" / "ep1.mkv").write_text("b" * 20)
    (pack_one / "ep1.mkv").write_text("c" * 30)
    (pack_two / "ep1.mkv").write_text("d" * 40)

    cfg = SimpleNamespace(
        movies_path="",
        tv_path=str(tv_dir),
        spam_path="",
    )

    class DummyBot:
        _find_remove_candidates = BotApp._find_remove_candidates
        _ctx = SimpleNamespace(cfg=cfg)

    bot = DummyBot()
    search_items = BotApp._find_remove_candidates(bot, "Daredevil Born Again")  # pyright: ignore[reportArgumentType]

    assert len(search_items) == 1
    assert search_items[0]["name"] == "Daredevil Born Again"
    assert len(search_items[0]["group_items"]) == 3
    assert search_items[0]["size_bytes"] == 100


def test_remove_show_group_children_formats_direct_episode_files(tmp_path) -> None:
    from patchy_bot.handlers.remove import remove_season_children

    show_file = tmp_path / "Show.Name.S01E02.1080p.mkv"
    show_file.write_text("x")

    class DummyBot:
        _remove_show_children = BotApp._remove_show_children
        _extract_show_name = staticmethod(BotApp._extract_show_name)

    grouped_children = BotApp._remove_show_group_children(
        DummyBot(),  # pyright: ignore[reportArgumentType]
        [
            {
                "name": "Show.Name.S01E02.1080p.mkv",
                "path": str(show_file),
                "root_key": "tv",
                "root_label": "TV",
                "root_path": str(tmp_path),
                "is_dir": False,
            }
        ],
    )

    assert [item["name"] for item in grouped_children] == ["Season 1"]
    assert [item["name"] for item in remove_season_children(grouped_children[0])] == ["S1 Episode 2"]


def test_extract_show_name_hides_release_group_noise_aggressively() -> None:
    assert BotApp._extract_show_name("www.1TamilMV.foo - Severance.S02.1080p.NF.WEB-DL.DDP5.1.H.264-NTb") == "Severance"
    assert BotApp._extract_show_name("The.Last.of.Us.2023.S01.2160p.UHD.BluRay.x265-TGx") == "The Last of Us"
    assert BotApp._extract_show_name("Andor Season 2 [AMZN][WEB-DL][1080p]") == "Andor"


def test_render_remove_ui_edits_existing_remove_message() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            return DummyMessage(self, int(kwargs["chat_id"]), int(kwargs["message_id"]))  # pyright: ignore[reportArgumentType]

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 999)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _render_flow_ui = BotApp._render_flow_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {
        "mode": "remove",
        "stage": "choose_item",
        "selected_items": [],
        "remove_ui_chat_id": 100,
        "remove_ui_message_id": 321,
    }

    rendered = asyncio.run(BotApp._render_remove_ui(app, 77, anchor, flow, "Updated remove UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 321
    assert len(bot_api.edit_calls) == 1
    assert anchor.reply_calls == []
    assert app.user_flow[77]["remove_ui_message_id"] == 321


def test_render_remove_ui_falls_back_to_new_message_when_edit_fails() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            raise TelegramError("message to edit not found")

        async def edit_message_reply_markup(self, **kwargs: object):
            pass

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 555)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _render_flow_ui = BotApp._render_flow_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {
        "mode": "remove",
        "stage": "choose_item",
        "selected_items": [],
        "remove_ui_chat_id": 100,
        "remove_ui_message_id": 321,
    }

    rendered = asyncio.run(BotApp._render_remove_ui(app, 77, anchor, flow, "Updated remove UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 555
    assert len(bot_api.edit_calls) == 1
    assert len(anchor.reply_calls) == 1
    assert app.user_flow[77]["remove_ui_message_id"] == 555


def test_render_command_center_edits_existing_message() -> None:
    class DummyMessage:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []
            self.reply_calls: list[dict[str, object]] = []

        async def edit_text(self, text: str, **kwargs: object):
            self.edit_calls.append({"text": text, **kwargs})
            return "edited"

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return "replied"

    class DummyBot:
        _render_command_center = BotApp._render_command_center

        @staticmethod
        def _ensure_media_categories() -> tuple[bool, str]:
            return True, "ready"

        @staticmethod
        def _start_text(storage_ok: bool, storage_reason: str) -> str:
            return f"center ok={storage_ok} reason={storage_reason}"

        @staticmethod
        def _command_center_keyboard():
            return "keyboard"

    msg = DummyMessage()
    result = asyncio.run(BotApp._render_command_center(DummyBot(), msg))  # pyright: ignore[reportArgumentType]

    assert result == "edited"
    assert msg.reply_calls == []
    assert msg.edit_calls == [{"text": "center ok=True reason=ready", "reply_markup": "keyboard", "parse_mode": "HTML"}]


def test_promote_stale_inline_ui_reposts_keyboard_and_disables_old_message() -> None:
    """Inline UI promotion was removed — the nav-UI system replaced it.
    This test validates that _render_nav_ui can re-send a message when the
    prior nav-UI location is stale (edit fails, so it falls back to reply)."""

    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            raise TelegramError("message to edit not found")

        async def edit_message_reply_markup(self, **kwargs: object):
            pass

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 901)

    class DummyApp:
        _remember_nav_ui_message = BotApp._remember_nav_ui_message
        _render_nav_ui = BotApp._render_nav_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

        def __init__(self) -> None:
            self.user_nav_ui: dict[int, dict[str, int]] = {77: {"chat_id": 100, "message_id": 200}}

        class store:
            @staticmethod
            def save_command_center(user_id, chat_id, message_id):
                pass

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 300)

    promoted = asyncio.run(BotApp._render_nav_ui(app, 77, anchor, "Old command center", reply_markup="keyboard"))  # pyright: ignore[reportArgumentType]

    assert promoted.message_id == 901
    assert len(bot_api.edit_calls) == 1
    assert len(anchor.reply_calls) == 1
    assert app.user_nav_ui[77] == {"chat_id": 100, "message_id": 901}


def test_promote_stale_inline_ui_noops_for_latest_message() -> None:
    """When the nav-UI message is still reachable, _render_nav_ui edits it in-place."""

    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            return DummyMessage(self, int(kwargs["chat_id"]), int(kwargs["message_id"]))  # pyright: ignore[reportArgumentType]

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 902)

    class DummyApp:
        _remember_nav_ui_message = BotApp._remember_nav_ui_message
        _render_nav_ui = BotApp._render_nav_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

        def __init__(self) -> None:
            self.user_nav_ui: dict[int, dict[str, int]] = {77: {"chat_id": 100, "message_id": 500}}

        class store:
            @staticmethod
            def save_command_center(user_id, chat_id, message_id):
                pass

    app = DummyApp()
    bot_api = DummyBotApi()
    current_message = DummyMessage(bot_api, 100, 300)

    result = asyncio.run(
        BotApp._render_nav_ui(app, 77, current_message, "Current command center", reply_markup="keyboard")  # pyright: ignore[reportArgumentType]
    )

    assert result.message_id == 500
    assert len(bot_api.edit_calls) == 1
    assert current_message.reply_calls == []


def test_open_remove_browse_root_skips_search_or_browse_landing_screen() -> None:
    class DummyBot:
        _open_remove_browse_root = BotApp._open_remove_browse_root
        _set_flow = BotApp._set_flow
        _get_flow = BotApp._get_flow
        _remove_selection_count = BotApp._remove_selection_count

        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)
            self.render_calls: list[dict[str, object]] = []

        def _remove_library_items(self, root_key: str) -> list[dict[str, object]]:
            if root_key == "movies":
                return [{"name": "Movie 1"}, {"name": "Movie 2"}]
            if root_key == "tv":
                return [{"name": "Show 1"}]
            return []

        def _remove_browse_root_keyboard(self, movie_count: int, show_count: int, selected_count: int = 0):
            return {"movie_count": movie_count, "show_count": show_count, "selected_count": selected_count}

        async def _render_remove_ui(
            self, user_id: int, msg, flow, text: str, reply_markup=None, current_ui_message=None
        ):
            self.render_calls.append(
                {
                    "user_id": user_id,
                    "msg": msg,
                    "flow": dict(flow),
                    "text": text,
                    "reply_markup": reply_markup,
                    "current_ui_message": current_ui_message,
                }
            )

    bot = DummyBot()
    msg = object()

    asyncio.run(BotApp._open_remove_browse_root(bot, 77, msg))  # pyright: ignore[reportArgumentType]

    assert bot.user_flow[77]["stage"] == "browse_root"
    assert bot.render_calls == [
        {
            "user_id": 77,
            "msg": msg,
            "flow": {"mode": "remove", "stage": "browse_root", "selected_items": []},
            "text": "📚 <b>Browse Plex/library items</b>\n\nChoose a library to browse, or <b>type any movie or show name</b> and the bot will find it for you directly.",
            "reply_markup": {"movie_count": 2, "show_count": 1, "selected_count": 0},
            "current_ui_message": None,
        }
    ]


def test_on_callback_remove_cancel_returns_to_command_center() -> None:
    class DummyMessage:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []
            self.reply_calls: list[dict[str, object]] = []

        async def edit_text(self, text: str, **kwargs: object):
            self.edit_calls.append({"text": text, **kwargs})
            return self

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return self

    class DummyQuery:
        def __init__(self, message: DummyMessage) -> None:
            self.data = "rm:cancel"
            self.message = message
            self.answer_calls: list[dict[str, object]] = []

        async def answer(self, text: str | None = None, show_alert: bool = False):
            self.answer_calls.append({"text": text, "show_alert": show_alert})

        def get_bot(self):
            return None

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self, query: DummyQuery) -> None:
            self.callback_query = query
            self.effective_user = DummyUser()

    class DummyBot:
        on_callback = BotApp.on_callback
        _render_command_center = BotApp._render_command_center
        _on_cb_nav_home = BotApp._on_cb_nav_home
        _on_cb_add = BotApp._on_cb_add
        _on_cb_download = BotApp._on_cb_download
        _on_cb_page = BotApp._on_cb_page
        _on_cb_remove = BotApp._on_cb_remove
        _on_cb_schedule = BotApp._on_cb_schedule
        _on_cb_movie_schedule = BotApp._on_cb_movie_schedule
        _on_cb_menu = BotApp._on_cb_menu
        _on_cb_flow = BotApp._on_cb_flow
        _on_cb_mwblock = BotApp._on_cb_mwblock
        _on_cb_stop = BotApp._on_cb_stop
        _on_cb_dl_manage = BotApp._on_cb_dl_manage
        _on_cb_tvpost = BotApp._on_cb_tvpost
        _on_cb_moviepost = BotApp._on_cb_moviepost
        _on_cb_tv_pick = BotApp._on_cb_tv_pick
        _on_cb_movie_pick = BotApp._on_cb_movie_pick
        _on_cb_fsd = BotApp._on_cb_fsd
        _register_callbacks = BotApp._register_callbacks

        def __init__(self) -> None:
            from patchy_bot.dispatch import CallbackDispatcher

            self.cleared: list[int] = []
            self.user_ephemeral_messages: dict[int, list] = {}
            self._dispatcher = CallbackDispatcher()
            self._register_callbacks()

        @staticmethod
        def is_allowed(_update) -> bool:
            return True

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        def _clear_flow(self, user_id: int) -> None:
            self.cleared.append(user_id)

        async def _cleanup_ephemeral_messages(self, user_id, bot):
            self.user_ephemeral_messages.pop(user_id, None)

        @staticmethod
        def _ensure_media_categories() -> tuple[bool, str]:
            return True, "ready"

        @staticmethod
        def _start_text(storage_ok: bool, storage_reason: str) -> str:
            return f"center ok={storage_ok} reason={storage_reason}"

        @staticmethod
        def _command_center_keyboard():
            return "keyboard"

        def _start_command_center_refresh(self, user_id):
            pass

        def _stop_command_center_refresh(self, user_id):
            pass

    message = DummyMessage()
    query = DummyQuery(message)
    update = DummyUpdate(query)
    bot = DummyBot()

    asyncio.run(BotApp.on_callback(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert bot.cleared == [77]
    assert query.answer_calls == [{"text": None, "show_alert": False}]
    assert message.reply_calls == []
    assert message.edit_calls == [
        {"text": "center ok=True reason=ready", "reply_markup": "keyboard", "parse_mode": "HTML"}
    ]


def test_on_callback_schedule_cancel_returns_to_command_center() -> None:
    class DummyMessage:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []
            self.reply_calls: list[dict[str, object]] = []

        async def edit_text(self, text: str, **kwargs: object):
            self.edit_calls.append({"text": text, **kwargs})
            return self

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return self

    class DummyQuery:
        def __init__(self, message: DummyMessage) -> None:
            self.data = "sch:cancel"
            self.message = message
            self.answer_calls: list[dict[str, object]] = []

        async def answer(self, text: str | None = None, show_alert: bool = False):
            self.answer_calls.append({"text": text, "show_alert": show_alert})

        def get_bot(self):
            return None

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self, query: DummyQuery) -> None:
            self.callback_query = query
            self.effective_user = DummyUser()

    class DummyBot:
        on_callback = BotApp.on_callback
        _render_command_center = BotApp._render_command_center
        _on_cb_nav_home = BotApp._on_cb_nav_home
        _on_cb_add = BotApp._on_cb_add
        _on_cb_download = BotApp._on_cb_download
        _on_cb_page = BotApp._on_cb_page
        _on_cb_remove = BotApp._on_cb_remove
        _on_cb_schedule = BotApp._on_cb_schedule
        _on_cb_movie_schedule = BotApp._on_cb_movie_schedule
        _on_cb_menu = BotApp._on_cb_menu
        _on_cb_flow = BotApp._on_cb_flow
        _on_cb_mwblock = BotApp._on_cb_mwblock
        _on_cb_stop = BotApp._on_cb_stop
        _on_cb_dl_manage = BotApp._on_cb_dl_manage
        _on_cb_tvpost = BotApp._on_cb_tvpost
        _on_cb_moviepost = BotApp._on_cb_moviepost
        _on_cb_tv_pick = BotApp._on_cb_tv_pick
        _on_cb_movie_pick = BotApp._on_cb_movie_pick
        _on_cb_fsd = BotApp._on_cb_fsd
        _register_callbacks = BotApp._register_callbacks

        def __init__(self) -> None:
            from patchy_bot.dispatch import CallbackDispatcher

            self.cleared: list[int] = []
            self.user_ephemeral_messages: dict[int, list] = {}
            self._dispatcher = CallbackDispatcher()
            self._register_callbacks()

        @staticmethod
        def is_allowed(_update) -> bool:
            return True

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        def _clear_flow(self, user_id: int) -> None:
            self.cleared.append(user_id)

        async def _cleanup_ephemeral_messages(self, user_id, bot):
            self.user_ephemeral_messages.pop(user_id, None)

        @staticmethod
        def _ensure_media_categories() -> tuple[bool, str]:
            return True, "ready"

        @staticmethod
        def _start_text(storage_ok: bool, storage_reason: str) -> str:
            return f"center ok={storage_ok} reason={storage_reason}"

        @staticmethod
        def _command_center_keyboard():
            return "keyboard"

        def _start_command_center_refresh(self, user_id):
            pass

        def _stop_command_center_refresh(self, user_id):
            pass

    message = DummyMessage()
    query = DummyQuery(message)
    update = DummyUpdate(query)
    bot = DummyBot()

    asyncio.run(BotApp.on_callback(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert bot.cleared == [77]
    assert query.answer_calls == [{"text": None, "show_alert": False}]
    assert message.reply_calls == []
    assert message.edit_calls == [
        {"text": "center ok=True reason=ready", "reply_markup": "keyboard", "parse_mode": "HTML"}
    ]


def test_on_text_schedule_cancel_returns_to_command_center() -> None:
    class DummyMessage:
        def __init__(self) -> None:
            self.text = "cancel"

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self) -> None:
            self.effective_message = DummyMessage()
            self.effective_user = DummyUser()

    class DummyStore:
        @staticmethod
        def get_command_center(_user_id: int) -> dict[str, object] | None:
            return None

    class DummyBot:
        on_text = BotApp.on_text

        def __init__(self) -> None:
            self.cleared: list[int] = []
            self.command_center_calls: list[object] = []
            self.user_nav_ui: dict[int, dict[str, object]] = {}
            self.store = DummyStore()

        @staticmethod
        def _is_allowlisted(_update) -> bool:
            return True

        @staticmethod
        def _requires_password() -> bool:
            return False

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        @staticmethod
        def _get_flow(_user_id: int) -> dict[str, object]:
            return {"mode": "schedule", "stage": "await_show"}

        def _clear_flow(self, user_id: int) -> None:
            self.cleared.append(user_id)

        async def _render_command_center(
            self, msg: object, user_id: int | None = None, *, use_remembered_ui: bool = False
        ) -> None:
            self.command_center_calls.append(msg)

        async def _navigate_to_command_center(self, msg: object, user_id: int) -> None:
            self.command_center_calls.append(msg)

    update = DummyUpdate()
    bot = DummyBot()

    asyncio.run(BotApp.on_text(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert bot.cleared == [77]
    assert bot.command_center_calls == [update.effective_message]


def test_on_callback_remove_clear_returns_to_library_browser() -> None:
    class DummyMessage:
        pass

    class DummyQuery:
        def __init__(self, message: DummyMessage) -> None:
            self.data = "rm:clear"
            self.message = message
            self.answer_calls: list[dict[str, object]] = []

        async def answer(self, text: str | None = None, show_alert: bool = False):
            self.answer_calls.append({"text": text, "show_alert": show_alert})

        def get_bot(self):
            return None

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self, query: DummyQuery) -> None:
            self.callback_query = query
            self.effective_user = DummyUser()

    class DummyBot:
        on_callback = BotApp.on_callback
        _on_cb_nav_home = BotApp._on_cb_nav_home
        _on_cb_add = BotApp._on_cb_add
        _on_cb_download = BotApp._on_cb_download
        _on_cb_page = BotApp._on_cb_page
        _on_cb_remove = BotApp._on_cb_remove
        _on_cb_schedule = BotApp._on_cb_schedule
        _on_cb_movie_schedule = BotApp._on_cb_movie_schedule
        _on_cb_menu = BotApp._on_cb_menu
        _on_cb_flow = BotApp._on_cb_flow
        _on_cb_mwblock = BotApp._on_cb_mwblock
        _on_cb_stop = BotApp._on_cb_stop
        _on_cb_dl_manage = BotApp._on_cb_dl_manage
        _on_cb_tvpost = BotApp._on_cb_tvpost
        _on_cb_moviepost = BotApp._on_cb_moviepost
        _on_cb_tv_pick = BotApp._on_cb_tv_pick
        _on_cb_movie_pick = BotApp._on_cb_movie_pick
        _on_cb_fsd = BotApp._on_cb_fsd
        _register_callbacks = BotApp._register_callbacks

        def __init__(self) -> None:
            from patchy_bot.dispatch import CallbackDispatcher

            self.flow = {
                "mode": "remove",
                "stage": "show_actions",
                "selected_items": [{"path": "/tmp/show"}],
                "selected": {"path": "/tmp/show"},
                "selected_child": {"path": "/tmp/show/Season 1"},
                "season_items": [{"path": "/tmp/show/Season 1"}],
                "episode_items": [{"path": "/tmp/show/Season 1/ep.mkv"}],
            }
            self.open_calls: list[dict[str, object]] = []
            self.user_ephemeral_messages: dict[int, list] = {}
            self._dispatcher = CallbackDispatcher()
            self._register_callbacks()

        @staticmethod
        def is_allowed(_update) -> bool:
            return True

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        async def _cleanup_ephemeral_messages(self, user_id, bot):
            self.user_ephemeral_messages.pop(user_id, None)

        def _stop_command_center_refresh(self, user_id):
            pass

        async def _render_nav_ui(self, *args, **kwargs):
            pass

        def _home_only_keyboard(self):
            return None

        def _get_flow(self, _user_id: int) -> dict[str, object]:
            return self.flow

        def _set_flow(self, _user_id: int, flow: dict[str, object]) -> None:
            self.flow = dict(flow)

        async def _open_remove_browse_root(self, user_id: int, msg, *, current_ui_message=None) -> None:
            self.open_calls.append(
                {
                    "user_id": user_id,
                    "msg": msg,
                    "current_ui_message": current_ui_message,
                    "flow": dict(self.flow),
                }
            )

    message = DummyMessage()
    query = DummyQuery(message)
    update = DummyUpdate(query)
    bot = DummyBot()

    asyncio.run(BotApp.on_callback(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert bot.flow == {"mode": "remove", "stage": "show_actions", "selected_items": []}
    assert bot.open_calls == [
        {
            "user_id": 77,
            "msg": message,
            "current_ui_message": message,
            "flow": {"mode": "remove", "stage": "show_actions", "selected_items": []},
        }
    ]
    assert query.answer_calls == [{"text": None, "show_alert": False}]


def test_on_callback_remove_review_is_noop_when_selection_is_empty() -> None:
    class DummyMessage:
        pass

    class DummyQuery:
        def __init__(self, message: DummyMessage) -> None:
            self.data = "rm:review"
            self.message = message
            self.answer_calls: list[dict[str, object]] = []

        async def answer(self, text: str | None = None, show_alert: bool = False):
            self.answer_calls.append({"text": text, "show_alert": show_alert})

        def get_bot(self):
            return None

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self, query: DummyQuery) -> None:
            self.callback_query = query
            self.effective_user = DummyUser()

    class DummyBot:
        on_callback = BotApp.on_callback
        _remove_enrich_candidate = BotApp._remove_enrich_candidate

        def __init__(self) -> None:
            self.flow = {"mode": "remove", "stage": "show_actions", "selected_items": []}
            self.render_calls: list[dict[str, object]] = []
            self.user_ephemeral_messages: dict[int, list] = {}

        @staticmethod
        def is_allowed(_update) -> bool:
            return True

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        async def _cleanup_ephemeral_messages(self, user_id, bot):
            self.user_ephemeral_messages.pop(user_id, None)

        def _stop_command_center_refresh(self, user_id):
            pass

        async def _render_nav_ui(self, *args, **kwargs):
            pass

        def _home_only_keyboard(self):
            return None

        def _get_flow(self, _user_id: int) -> dict[str, object]:
            return self.flow

        def _set_flow(self, _user_id: int, flow: dict[str, object]) -> None:
            self.flow = dict(flow)

        async def _render_remove_ui(self, *args, **kwargs) -> None:
            self.render_calls.append({"args": args, "kwargs": kwargs})

    message = DummyMessage()
    query = DummyQuery(message)
    update = DummyUpdate(query)
    bot = DummyBot()

    asyncio.run(BotApp.on_callback(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert bot.flow == {"mode": "remove", "stage": "show_actions", "selected_items": []}
    assert bot.render_calls == []
    assert query.answer_calls == [{"text": None, "show_alert": False}]


def test_on_callback_schedule_pickeps_uses_anchor_renderer() -> None:
    class DummyMessage:
        pass

    class DummyQuery:
        def __init__(self, message: DummyMessage) -> None:
            self.data = "sch:pickeps:track-1"
            self.message = message
            self.answer_calls: list[dict[str, object]] = []

        async def answer(self, text: str | None = None, show_alert: bool = False):
            self.answer_calls.append({"text": text, "show_alert": show_alert})

        def get_bot(self):
            return None

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self, query: DummyQuery) -> None:
            self.callback_query = query
            self.effective_user = DummyUser()

    class DummyStore:
        @staticmethod
        def get_schedule_track(_user_id: int, _track_id: str) -> dict[str, object]:
            return {"last_probe_json": {"actionable_missing_codes": ["S01E01", "S01E02"]}}

    class DummyBot:
        on_callback = BotApp.on_callback
        _schedule_picker_all_missing = BotApp._schedule_picker_all_missing
        _schedule_picker_text = BotApp._schedule_picker_text
        _schedule_picker_keyboard = BotApp._schedule_picker_keyboard
        _on_cb_nav_home = BotApp._on_cb_nav_home
        _on_cb_add = BotApp._on_cb_add
        _on_cb_download = BotApp._on_cb_download
        _on_cb_page = BotApp._on_cb_page
        _on_cb_remove = BotApp._on_cb_remove
        _on_cb_schedule = BotApp._on_cb_schedule
        _on_cb_movie_schedule = BotApp._on_cb_movie_schedule
        _on_cb_menu = BotApp._on_cb_menu
        _on_cb_flow = BotApp._on_cb_flow
        _on_cb_mwblock = BotApp._on_cb_mwblock
        _on_cb_stop = BotApp._on_cb_stop
        _on_cb_dl_manage = BotApp._on_cb_dl_manage
        _on_cb_tvpost = BotApp._on_cb_tvpost
        _on_cb_moviepost = BotApp._on_cb_moviepost
        _on_cb_tv_pick = BotApp._on_cb_tv_pick
        _on_cb_movie_pick = BotApp._on_cb_movie_pick
        _on_cb_fsd = BotApp._on_cb_fsd
        _register_callbacks = BotApp._register_callbacks

        def __init__(self) -> None:
            from patchy_bot.dispatch import CallbackDispatcher

            self.store = DummyStore()
            self.flow: dict[str, object] = {}
            self.render_calls: list[dict[str, object]] = []
            self.user_ephemeral_messages: dict[int, list] = {}
            self._dispatcher = CallbackDispatcher()
            self._register_callbacks()

        @staticmethod
        def is_allowed(_update) -> bool:
            return True

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        async def _cleanup_ephemeral_messages(self, user_id, bot):
            self.user_ephemeral_messages.pop(user_id, None)

        def _stop_command_center_refresh(self, user_id):
            pass

        async def _render_nav_ui(self, *args, **kwargs):
            pass

        def _home_only_keyboard(self):
            return None

        def _get_flow(self, _user_id: int) -> dict[str, object]:
            return self.flow

        def _set_flow(self, _user_id: int, flow: dict[str, object]) -> None:
            self.flow = dict(flow)

        async def _render_schedule_ui(self, *args, **kwargs) -> None:
            self.render_calls.append({"args": args, "kwargs": kwargs})

        def _nav_footer(self, *, back_data: str = "", include_home: bool = True):
            return BotApp._nav_footer(self, back_data=back_data, include_home=include_home)  # pyright: ignore[reportArgumentType]

    message = DummyMessage()
    query = DummyQuery(message)
    update = DummyUpdate(query)
    bot = DummyBot()

    asyncio.run(BotApp.on_callback(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert query.answer_calls == [{"text": None, "show_alert": False}]
    assert len(bot.render_calls) == 1
    assert bot.render_calls[0]["args"][1] == message  # pyright: ignore[reportIndexIssue]
    assert "🎯 Choose Episodes to Download" in str(bot.render_calls[0]["args"][3])  # pyright: ignore[reportIndexIssue]


def test_on_callback_schedule_skip_uses_anchor_renderer() -> None:
    class DummyMessage:
        pass

    class DummyQuery:
        def __init__(self, message: DummyMessage) -> None:
            self.data = "sch:skip:track-1"
            self.message = message
            self.answer_calls: list[dict[str, object]] = []

        async def answer(self, text: str | None = None, show_alert: bool = False):
            self.answer_calls.append({"text": text, "show_alert": show_alert})

        def get_bot(self):
            return None

    class DummyUser:
        id = 77

    class DummyUpdate:
        def __init__(self, query: DummyQuery) -> None:
            self.callback_query = query
            self.effective_user = DummyUser()

    class DummyStore:
        def __init__(self) -> None:
            self.updated: dict[str, object] | None = None

        @staticmethod
        def get_schedule_track(_user_id: int, _track_id: str) -> dict[str, object]:
            return {"last_probe_json": {"signature": "sig-1"}}

        def update_schedule_track(self, track_id: str, **kwargs: object) -> None:
            self.updated = {"track_id": track_id, **kwargs}

    class DummyBot:
        on_callback = BotApp.on_callback
        _on_cb_nav_home = BotApp._on_cb_nav_home
        _on_cb_add = BotApp._on_cb_add
        _on_cb_download = BotApp._on_cb_download
        _on_cb_page = BotApp._on_cb_page
        _on_cb_remove = BotApp._on_cb_remove
        _on_cb_schedule = BotApp._on_cb_schedule
        _on_cb_movie_schedule = BotApp._on_cb_movie_schedule
        _on_cb_menu = BotApp._on_cb_menu
        _on_cb_flow = BotApp._on_cb_flow
        _on_cb_mwblock = BotApp._on_cb_mwblock
        _on_cb_stop = BotApp._on_cb_stop
        _on_cb_dl_manage = BotApp._on_cb_dl_manage
        _on_cb_tvpost = BotApp._on_cb_tvpost
        _on_cb_moviepost = BotApp._on_cb_moviepost
        _on_cb_tv_pick = BotApp._on_cb_tv_pick
        _on_cb_movie_pick = BotApp._on_cb_movie_pick
        _on_cb_fsd = BotApp._on_cb_fsd
        _register_callbacks = BotApp._register_callbacks

        def __init__(self) -> None:
            from patchy_bot.dispatch import CallbackDispatcher

            self.store = DummyStore()
            self.render_calls: list[dict[str, object]] = []
            self.user_ephemeral_messages: dict[int, list] = {}
            self._dispatcher = CallbackDispatcher()
            self._register_callbacks()

        @staticmethod
        def is_allowed(_update) -> bool:
            return True

        async def deny(self, _update) -> None:
            raise AssertionError("deny should not be called")

        async def _cleanup_ephemeral_messages(self, user_id, bot):
            self.user_ephemeral_messages.pop(user_id, None)

        def _stop_command_center_refresh(self, user_id):
            pass

        async def _render_nav_ui(self, *args, **kwargs) -> None:
            self.render_calls.append({"args": args, "kwargs": kwargs})

        def _home_only_keyboard(self):
            return "home-kb"

    message = DummyMessage()
    query = DummyQuery(message)
    update = DummyUpdate(query)
    bot = DummyBot()

    asyncio.run(BotApp.on_callback(bot, update, None))  # pyright: ignore[reportArgumentType]

    assert query.answer_calls == [{"text": None, "show_alert": False}]
    assert bot.store.updated == {
        "track_id": "track-1",
        "skipped_signature": "sig-1",
        "last_missing_signature": "sig-1",
    }
    assert len(bot.render_calls) == 1
    assert "I'll skip this notification." in bot.render_calls[0]["args"][2]  # pyright: ignore[reportIndexIssue]


def test_render_schedule_ui_edits_existing_schedule_message() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            return DummyMessage(self, int(kwargs["chat_id"]), int(kwargs["message_id"]))  # pyright: ignore[reportArgumentType]

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 999)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _render_flow_ui = BotApp._render_flow_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {"mode": "schedule", "stage": "confirm", "schedule_ui_chat_id": 100, "schedule_ui_message_id": 321}

    rendered = asyncio.run(BotApp._render_schedule_ui(app, 77, anchor, flow, "Updated schedule UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 321
    assert len(bot_api.edit_calls) == 1
    assert anchor.reply_calls == []
    assert app.user_flow[77]["schedule_ui_message_id"] == 321


def test_render_nav_ui_edits_existing_navigation_message() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            return DummyMessage(self, int(kwargs["chat_id"]), int(kwargs["message_id"]))  # pyright: ignore[reportArgumentType]

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 999)

    class DummyApp:
        def __init__(self) -> None:
            self.user_nav_ui = {77: {"chat_id": 100, "message_id": 321}}

        _remember_nav_ui_message = BotApp._remember_nav_ui_message

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)

    rendered = asyncio.run(BotApp._render_nav_ui(app, 77, anchor, "Updated nav UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 321
    assert len(bot_api.edit_calls) == 1
    assert anchor.reply_calls == []
    assert app.user_nav_ui[77]["message_id"] == 321


def test_render_nav_ui_falls_back_to_new_message_when_edit_fails() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            raise TelegramError("message to edit not found")

        async def edit_message_reply_markup(self, **kwargs: object):
            pass

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 555)

    class DummyApp:
        def __init__(self) -> None:
            self.user_nav_ui = {77: {"chat_id": 100, "message_id": 321}}

        _remember_nav_ui_message = BotApp._remember_nav_ui_message
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)

    rendered = asyncio.run(BotApp._render_nav_ui(app, 77, anchor, "Updated nav UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 555
    assert len(bot_api.edit_calls) == 1
    assert len(anchor.reply_calls) == 1
    assert app.user_nav_ui[77]["message_id"] == 555


def test_render_schedule_ui_falls_back_to_new_message_when_edit_fails() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            raise TelegramError("message to edit not found")

        async def edit_message_reply_markup(self, **kwargs: object):
            pass

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 555)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _render_flow_ui = BotApp._render_flow_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {"mode": "schedule", "stage": "confirm", "schedule_ui_chat_id": 100, "schedule_ui_message_id": 321}

    rendered = asyncio.run(BotApp._render_schedule_ui(app, 77, anchor, flow, "Updated schedule UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 555
    assert len(bot_api.edit_calls) == 1
    assert len(anchor.reply_calls) == 1
    assert app.user_flow[77]["schedule_ui_message_id"] == 555


def test_render_tv_ui_edits_existing_tv_message() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            return DummyMessage(self, int(kwargs["chat_id"]), int(kwargs["message_id"]))  # pyright: ignore[reportArgumentType]

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 999)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _render_flow_ui = BotApp._render_flow_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {"mode": "tv", "stage": "await_title", "tv_ui_chat_id": 100, "tv_ui_message_id": 321}

    rendered = asyncio.run(BotApp._render_tv_ui(app, 77, anchor, flow, "Updated tv UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 321
    assert len(bot_api.edit_calls) == 1
    assert anchor.reply_calls == []
    assert app.user_flow[77]["tv_ui_message_id"] == 321


def test_render_tv_ui_falls_back_to_new_message_when_edit_fails() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            raise TelegramError("message to edit not found")

        async def edit_message_reply_markup(self, **kwargs: object):
            pass

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 555)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _render_flow_ui = BotApp._render_flow_ui
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {"mode": "tv", "stage": "await_title", "tv_ui_chat_id": 100, "tv_ui_message_id": 321}

    rendered = asyncio.run(BotApp._render_tv_ui(app, 77, anchor, flow, "Updated tv UI"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 555
    assert len(bot_api.edit_calls) == 1
    assert len(anchor.reply_calls) == 1
    assert app.user_flow[77]["tv_ui_message_id"] == 555


def test_cleanup_private_user_message_only_deletes_private_chats() -> None:
    class DummyChat:
        def __init__(self, chat_type: str) -> None:
            self.type = chat_type

    class DummyMessage:
        def __init__(self, chat_type: str) -> None:
            self.chat = DummyChat(chat_type)
            self.deleted = 0

        async def delete(self) -> None:
            self.deleted += 1

    private_msg = DummyMessage("private")
    group_msg = DummyMessage("group")

    asyncio.run(BotApp._cleanup_private_user_message(object(), private_msg))  # pyright: ignore[reportArgumentType]
    asyncio.run(BotApp._cleanup_private_user_message(object(), group_msg))  # pyright: ignore[reportArgumentType]

    assert private_msg.deleted == 1
    assert group_msg.deleted == 0


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


def test_relative_time_past_hours() -> None:
    base = 1000000
    assert _relative_time(base - 7200, from_ts=base) == "2h ago"


def test_relative_time_past_days() -> None:
    base = 1000000
    assert _relative_time(base - 172800, from_ts=base) == "2d ago"


def test_relative_time_boundary_exactly_60s() -> None:
    base = 1000000
    assert _relative_time(base + 60, from_ts=base) == "in 1m"


def test_relative_time_boundary_exactly_3600s() -> None:
    base = 1000000
    assert _relative_time(base + 3600, from_ts=base) == "in 1h"


def test_relative_time_boundary_exactly_86400s() -> None:
    base = 1000000
    assert _relative_time(base + 86400, from_ts=base) == "in 1d"


def test_relative_time_zero_ts_is_not_tbd() -> None:
    # ts=0 is Unix epoch — it's a real timestamp, not missing data
    result = _relative_time(0, from_ts=1000000)
    assert result != "TBD"


def test_relative_time_beyond_7_days_falls_back_to_absolute() -> None:
    base = 1000000
    result = _relative_time(base + 8 * 86400, from_ts=base)
    # Should be an absolute date string (from format_local_ts), not a relative label
    assert "in " not in result and "ago" not in result and result != "TBD"


def test_episode_status_icon_priority_present_wins() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=[])
    probe = {
        "present_codes": ["S01E01"],
        "pending_codes": ["S01E01"],
        "unreleased_codes": ["S01E01"],
        "actionable_missing_codes": ["S01E01"],
    }
    # present must win over all other statuses
    assert BotApp._episode_status_icon(bot, probe, "S01E01") == "✅"


def test_episode_status_icon_priority_unreleased_before_actionable() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=[])
    probe = {
        "present_codes": [],
        "pending_codes": [],
        "unreleased_codes": ["S01E03"],
        "actionable_missing_codes": ["S01E03"],
    }
    # unreleased wins over actionable
    assert BotApp._episode_status_icon(bot, probe, "S01E03") == "⏰"


def test_episode_status_icon_queued() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=[])
    probe = {
        "present_codes": [],
        "pending_codes": ["S01E02"],
        "unreleased_codes": [],
        "actionable_missing_codes": [],
    }
    assert BotApp._episode_status_icon(bot, probe, "S01E02") == "⬇️"


def test_episode_status_icon_actionable_missing() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=[])
    probe = {
        "present_codes": [],
        "pending_codes": [],
        "unreleased_codes": [],
        "actionable_missing_codes": ["S01E04"],
    }
    assert BotApp._episode_status_icon(bot, probe, "S01E04") == "🔍"


def test_episode_status_icon_default() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=[])
    probe = {
        "present_codes": [],
        "pending_codes": [],
        "unreleased_codes": [],
        "actionable_missing_codes": [],
    }
    assert BotApp._episode_status_icon(bot, probe, "S01E99") == "📋"


def test_episode_status_icon_pending_arg_merges_with_probe_pending() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=[])
    probe = {
        "present_codes": [],
        "pending_codes": [],  # not in probe
        "unreleased_codes": [],
        "actionable_missing_codes": [],
    }
    # extra pending set passed as kwarg should trigger ⬇️
    assert BotApp._episode_status_icon(bot, probe, "S01E05", pending={"S01E05"}) == "⬇️"


def test_schedule_episode_label_format_includes_icon_and_relative_time() -> None:
    import re
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp, now_ts

    bot = MagicMock(spec=BotApp)
    # Wire real _episode_status_icon and _relative_time into the mock
    bot._episode_status_icon = lambda probe, code, pending=None: BotApp._episode_status_icon(
        bot, probe, code, pending=pending
    )
    # Use a timestamp 2 hours in the future
    future_ts = now_ts() + 7200
    probe = {
        "episode_map": {"S01E05": "The One Where"},
        "episode_air": {"S01E05": future_ts},
        "present_codes": [],
        "pending_codes": [],
        "unreleased_codes": [],
        "actionable_missing_codes": ["S01E05"],
    }
    label = BotApp._schedule_episode_label(bot, probe, "S01E05")
    # Must include an emoji icon
    assert any(icon in label for icon in ("✅", "⬇️", "⏰", "🔍", "📋"))
    # Must NOT contain an absolute timestamp pattern like "2024-03-22 14:00"
    assert not re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", label)
    # Must contain the episode code
    assert "S01E05" in label
    # Must contain the episode name
    assert "The One Where" in label


def test_schedule_episode_label_no_air_ts_shows_released() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot._episode_status_icon = lambda probe, code, pending=None: BotApp._episode_status_icon(
        bot, probe, code, pending=pending
    )
    probe = {
        "episode_map": {"S01E01": "Pilot"},
        "episode_air": {},
        "present_codes": ["S01E01"],
        "pending_codes": [],
        "unreleased_codes": [],
        "actionable_missing_codes": [],
    }
    label = BotApp._schedule_episode_label(bot, probe, "S01E01")
    assert "released" in label
    assert "S01E01" in label


def test_schedule_active_line_missing_shows_search_icon() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {
        "show_json": {"name": "The Bear"},
        "season": 2,
        "pending_json": [],
        "next_air_ts": None,
        "next_check_at": None,
        "last_probe_json": {
            "actionable_missing_codes": ["S02E01", "S02E02"],
            "pending_codes": [],
            "unreleased_codes": [],
        },
    }
    line = BotApp._schedule_active_line(bot, track)
    assert "🔍" not in line
    assert "The Bear" in line
    assert "S2 · 2 eps. missing" in line


def test_schedule_active_line_up_to_date_shows_checkmark() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {
        "show_json": {"name": "Succession"},
        "season": 4,
        "pending_json": [],
        "next_air_ts": None,
        "next_check_at": None,
        "last_probe_json": {
            "actionable_missing_codes": [],
            "pending_codes": [],
            "unreleased_codes": [],
        },
    }
    line = BotApp._schedule_active_line(bot, track)
    assert "✅" not in line
    assert "Succession" in line
    assert "<b>S4 · up to date</b>" in line


def test_schedule_active_line_uses_dot_separator_not_pipe() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {
        "show_json": {"name": "Test Show"},
        "season": 1,
        "pending_json": [],
        "next_air_ts": None,
        "next_check_at": None,
        "last_probe_json": {
            "actionable_missing_codes": [],
            "pending_codes": [],
            "unreleased_codes": [1, 2],
        },
    }
    line = BotApp._schedule_active_line(bot, track)
    assert " · " in line
    assert " | " not in line
    assert "⏰" not in line
    assert "S1 · 2 eps. left" in line


def test_schedule_active_line_formats_next_air_as_bold_ep_left_summary() -> None:
    import time
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {
        "show_json": {"name": "High Potential"},
        "season": 2,
        "pending_json": [],
        "next_air_ts": None,
        "next_check_at": None,
        "last_probe_json": {
            "actionable_missing_codes": [],
            "pending_codes": [],
            "unreleased_codes": ["S02E09"],
            "next_air_ts": int(time.time()) + 3 * 3600,
        },
    }
    line = BotApp._schedule_active_line(bot, track)
    assert line.startswith("<b>High Potential</b>\n   <b>S2 · 1 ep. left · next ")
    assert line.endswith("</b>")


def test_schedule_preview_text_inventory_uses_status_icons() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot._relative_time = None  # not needed — method uses module-level _relative_time
    probe = {
        "show": {"name": "Severance", "year": 2022, "status": "Returning", "network": "Apple TV+"},
        "season": 2,
        "tracking_mode": "upcoming",
        "released_codes": ["S02E01"],
        "total_season_episodes": 10,
        "present_codes": ["S02E01"],
        "unreleased_codes": ["S02E03"],
        "tracked_missing_codes": ["S02E02"],
        "missing_codes": ["S02E02"],
        "inventory_source": "plex",
        "next_air_ts": None,
        "metadata_stale": False,
        "inventory_degraded": False,
        "pending_codes": [],
        "series_missing_by_season": {},
        "series_actionable_all": [],
    }
    text = BotApp._schedule_preview_text(bot, probe)
    assert "✅ In library" in text
    assert "📋 Released" in text
    assert "⏰ Unreleased" in text
    # New format: missing episodes listed explicitly under "Missing (Season N)"
    assert "Missing (Season 2)" in text
    assert "E02" in text
    assert "S02E02" not in text  # season prefix stripped in Missing section
    # Old fields must be gone
    assert "🔍 To fetch" not in text
    assert "• Next targets:" not in text
    assert "• Released:" not in text
    assert "• In library:" not in text


def test_schedule_preview_text_missing_strips_season_prefix() -> None:
    """Missing and other-season-gaps lines show Exx, not SxxExx."""
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot._relative_time = None
    probe = {
        "show": {"name": "Test Show", "year": 2024, "status": "Returning"},
        "season": 2,
        "tracking_mode": "upcoming",
        "released_codes": ["S02E01", "S02E02", "S02E03"],
        "total_season_episodes": 10,
        "present_codes": [],
        "unreleased_codes": [],
        "tracked_missing_codes": ["S02E01", "S02E02", "S02E03"],
        "missing_codes": ["S02E01", "S02E02", "S02E03"],
        "inventory_source": "plex",
        "next_air_ts": None,
        "metadata_stale": False,
        "inventory_degraded": False,
        "pending_codes": ["S02E01"],
        "series_missing_by_season": {
            1: ["S01E01", "S01E02", "S01E03", "S01E04", "S01E05"],
        },
        "series_actionable_all": [],
    }
    text = BotApp._schedule_preview_text(bot, probe)
    # Missing section should show short episode codes
    assert "E02 · E03" in text
    assert "S02E02" not in text  # no full code in Missing line
    # Queued line must retain full SxxExx
    assert "S02E01" in text
    # Other seasons with gaps should strip prefix too
    assert "Season 1:" in text
    assert "E01 · E02 · E03 · E04" in text
    assert "S01E01" not in text
    assert "+1 more" in text


def test_schedule_preview_text_next_air_ts_uses_relative_time() -> None:
    import time
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    probe = {
        "show": {"name": "Test Show", "year": 2024, "status": "Returning"},
        "season": 1,
        "tracking_mode": "upcoming",
        "released_codes": [],
        "total_season_episodes": 8,
        "present_codes": [],
        "unreleased_codes": [],
        "tracked_missing_codes": [],
        "inventory_source": "plex",
        "next_air_ts": int(time.time()) + 86400,  # 1 day in future
        "metadata_stale": False,
        "inventory_degraded": False,
        "pending_codes": [],
    }
    text = BotApp._schedule_preview_text(bot, probe)
    # Must contain 📅 prefix
    assert "📅" in text
    # Must contain relative time format like "in 1d"
    assert "in " in text or "ago" in text


def test_schedule_track_ready_text_contains_divider_and_icons() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {
        "show_json": {"name": "White Lotus"},
        "season": 3,
    }
    probe = {
        "tracking_mode": "upcoming",
        "tracked_missing_codes": ["S03E01"],
        "present_codes": ["S03E01"],
        "unreleased_codes": ["S03E03"],
        "next_air_ts": None,
        "metadata_stale": False,
        "inventory_degraded": False,
    }
    text = BotApp._schedule_track_ready_text(bot, track, probe)
    assert "━" in text
    assert "✅ In library" in text
    assert "🔍 Still needed" in text
    assert "⏰ Unreleased" in text


def test_schedule_track_ready_text_next_air_ts_uses_relative_time() -> None:
    import time
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {"show_json": {"name": "Test"}, "season": 1}
    probe = {
        "tracking_mode": "upcoming",
        "tracked_missing_codes": [],
        "present_codes": [],
        "unreleased_codes": [],
        "next_air_ts": int(time.time()) + 86400,  # 1 day in future
        "metadata_stale": False,
        "inventory_degraded": False,
    }
    text = BotApp._schedule_track_ready_text(bot, track, probe)
    assert "📅" in text
    # Within 7 days should use relative format, not absolute timestamp
    assert "in " in text or "ago" in text


def test_schedule_track_ready_text_duplicate_flag_changes_header() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    track = {"show_json": {"name": "Test"}, "season": 1}
    probe = {
        "tracking_mode": "upcoming",
        "tracked_missing_codes": [],
        "present_codes": [],
        "unreleased_codes": [],
        "next_air_ts": None,
        "metadata_stale": False,
        "inventory_degraded": False,
    }
    text_new = BotApp._schedule_track_ready_text(bot, track, probe, duplicate=False)
    text_dup = BotApp._schedule_track_ready_text(bot, track, probe, duplicate=True)
    assert "Schedule Tracking Enabled" in text_new
    assert "Already Tracking" in text_dup


def test_schedule_missing_text_first_two_episodes_inline() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    # Wire real _schedule_episode_label and _schedule_episode_auto_state
    bot._schedule_episode_auto_state = lambda track: {}
    bot._schedule_episode_label = lambda probe, code, **kw: f"🔍 {code} — Episode ({code})"
    track = {
        "show_json": {"name": "The Bear"},
        "season": 3,
        "auto_state_json": {},
    }
    probe = {
        "actionable_missing_codes": ["S03E01", "S03E02", "S03E03"],
        "present_codes": [],
        "unreleased_codes": [],
        "pending_codes": [],
    }
    text = BotApp._schedule_missing_text(bot, track, probe)
    # First two must appear inline (outside of blockquote)
    blockquote_start = text.find("<blockquote")
    assert blockquote_start > 0
    text_before_blockquote = text[:blockquote_start]
    assert "S03E01" in text_before_blockquote
    assert "S03E02" in text_before_blockquote
    # Third episode must be inside blockquote
    text_in_blockquote = text[blockquote_start:]
    assert "S03E03" in text_in_blockquote


def test_schedule_missing_text_footer_shows_next_retry_time() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot._schedule_episode_auto_state = lambda track: {"next_auto_retry_at": 1000000 + 3600}
    bot._schedule_episode_label = lambda probe, code, **kw: f"🔍 {code} — Episode"
    track = {"show_json": {"name": "Test"}, "season": 1, "auto_state_json": {}}
    probe = {
        "actionable_missing_codes": ["S01E01"],
        "present_codes": [],
        "unreleased_codes": [],
        "pending_codes": [],
    }
    text = BotApp._schedule_missing_text(bot, track, probe)
    # Should NOT say "Searching hourly"
    assert "hourly" not in text
    # Should contain a relative time reference
    assert "next attempt" in text


def test_schedule_missing_text_singular_episode_label() -> None:
    from unittest.mock import MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot._schedule_episode_auto_state = lambda track: {}
    bot._schedule_episode_label = lambda probe, code, **kw: f"🔍 {code} — Episode"
    track = {"show_json": {"name": "Test"}, "season": 1, "auto_state_json": {}}
    probe = {
        "actionable_missing_codes": ["S01E01"],
        "present_codes": [],
        "unreleased_codes": [],
        "pending_codes": [],
    }
    text = BotApp._schedule_missing_text(bot, track, probe)
    assert "episode needed" in text
    assert "episodes needed" not in text  # must be singular


def test_schedule_notify_auto_queued_includes_category_and_path() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from qbt_telegram_bot import BotApp

    sent_texts = []

    async def fake_send_message(**kwargs):
        sent_texts.append(kwargs.get("text", ""))
        return MagicMock()

    bot = MagicMock(spec=BotApp)
    bot.app = MagicMock()
    bot.app.bot.send_message = AsyncMock(side_effect=fake_send_message)
    bot._stop_download_keyboard = MagicMock(return_value=MagicMock())
    bot._start_progress_tracker = MagicMock()
    bot._start_pending_progress_tracker = MagicMock()

    track = {"show_json": {"name": "The Bear"}, "chat_id": 12345, "user_id": 99}
    result = {
        "name": "The.Bear.S03E01.1080p.WEB-DL",
        "category": "tv",
        "path": "/media/tv",
        "hash": "abc123",
    }

    asyncio.run(BotApp._schedule_notify_auto_queued(bot, track, "S03E01", result))

    assert len(sent_texts) >= 1
    first_msg = sent_texts[0]
    assert "Auto-Queued" in first_msg
    assert "The Bear" in first_msg
    assert "S03E01" in first_msg
    assert "Category:" in first_msg
    assert "Path:" in first_msg


def test_schedule_notify_auto_queued_starts_headless_tracker_when_hash_available() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from qbt_telegram_bot import BotApp

    call_count = [0]

    async def fake_send_message(**kwargs):
        call_count[0] += 1
        return MagicMock()

    bot = MagicMock(spec=BotApp)
    bot.app = MagicMock()
    bot.app.bot.send_message = AsyncMock(side_effect=fake_send_message)
    bot._stop_download_keyboard = MagicMock(return_value=MagicMock())
    bot._start_progress_tracker = MagicMock()
    bot._start_pending_progress_tracker = MagicMock()
    bot._ctx = MagicMock()
    bot._ctx.background_tasks = set()

    track = {"show_json": {"name": "Test"}, "chat_id": 1, "user_id": 1}
    result = {"name": "Test.S01E01", "category": "tv", "path": "/media/tv", "hash": "deadbeef"}

    asyncio.run(BotApp._schedule_notify_auto_queued(bot, track, "S01E01", result))

    # Should have sent exactly 1 message: the auto-queued notification card.
    # The per-download "Live Monitor Attached" message is gone — Command Center
    # is the sole display.
    assert call_count[0] == 1
    # _start_progress_tracker must be called with tracker_msg=None (headless)
    bot._start_progress_tracker.assert_called_once()
    pos_args, kw_args = bot._start_progress_tracker.call_args
    # Signature: (user_id, torrent_hash, tracker_msg, title, *, chat_id=...)
    assert pos_args[0] == 1  # user_id
    assert pos_args[1] == "deadbeef"
    assert pos_args[2] is None  # tracker_msg is None (headless)
    assert kw_args.get("chat_id") == 1
    bot._start_pending_progress_tracker.assert_not_called()


def test_schedule_download_requested_edits_status_card_not_new_message() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot.store = MagicMock()
    bot.store.update_schedule_track = AsyncMock()
    bot.store.get_schedule_track = AsyncMock(return_value=None)
    bot._command_center_keyboard = MagicMock(return_value=MagicMock())
    bot._stop_download_keyboard = MagicMock(return_value=MagicMock())
    bot._start_progress_tracker = MagicMock()
    bot._start_pending_progress_tracker = MagicMock()
    bot._schedule_refresh_track = AsyncMock()

    # Simulate a successful download
    bot._schedule_download_episode = AsyncMock(
        return_value={
            "name": "The.Bear.S03E01.1080p",
            "category": "tv",
            "hash": "abc123",
            "path": "/media/tv",
        }
    )

    status_mock = MagicMock()
    status_mock.edit_text = AsyncMock()
    status_mock.chat_id = 777

    reply_texts = []

    async def fake_reply_text(text, **kwargs):
        reply_texts.append(text)
        return status_mock

    msg = MagicMock()
    msg.reply_text = AsyncMock(side_effect=fake_reply_text)

    track = {
        "track_id": "t1",
        "user_id": 1,
        "show_json": {"name": "The Bear"},
        "last_probe_json": {"actionable_missing_codes": ["S03E01"]},
        "pending_json": [],
    }

    asyncio.run(BotApp._schedule_download_requested(bot, msg, track, ["S03E01"]))

    # status_msg must be edited (not a new reply_text call for results)
    status_mock.edit_text.assert_called_once()
    edit_text_call = status_mock.edit_text.call_args
    final_text = edit_text_call[0][0] if edit_text_call[0] else edit_text_call[1].get("text", "")
    assert "Queue Results" in final_text
    assert "✅" in final_text

    # Must NOT have a separate "What's next?" reply message
    assert not any("What's next" in t for t in reply_texts)

    # Headless refactor: the progress tracker must be started with tracker_msg=None
    # and the status_msg chat_id passed explicitly so the batch monitor can render.
    bot._start_progress_tracker.assert_called_once()
    pos_args, kw_args = bot._start_progress_tracker.call_args
    # (user_id_track, result["hash"], None, result["name"], chat_id=...)
    assert pos_args[2] is None
    assert kw_args.get("chat_id") == 777


# ── RateLimiter ──────────────────────────────────────────────────────────────


def test_rate_limiter_allows_requests_under_limit():
    rl = RateLimiter(limit=5, window_s=60.0)
    for _ in range(5):
        assert rl.is_allowed(user_id=1) is True


def test_rate_limiter_blocks_request_over_limit():
    rl = RateLimiter(limit=3, window_s=60.0)
    for _ in range(3):
        rl.is_allowed(user_id=1)
    assert rl.is_allowed(user_id=1) is False


def test_rate_limiter_tracks_users_independently():
    rl = RateLimiter(limit=2, window_s=60.0)
    rl.is_allowed(user_id=1)
    rl.is_allowed(user_id=1)
    assert rl.is_allowed(user_id=1) is False  # user 1 is blocked
    assert rl.is_allowed(user_id=2) is True  # user 2 is unaffected


def test_rate_limiter_reset_clears_counter():
    rl = RateLimiter(limit=2, window_s=60.0)
    rl.is_allowed(user_id=1)
    rl.is_allowed(user_id=1)
    assert rl.is_allowed(user_id=1) is False  # blocked
    rl.reset(user_id=1)
    assert rl.is_allowed(user_id=1) is True  # allowed after reset


def test_rate_limiter_check_within_limit_does_not_advance_counter():
    rl = RateLimiter(limit=2, window_s=60.0)
    # _check_within_limit should not consume quota
    for _ in range(10):
        assert rl._check_within_limit(user_id=1) is True
    # Counter should still be empty — first is_allowed() should succeed
    assert rl.is_allowed(user_id=1) is True
    assert rl.is_allowed(user_id=1) is True
    # Now at limit
    assert rl.is_allowed(user_id=1) is False


# ── Store security ────────────────────────────────────────────────────────────


def test_store_creates_db_with_owner_only_permissions(tmp_path):
    import stat

    db_path = str(tmp_path / "test_state.sqlite3")
    Store(db_path)  # creates DB file as side effect
    mode = stat.S_IMODE(os.stat(db_path).st_mode)
    assert mode == 0o600, f"Expected 0600, got {oct(mode)}"


def test_store_uses_wal_journal_mode(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "test_wal.sqlite3")
    Store(db_path)  # creates DB file as side effect
    conn = sqlite3.connect(db_path)
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    conn.close()
    assert mode == "wal", f"Expected wal journal mode, got {mode}"


def test_store_clear_auth_failures_removes_record(tmp_path):
    db_path = str(tmp_path / "test_auth.sqlite3")
    s = Store(db_path)
    # Record some failures
    s.record_auth_failure(user_id=42, max_attempts=10, lockout_s=900)
    s.record_auth_failure(user_id=42, max_attempts=10, lockout_s=900)
    # Verify failures were recorded
    assert s.is_auth_locked(user_id=42) is False  # not locked yet
    # Clear them
    s.clear_auth_failures(user_id=42)
    # Should be gone — re-recording from scratch should work
    for _ in range(9):
        s.record_auth_failure(user_id=42, max_attempts=10, lockout_s=900)
    assert s.is_auth_locked(user_id=42) is False  # still not locked (only 9/10)


def test_schedule_download_requested_no_waiting_for_hash_message() -> None:
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from qbt_telegram_bot import BotApp

    bot = MagicMock(spec=BotApp)
    bot.store = MagicMock()
    bot.store.update_schedule_track = AsyncMock()
    bot.store.get_schedule_track = AsyncMock(return_value=None)
    bot._command_center_keyboard = MagicMock(return_value=MagicMock())
    bot._start_pending_progress_tracker = MagicMock()
    bot._schedule_refresh_track = AsyncMock()

    # No hash — should silently start pending tracker, no "waiting for hash" message
    bot._schedule_download_episode = AsyncMock(
        return_value={
            "name": "Test.S01E01",
            "category": "tv",
            "hash": None,
            "path": "/media/tv",
        }
    )

    status_mock = MagicMock()
    status_mock.edit_text = AsyncMock()
    reply_texts = []

    async def fake_reply_text(text, **kwargs):
        reply_texts.append(text)
        return status_mock

    msg = MagicMock()
    msg.reply_text = AsyncMock(side_effect=fake_reply_text)

    track = {
        "track_id": "t1",
        "user_id": 1,
        "show_json": {"name": "Test Show"},
        "last_probe_json": {"actionable_missing_codes": ["S01E01"]},
        "pending_json": [],
    }

    asyncio.run(BotApp._schedule_download_requested(bot, msg, track, ["S01E01"]))

    # Must NOT contain "waiting" message
    assert not any("waiting" in t.lower() for t in reply_texts)
    # Pending tracker should have been called
    bot._start_pending_progress_tracker.assert_called_once()


def test_skip_reply_text_explains_re_notification_conditions() -> None:
    # Verify the skip confirmation text content by searching for it in the source
    import inspect

    from patchy_bot.handlers.schedule import on_cb_schedule

    # Get the source of the callback handler that handles sch:skip
    source = inspect.getsource(on_cb_schedule)
    # The new text must be present
    assert "I'll alert you again if new episodes air or the missing count changes" in source
    # The old vague text must NOT be present
    assert "unless something changes" not in source


def test_plex_refresh_all_by_type_calls_refresh_and_empty_trash_for_matching_sections(monkeypatch) -> None:
    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = 200
            self.text = ""

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []

        def request(
            self,
            method: str,
            url: str,
            *,
            params: dict | None = None,
            headers: dict | None = None,
            timeout: int | None = None,
        ) -> FakeResponse:
            self.calls.append((method, url, dict(params or {})))
            return FakeResponse()

    fake_session = FakeSession()
    client.session = fake_session  # type: ignore[assignment]
    monkeypatch.setattr("patchy_bot.clients.plex.time.sleep", lambda _: None)

    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
        {"key": "2", "title": "4K Movies", "type": "movie", "locations": ["/mnt/4k"], "refreshing": False},
        {"key": "3", "title": "TV Shows", "type": "show", "locations": ["/mnt/tv"], "refreshing": False},
    ]
    client._wait_for_section_idle = lambda *args, **kwargs: True  # type: ignore[method-assign]

    titles = client.refresh_all_by_type(["movie"])

    assert titles == ["Movies", "4K Movies"]
    post_urls = [url for method, url, _ in fake_session.calls if method == "POST"]
    put_urls = [url for method, url, _ in fake_session.calls if method == "PUT"]
    assert "http://plex.local:32400/library/sections/1/refresh" in post_urls
    assert "http://plex.local:32400/library/sections/2/refresh" in post_urls
    assert "http://plex.local:32400/library/sections/3/refresh" not in post_urls
    assert "http://plex.local:32400/library/sections/1/emptyTrash" in put_urls
    assert "http://plex.local:32400/library/sections/2/emptyTrash" in put_urls
    assert "http://plex.local:32400/library/sections/3/emptyTrash" not in put_urls


def test_plex_refresh_all_by_type_skips_empty_trash_on_section_idle_timeout(monkeypatch) -> None:
    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = 200
            self.text = ""

    class FakeSession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict]] = []

        def request(
            self,
            method: str,
            url: str,
            *,
            params: dict | None = None,
            headers: dict | None = None,
            timeout: int | None = None,
        ) -> FakeResponse:
            self.calls.append((method, url, dict(params or {})))
            return FakeResponse()

    fake_session = FakeSession()
    client.session = fake_session  # type: ignore[assignment]
    monkeypatch.setattr("patchy_bot.clients.plex.time.sleep", lambda _: None)

    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
    ]
    client._wait_for_section_idle = lambda *args, **kwargs: False  # type: ignore[method-assign]

    titles = client.refresh_all_by_type(["movie"])

    assert titles == ["Movies"]
    post_urls = [url for method, url, _ in fake_session.calls if method == "POST"]
    assert "http://plex.local:32400/library/sections/1/refresh" in post_urls
    put_urls = [url for method, url, _ in fake_session.calls if method == "PUT"]
    assert "http://plex.local:32400/library/sections/1/emptyTrash" not in put_urls


def test_plex_verify_remove_identity_absent_scans_all_sections_when_no_section_key() -> None:
    import xml.etree.ElementTree as ET

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")
    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
        {"key": "2", "title": "4K Movies", "type": "movie", "locations": ["/mnt/4k"], "refreshing": False},
    ]
    client._get_xml = lambda path, params=None: ET.fromstring("<MediaContainer />")  # type: ignore[method-assign]

    ok, detail = client.verify_remove_identity_absent(
        "/mnt/movies/Tires (2023)",
        "movie",
        {"verification_mode": "path_fallback", "title": "Tires"},
    )

    assert ok is True
    assert "Tires" in detail


def test_plex_verify_remove_identity_absent_fails_when_path_still_in_any_section() -> None:
    import xml.etree.ElementTree as ET

    target = "/mnt/movies/Tires (2023)"

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/srv/tv")
    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "1", "title": "Movies", "type": "movie", "locations": ["/mnt/movies"], "refreshing": False},
    ]

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


def test_plex_verify_remove_identity_absent_scans_show_sections_when_no_section_key() -> None:
    import xml.etree.ElementTree as ET

    target = "/mnt/tv/Tires/Season 01/Tires.S01E01.mkv"

    client = PlexInventoryClient("http://plex.local:32400", "token-123", "/mnt/tv")
    client._sections = lambda: [  # type: ignore[method-assign]
        {"key": "5", "title": "TV Shows", "type": "show", "locations": ["/mnt/tv"], "refreshing": False},
    ]

    def fake_get_xml_still_present(path: str, *, params: dict | None = None) -> ET.Element:
        if "/all" in path and (params or {}).get("type") == 4:
            xml = f"""<MediaContainer>
              <Video ratingKey="201" title="Tires S01E01" type="episode">
                <Media><Part file="{target}" /></Media>
              </Video>
            </MediaContainer>"""
            return ET.fromstring(xml)
        return ET.fromstring("<MediaContainer />")

    client._get_xml = fake_get_xml_still_present  # type: ignore[method-assign]

    ok, detail = client.verify_remove_identity_absent(
        target,
        "episode",
        {"verification_mode": "path_fallback", "title": "Tires S01E01"},
    )
    assert ok is False
    assert "Tires" in detail

    client._get_xml = lambda path, params=None: ET.fromstring("<MediaContainer />")  # type: ignore[method-assign]

    ok2, detail2 = client.verify_remove_identity_absent(
        target,
        "episode",
        {"verification_mode": "path_fallback", "title": "Tires S01E01"},
    )
    assert ok2 is True
    assert "Tires" in detail2


def test_remove_attempt_plex_cleanup_falls_back_to_refresh_all_when_section_key_missing(monkeypatch) -> None:
    from unittest.mock import MagicMock

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
    store.update_remove_job = MagicMock(return_value=None)

    bot = MagicMock(spec=BotApp)
    bot.plex = plex
    bot.store = store
    bot._ctx = SimpleNamespace(store=store, plex=plex)

    job = {
        "job_id": "test-job-1",
        "plex_section_key": "",
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
    assert refresh_calls == [["movie"]]


def test_remove_attempt_plex_cleanup_falls_back_to_show_type_for_episode_remove_kind(monkeypatch) -> None:
    from unittest.mock import MagicMock

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
    store.update_remove_job = MagicMock(return_value=None)

    bot = MagicMock(spec=BotApp)
    bot.plex = plex
    bot.store = store
    bot._ctx = SimpleNamespace(store=store, plex=plex)

    job = {
        "job_id": "test-job-2",
        "plex_section_key": "",
        "scan_path": "",
        "target_path": "/mnt/tv/Tires/Season 01/Tires.S01E01.mkv",
        "remove_kind": "episode",
        "plex_title": "Tires S01E01",
        "item_name": "Tires S01E01",
        "verification_json": {},
        "retry_count": 0,
    }

    result = BotApp._remove_attempt_plex_cleanup(bot, job, inline_timeout_s=10)

    assert result["status"] == "verified"
    assert refresh_calls == [["show"]]


def test_remove_attempt_plex_cleanup_falls_back_to_both_types_for_unknown_remove_kind(monkeypatch) -> None:
    from unittest.mock import MagicMock

    refresh_calls: list[list[str]] = []

    def fake_refresh_all_by_type(section_types: list[str]) -> list[str]:
        refresh_calls.append(list(section_types))
        return ["Movies", "TV Shows"]

    def fake_verify_absent(target_path: str, remove_kind: str, verification: dict | None) -> tuple[bool, str]:
        return True, "Plex media parts removed (all-section scan)"

    plex = MagicMock(spec=PlexInventoryClient)
    plex.refresh_all_by_type = fake_refresh_all_by_type
    plex.verify_remove_identity_absent = fake_verify_absent

    store = MagicMock()
    store.update_remove_job = MagicMock(return_value=None)

    bot = MagicMock(spec=BotApp)
    bot.plex = plex
    bot.store = store
    bot._ctx = SimpleNamespace(store=store, plex=plex)

    job = {
        "job_id": "test-job-3",
        "plex_section_key": "",
        "scan_path": "",
        "target_path": "/mnt/movies/Unknown (2023)",
        "remove_kind": "item",
        "plex_title": "Unknown",
        "item_name": "Unknown",
        "verification_json": {},
        "retry_count": 0,
    }

    result = BotApp._remove_attempt_plex_cleanup(bot, job, inline_timeout_s=10)

    assert result["status"] == "verified"
    assert refresh_calls == [["movie", "show"]]


# ── Auth system tests ─────────────────────────────────────────────────────────


def test_store_unlock_and_is_unlocked(tmp_path):
    """Correct password flow: user unlocks and is immediately recognised as unlocked."""
    s = Store(str(tmp_path / "auth.sqlite3"))

    assert s.is_unlocked(99) is False
    s.unlock_user(99, ttl_s=0)
    assert s.is_unlocked(99) is True


def test_store_is_unlocked_treats_past_timestamp_as_locked(tmp_path):
    """is_unlocked() returns False for any row with a past unlocked_until (legacy rows from before permanent-unlock enforcement)."""
    s = Store(str(tmp_path / "auth_ttl.sqlite3"))

    # Directly insert an already-expired record
    expired_ts = now_ts() - 1  # 1 second in the past
    with s._create_connection() as conn:
        conn.execute(
            "INSERT INTO user_auth(user_id, unlocked_until, updated_at) VALUES(?,?,?)",
            (7, expired_ts, now_ts()),
        )
        conn.commit()

    assert s.is_unlocked(7) is False


def test_store_lockout_after_max_attempts(tmp_path):
    """Five consecutive failures trigger a lockout; the sixth attempt confirms it."""
    s = Store(str(tmp_path / "auth_lock.sqlite3"))

    for _ in range(4):
        locked = s.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
        assert locked is False

    # Fifth failure should trigger the lock
    locked = s.record_auth_failure(user_id=55, max_attempts=5, lockout_s=900)
    assert locked is True
    assert s.is_auth_locked(55) is True


def test_store_lock_user_removes_session(tmp_path):
    """logout: lock_user() removes the session so is_unlocked returns False."""
    s = Store(str(tmp_path / "auth_logout.sqlite3"))

    s.unlock_user(33, ttl_s=0)
    assert s.is_unlocked(33) is True

    s.lock_user(33)
    assert s.is_unlocked(33) is False


def test_store_auth_attempts_cleanup_prunes_stale_rows(tmp_path):
    """cleanup() removes old, expired auth_attempts rows but keeps active lockouts.
    Note: Store.cleanup only cleans up searches. Auth attempts are cleaned
    via direct SQL here to verify the schema supports the expected pruning."""
    s = Store(str(tmp_path / "auth_cleanup.sqlite3"))

    old_ts = now_ts() - 48 * 3600  # 48 h ago — older than default 24 h window
    locked_until_future = now_ts() + 900

    # Insert a stale row that is no longer locked (locked_until = 0)
    with s._create_connection() as conn:
        conn.execute(
            "INSERT INTO auth_attempts(user_id, fail_count, first_fail_at, locked_until) VALUES(?,?,?,?)",
            (101, 3, old_ts, 0),
        )
        # Insert a row that is still actively locked — must NOT be pruned
        conn.execute(
            "INSERT INTO auth_attempts(user_id, fail_count, first_fail_at, locked_until) VALUES(?,?,?,?)",
            (102, 5, old_ts, locked_until_future),
        )
        conn.commit()

    # Prune stale unlocked rows (first_fail_at older than 24h AND not currently locked)
    cutoff = now_ts() - 24 * 3600
    with s._create_connection() as conn:
        conn.execute(
            "DELETE FROM auth_attempts WHERE first_fail_at < ? AND locked_until <= ?",
            (cutoff, now_ts()),
        )
        conn.commit()

    # Stale unlocked row should be gone
    with s._create_connection() as conn:
        row = conn.execute("SELECT 1 FROM auth_attempts WHERE user_id = 101").fetchone()
        assert row is None

    # Still-locked row must remain
    with s._create_connection() as conn:
        row = conn.execute("SELECT 1 FROM auth_attempts WHERE user_id = 102").fetchone()
        assert row is not None


def test_render_movie_ui_edits_existing_movie_message() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            return DummyMessage(self, int(kwargs["chat_id"]), int(kwargs["message_id"]))  # pyright: ignore[reportArgumentType]

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 999)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {"mode": "movie", "stage": "await_title", "movie_ui_chat_id": 100, "movie_ui_message_id": 321}

    rendered = asyncio.run(BotApp._render_flow_ui(app, 77, anchor, flow, "Updated movie UI", flow_key="movie"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 321
    assert len(bot_api.edit_calls) == 1
    assert anchor.reply_calls == []
    assert app.user_flow[77]["movie_ui_message_id"] == 321


def test_render_movie_ui_falls_back_to_new_message_when_edit_fails() -> None:
    class DummyBotApi:
        def __init__(self) -> None:
            self.edit_calls: list[dict[str, object]] = []

        async def edit_message_text(self, **kwargs: object):
            self.edit_calls.append(kwargs)
            raise TelegramError("message to edit not found")

        async def edit_message_reply_markup(self, **kwargs: object):
            pass

    class DummyMessage:
        def __init__(self, bot: DummyBotApi, chat_id: int, message_id: int) -> None:
            self._bot = bot
            self.chat_id = chat_id
            self.message_id = message_id
            self.reply_calls: list[dict[str, object]] = []

        def get_bot(self) -> DummyBotApi:
            return self._bot

        async def reply_text(self, text: str, **kwargs: object):
            self.reply_calls.append({"text": text, **kwargs})
            return DummyMessage(self._bot, self.chat_id, 555)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _remember_flow_ui_message = BotApp._remember_flow_ui_message
        _strip_old_keyboard = BotApp._strip_old_keyboard

    app = DummyApp()
    bot_api = DummyBotApi()
    anchor = DummyMessage(bot_api, 100, 200)
    flow = {"mode": "movie", "stage": "await_title", "movie_ui_chat_id": 100, "movie_ui_message_id": 321}

    rendered = asyncio.run(BotApp._render_flow_ui(app, 77, anchor, flow, "Updated movie UI", flow_key="movie"))  # pyright: ignore[reportArgumentType]

    assert rendered.chat_id == 100
    assert rendered.message_id == 555
    assert len(bot_api.edit_calls) == 1
    assert len(anchor.reply_calls) == 1
    assert app.user_flow[77]["movie_ui_message_id"] == 555


def test_movie_cancel_renders_movie_specific_screen() -> None:
    cancel_calls: list[dict[str, object]] = []

    class DummyChat:
        def __init__(self) -> None:
            self.type = "private"

    class DummyMessage:
        def __init__(self) -> None:
            self.chat = DummyChat()
            self.deleted = 0

        async def delete(self) -> None:
            self.deleted += 1

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _get_flow = BotApp._get_flow
        _clear_flow = BotApp._clear_flow
        _cleanup_private_user_message = BotApp._cleanup_private_user_message
        _remember_flow_ui_message = BotApp._remember_flow_ui_message

        async def _render_flow_ui(self, user_id, anchor, flow, text, *, flow_key="movie", reply_markup=None, **kwargs):
            cancel_calls.append({"user_id": user_id, "text": text})

    app = DummyApp()
    msg = DummyMessage()
    app.user_flow[42] = {"mode": "movie", "stage": "await_title"}

    async def _run():
        flow = app._get_flow(42)
        await app._cleanup_private_user_message(msg)
        flow_snapshot = dict(flow)  # pyright: ignore[reportArgumentType, reportCallIssue]
        app._clear_flow(42)
        from telegram import InlineKeyboardMarkup

        await app._render_flow_ui(
            42,
            msg,
            flow_snapshot,
            "<b>🎬 Movie Search Cancelled</b>\n\nTap Movie Search to start again.",
            flow_key="movie",
            reply_markup=InlineKeyboardMarkup([]),
        )

    asyncio.run(_run())

    assert msg.deleted == 1
    assert app._get_flow(42) is None
    assert len(cancel_calls) == 1
    assert "Movie Search Cancelled" in cancel_calls[0]["text"]  # pyright: ignore[reportOperatorIssue]


def test_movie_title_submission_calls_cleanup_private() -> None:
    cleanup_called: list[object] = []

    class DummyChat:
        def __init__(self) -> None:
            self.type = "private"

    class DummyMessage:
        def __init__(self) -> None:
            self.chat = DummyChat()
            self.deleted = 0

        async def delete(self) -> None:
            self.deleted += 1
            cleanup_called.append(self)

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _set_flow = BotApp._set_flow
        _get_flow = BotApp._get_flow
        _clear_flow = BotApp._clear_flow
        _cleanup_private_user_message = BotApp._cleanup_private_user_message

    app = DummyApp()
    msg = DummyMessage()
    app.user_flow[7] = {"mode": "movie", "stage": "await_title"}

    async def _run():
        flow = app._get_flow(7)
        assert flow is not None
        await app._cleanup_private_user_message(msg)
        app._clear_flow(7)

    asyncio.run(_run())

    assert len(cleanup_called) == 1
    assert msg.deleted == 1


def test_movie_noresult_footer_uses_menu_movie_back_data() -> None:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    class DummyApp:
        def __init__(self) -> None:
            self.user_flow: dict[int, dict[str, object]] = {}
            self._ctx = SimpleNamespace(user_flow=self.user_flow)

        _nav_footer = BotApp._nav_footer

    app = DummyApp()
    movie_flow: dict[str, object] = {"mode": "movie", "stage": "await_title"}

    kb_rows: list[list[InlineKeyboardButton]] = []
    kb_rows.append([InlineKeyboardButton("🚫 Show Everything", callback_data="nr:unfiltered")])
    if isinstance(movie_flow, dict):
        kb_rows.extend(app._nav_footer(back_data="menu:movie"))

    markup = InlineKeyboardMarkup(kb_rows)
    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    back_buttons = [b for b in all_buttons if b.callback_data and "menu:movie" in b.callback_data]  # pyright: ignore[reportOperatorIssue]
    assert len(back_buttons) >= 1


# ---------------------------------------------------------------------------
# Multi-episode premiere batch download tests
# ---------------------------------------------------------------------------


def test_schedule_apply_tracking_mode_multi_episode_premiere(monkeypatch) -> None:
    """Three released episodes all appear in actionable_missing_codes."""
    from patchy_bot.handlers.schedule import schedule_apply_tracking_mode

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 3600)

    ctx = SimpleNamespace()
    past = NOW - 7200
    track = {"auto_state_json": {"enabled": True, "tracking_mode": "upcoming"}}
    probe = {
        "all_missing_codes": ["S01E01", "S01E02", "S01E03"],
        "episode_order": ["S01E01", "S01E02", "S01E03"],
        "present_codes": [],
        "pending_codes": [],
        "episode_air": {"S01E01": past, "S01E02": past, "S01E03": past},
    }
    result = schedule_apply_tracking_mode(ctx, track, probe)  # pyright: ignore[reportArgumentType]
    assert result["actionable_missing_codes"] == ["S01E01", "S01E02", "S01E03"]
    assert result["tracking_code"] == "S01E01"
    assert result["tracked_missing_codes"] == ["S01E01", "S01E02", "S01E03"]


def test_schedule_apply_tracking_mode_stops_at_unreleased(monkeypatch) -> None:
    """Collection stops at the first unreleased episode."""
    from patchy_bot.handlers.schedule import schedule_apply_tracking_mode

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 3600)

    ctx = SimpleNamespace()
    past = NOW - 7200
    future = NOW + 86400
    track = {"auto_state_json": {"enabled": True, "tracking_mode": "upcoming", "next_code": "S01E01"}}
    probe = {
        "all_missing_codes": ["S01E01", "S01E02", "S01E03", "S01E04"],
        "episode_order": ["S01E01", "S01E02", "S01E03", "S01E04"],
        "present_codes": [],
        "pending_codes": [],
        "episode_air": {"S01E01": past, "S01E02": past, "S01E03": future, "S01E04": future},
    }
    result = schedule_apply_tracking_mode(ctx, track, probe)  # pyright: ignore[reportArgumentType]
    assert result["actionable_missing_codes"] == ["S01E01", "S01E02"]
    assert result["tracking_code"] == "S01E01"


def test_schedule_apply_tracking_mode_skips_pending_in_batch(monkeypatch) -> None:
    """Pending episodes are excluded from actionable but the loop continues past them."""
    from patchy_bot.handlers.schedule import schedule_apply_tracking_mode

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 3600)

    ctx = SimpleNamespace()
    past = NOW - 7200
    track = {"auto_state_json": {"enabled": True, "tracking_mode": "upcoming"}}
    probe = {
        "all_missing_codes": ["S01E01", "S01E02", "S01E03"],
        "episode_order": ["S01E01", "S01E02", "S01E03"],
        "present_codes": [],
        "pending_codes": ["S01E02"],
        "episode_air": {"S01E01": past, "S01E02": past, "S01E03": past},
    }
    result = schedule_apply_tracking_mode(ctx, track, probe)  # pyright: ignore[reportArgumentType]
    assert result["actionable_missing_codes"] == ["S01E01", "S01E03"]
    assert "S01E02" not in result["actionable_missing_codes"]


def test_schedule_apply_tracking_mode_single_episode_still_works(monkeypatch) -> None:
    """Single released episode followed by unreleased behaves as before."""
    from patchy_bot.handlers.schedule import schedule_apply_tracking_mode

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 3600)

    ctx = SimpleNamespace()
    past = NOW - 7200
    future = NOW + 86400
    track = {"auto_state_json": {"enabled": True, "tracking_mode": "upcoming", "next_code": "S01E01"}}
    probe = {
        "all_missing_codes": ["S01E01", "S01E02"],
        "episode_order": ["S01E01", "S01E02"],
        "present_codes": [],
        "pending_codes": [],
        "episode_air": {"S01E01": past, "S01E02": future},
    }
    result = schedule_apply_tracking_mode(ctx, track, probe)  # pyright: ignore[reportArgumentType]
    assert result["actionable_missing_codes"] == ["S01E01"]


def test_schedule_next_check_known_future_air_date(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_next_check_at

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 5400)

    ctx = SimpleNamespace()
    air = NOW + 3600
    result = schedule_next_check_at(ctx, air, has_actionable_missing=False, has_unknown_missing=False, auto_state={})  # pyright: ignore[reportArgumentType]
    assert result == air + 5400


def test_schedule_next_check_released_episode(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_next_check_at

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 5400)

    ctx = SimpleNamespace()
    result = schedule_next_check_at(ctx, None, has_actionable_missing=True, has_unknown_missing=False, auto_state={})  # pyright: ignore[reportArgumentType]
    assert result == NOW + 300


def test_schedule_next_check_unknown_air_date_slow_poll(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_next_check_at

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 5400)

    ctx = SimpleNamespace()
    result = schedule_next_check_at(ctx, None, has_actionable_missing=False, has_unknown_missing=True, auto_state={})  # pyright: ignore[reportArgumentType]
    assert result == NOW + 12 * 3600


def test_schedule_next_check_no_schedule_info(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_next_check_at

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 5400)

    ctx = SimpleNamespace()
    result = schedule_next_check_at(ctx, None, has_actionable_missing=False, has_unknown_missing=False, auto_state={})  # pyright: ignore[reportArgumentType]
    assert result == NOW + 24 * 3600


def test_schedule_next_check_backoff_wins_over_air_date(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_next_check_at

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 5400)

    ctx = SimpleNamespace()
    air = NOW + 3600
    backoff = air + 5400 + 10_000
    result = schedule_next_check_at(
        ctx,  # pyright: ignore[reportArgumentType]
        air,
        has_actionable_missing=False,
        has_unknown_missing=False,
        auto_state={"next_auto_retry_at": backoff},
    )
    assert result == backoff


def test_schedule_next_check_air_date_past_grace(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_next_check_at

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 5400)

    ctx = SimpleNamespace()
    past_air = NOW - 10_000
    result = schedule_next_check_at(
        ctx,  # pyright: ignore[reportArgumentType]
        past_air,
        has_actionable_missing=False,
        has_unknown_missing=False,
        auto_state={},
    )
    assert result == NOW + 300


def test_apply_tracking_mode_unknown_air_date_not_actionable(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_apply_tracking_mode

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 3600)

    ctx = SimpleNamespace()
    track = {"auto_state_json": {"enabled": True, "tracking_mode": "upcoming"}}
    probe = {
        "all_missing_codes": ["S01E01"],
        "episode_order": ["S01E01"],
        "present_codes": [],
        "pending_codes": [],
        "episode_air": {"S01E01": None},
    }
    result = schedule_apply_tracking_mode(ctx, track, probe)  # pyright: ignore[reportArgumentType]
    assert result["tracked_missing_codes"] == ["S01E01"]
    assert result["actionable_missing_codes"] == []


def test_apply_tracking_mode_mixed_known_unknown(monkeypatch) -> None:
    from patchy_bot.handlers.schedule import schedule_apply_tracking_mode

    NOW = 1_000_000
    monkeypatch.setattr("patchy_bot.handlers.schedule.now_ts", lambda: NOW)
    monkeypatch.setattr("patchy_bot.handlers.schedule.schedule_release_grace_s", lambda: 3600)

    ctx = SimpleNamespace()
    track = {
        "auto_state_json": {
            "enabled": True,
            "tracking_mode": "upcoming",
            "next_code": "S01E01",
        }
    }
    probe = {
        "all_missing_codes": ["S01E01", "S01E02"],
        "episode_order": ["S01E01", "S01E02"],
        "present_codes": [],
        "pending_codes": [],
        "episode_air": {"S01E01": NOW - 7200, "S01E02": None},
    }
    result = schedule_apply_tracking_mode(ctx, track, probe)  # pyright: ignore[reportArgumentType]
    assert "S01E01" in result["actionable_missing_codes"]
    assert "S01E02" not in result["actionable_missing_codes"]
    assert "S01E02" in result["tracked_missing_codes"]


def test_schedule_is_season_complete_last_episode_present() -> None:
    from patchy_bot.handlers.schedule import schedule_is_season_complete

    probe = {
        "episode_order": ["S01E01", "S01E02", "S01E03"],
        "present_codes": ["S01E01", "S01E02", "S01E03"],
    }
    assert schedule_is_season_complete(probe) is True


def test_schedule_is_season_complete_last_episode_absent() -> None:
    from patchy_bot.handlers.schedule import schedule_is_season_complete

    probe = {
        "episode_order": ["S01E01", "S01E02", "S01E03"],
        "present_codes": ["S01E01", "S01E02"],
    }
    assert schedule_is_season_complete(probe) is False


def test_schedule_is_season_complete_empty_episode_order() -> None:
    from patchy_bot.handlers.schedule import schedule_is_season_complete

    probe = {
        "episode_order": [],
        "present_codes": ["S01E01"],
    }
    assert schedule_is_season_complete(probe) is False


def test_schedule_is_season_complete_empty_present_codes() -> None:
    from patchy_bot.handlers.schedule import schedule_is_season_complete

    probe = {
        "episode_order": ["S01E01", "S01E02", "S01E03"],
        "present_codes": [],
    }
    assert schedule_is_season_complete(probe) is False


def test_schedule_is_season_complete_middle_episodes_missing_but_last_present() -> None:
    from patchy_bot.handlers.schedule import schedule_is_season_complete

    probe = {
        "episode_order": ["S01E01", "S01E02", "S01E03", "S01E04", "S01E05"],
        "present_codes": ["S01E03", "S01E04", "S01E05"],
    }
    assert schedule_is_season_complete(probe) is True


def test_schedule_is_season_complete_only_first_present() -> None:
    from patchy_bot.handlers.schedule import schedule_is_season_complete

    probe = {
        "episode_order": ["S01E01", "S01E02", "S01E03"],
        "present_codes": ["S01E01"],
    }
    assert schedule_is_season_complete(probe) is False


# ---------------------------------------------------------------------------
# Strict guided parser — parse_strict_season_episode
# ---------------------------------------------------------------------------


def test_parse_strict_season_episode_accepts_s1e2() -> None:
    from patchy_bot.handlers.search import parse_strict_season_episode

    assert parse_strict_season_episode("S1E2") == (1, 2)


def test_parse_strict_season_episode_accepts_season_episode_words() -> None:
    from patchy_bot.handlers.search import parse_strict_season_episode

    assert parse_strict_season_episode("season 1 episode 2") == (1, 2)


def test_parse_strict_season_episode_rejects_season_only() -> None:
    from patchy_bot.handlers.search import parse_strict_season_episode

    assert parse_strict_season_episode("season 2") is None


def test_parse_strict_season_episode_rejects_episode_only() -> None:
    from patchy_bot.handlers.search import parse_strict_season_episode

    assert parse_strict_season_episode("episode 5") is None


# ---------------------------------------------------------------------------
# Season number parser — parse_season_number
# ---------------------------------------------------------------------------


def test_parse_season_number_bare_digit() -> None:
    from patchy_bot.handlers.search import parse_season_number

    assert parse_season_number("3") == 3


def test_parse_season_number_s_prefix() -> None:
    from patchy_bot.handlers.search import parse_season_number

    assert parse_season_number("S2") == 2


def test_parse_season_number_season_word() -> None:
    from patchy_bot.handlers.search import parse_season_number

    assert parse_season_number("season 1") == 1


def test_parse_season_number_rejects_nonsense() -> None:
    from patchy_bot.handlers.search import parse_season_number

    assert parse_season_number("hello") is None


# ---------------------------------------------------------------------------
# Episode number parser — parse_episode_number
# ---------------------------------------------------------------------------


def test_parse_episode_number_bare_digit() -> None:
    from patchy_bot.handlers.search import parse_episode_number

    assert parse_episode_number("5") == 5


def test_parse_episode_number_e_prefix() -> None:
    from patchy_bot.handlers.search import parse_episode_number

    assert parse_episode_number("E7") == 7


def test_parse_episode_number_episode_word() -> None:
    from patchy_bot.handlers.search import parse_episode_number

    assert parse_episode_number("episode 3") == 3


def test_parse_episode_number_rejects_nonsense() -> None:
    from patchy_bot.handlers.search import parse_episode_number

    assert parse_episode_number("hello") is None
