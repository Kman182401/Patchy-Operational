"""Tests for the movie schedule tracking feature."""

from __future__ import annotations

from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchy_bot.clients.tv_metadata import MovieReleaseDates, MovieReleaseStatus, TVMetadataClient
from patchy_bot.handlers.schedule import on_cb_movie_schedule
from patchy_bot.store import Store
from patchy_bot.types import HandlerContext
from patchy_bot.utils import now_ts

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> Store:
    s = Store(":memory:")
    yield s
    s.close()


@pytest.fixture
def tvmeta() -> TVMetadataClient:
    return TVMetadataClient(tmdb_api_key="test-key")


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


class TestMovieTrackCRUD:
    def test_create_and_get(self, store: Store) -> None:
        tid = store.create_movie_track(100, 456, "Test Movie", 2024, "theatrical", 1700000000, "Test Movie 2024")
        assert tid  # non-empty string
        track = store.get_movie_track(tid)
        assert track is not None
        assert track["user_id"] == 100
        assert track["tmdb_id"] == 456
        assert track["title"] == "Test Movie"
        assert track["year"] == 2024
        assert track["release_date_type"] == "theatrical"
        assert track["release_date_ts"] == 1700000000
        assert track["search_query"] == "Test Movie 2024"
        assert track["status"] == "pending"
        assert track["notified"] == 0

    def test_get_pending_respects_release_date(self, store: Store) -> None:
        """Track with future release date should NOT be returned by get_pending."""
        future_ts = now_ts() + 86400 * 30  # 30 days from now
        past_ts = now_ts() - 86400  # yesterday
        store.create_movie_track(100, 1, "Future Movie", 2025, "theatrical", future_ts, "Future Movie 2025")
        store.create_movie_track(100, 2, "Past Movie", 2024, "theatrical", past_ts, "Past Movie 2024")
        pending = store.get_pending_movie_tracks()
        titles = [t["title"] for t in pending]
        assert "Past Movie" in titles
        assert "Future Movie" not in titles

    def test_get_pending_respects_next_check(self, store: Store) -> None:
        """Track with next_check_ts in the future should NOT be returned."""
        past_ts = now_ts() - 86400
        tid = store.create_movie_track(100, 3, "Movie A", 2024, "digital", past_ts, "Movie A 2024")
        # Set next_check_ts far in the future
        store.update_movie_track_status(tid, next_check_ts=now_ts() + 7200)
        pending = store.get_pending_movie_tracks()
        assert all(t["track_id"] != tid for t in pending)

    def test_update_status(self, store: Store) -> None:
        tid = store.create_movie_track(100, 4, "Movie B", 2024, "digital", 1700000000, "Movie B 2024")
        store.update_movie_track_status(
            tid, status="downloading", torrent_hash="abc123", notified=True, next_check_ts=999
        )
        track = store.get_movie_track(tid)
        assert track is not None
        assert track["status"] == "downloading"
        assert track["torrent_hash"] == "abc123"
        assert track["notified"] == 1
        assert track["next_check_ts"] == 999

    def test_delete(self, store: Store) -> None:
        tid = store.create_movie_track(100, 5, "Movie C", 2024, "physical", 1700000000, "Movie C 2024")
        assert store.get_movie_track(tid) is not None
        store.delete_movie_track(tid)
        assert store.get_movie_track(tid) is None

    def test_exists_for_tmdb(self, store: Store) -> None:
        store.create_movie_track(100, 6, "Movie D", 2024, "theatrical", 1700000000, "Movie D 2024")
        assert store.movie_track_exists_for_tmdb(100, 6) is True
        assert store.movie_track_exists_for_tmdb(100, 999) is False
        assert store.movie_track_exists_for_tmdb(999, 6) is False  # different user

    def test_get_downloading(self, store: Store) -> None:
        tid = store.create_movie_track(100, 7, "Movie E", 2024, "digital", 1700000000, "Movie E 2024")
        assert len(store.get_downloading_movie_tracks()) == 0
        store.update_movie_track_status(tid, status="downloading")
        downloading = store.get_downloading_movie_tracks()
        assert len(downloading) == 1
        assert downloading[0]["track_id"] == tid

    def test_get_tracks_for_user(self, store: Store) -> None:
        store.create_movie_track(100, 8, "User1 Movie", 2024, "theatrical", 1700000000, "q1")
        store.create_movie_track(200, 9, "User2 Movie", 2024, "theatrical", 1700000000, "q2")
        user1_tracks = store.get_movie_tracks_for_user(100)
        assert len(user1_tracks) == 1
        assert user1_tracks[0]["title"] == "User1 Movie"

    def test_create_returns_unique_ids(self, store: Store) -> None:
        """Two tracks created back-to-back must have different IDs."""
        tid1 = store.create_movie_track(100, 10, "Alpha", 2024, "theatrical", 1700000000, "Alpha 2024")
        tid2 = store.create_movie_track(100, 11, "Beta", 2024, "digital", 1700000000, "Beta 2024")
        assert tid1 != tid2

    def test_get_nonexistent_track_returns_none(self, store: Store) -> None:
        assert store.get_movie_track("does-not-exist") is None

    def test_update_status_error_text(self, store: Store) -> None:
        tid = store.create_movie_track(100, 12, "Movie F", 2024, "theatrical", 1700000000, "Movie F 2024")
        store.update_movie_track_status(tid, status="error", error_text="torrent not found")
        track = store.get_movie_track(tid)
        assert track is not None
        assert track["status"] == "error"
        assert track["error_text"] == "torrent not found"

    def test_get_pending_only_returns_pending_status(self, store: Store) -> None:
        """Tracks with status != 'pending' should never appear in get_pending."""
        past_ts = now_ts() - 86400
        tid = store.create_movie_track(100, 13, "Downloading Movie", 2024, "theatrical", past_ts, "q")
        store.update_movie_track_status(tid, status="downloading")
        pending = store.get_pending_movie_tracks()
        assert all(t["track_id"] != tid for t in pending)

    def test_year_can_be_none(self, store: Store) -> None:
        """year=None should be stored and retrieved without error."""
        tid = store.create_movie_track(100, 14, "No Year Movie", None, "theatrical", 1700000000, "No Year Movie")
        track = store.get_movie_track(tid)
        assert track is not None
        assert track["year"] is None

    def test_get_tracks_for_user_empty(self, store: Store) -> None:
        tracks = store.get_movie_tracks_for_user(99999)
        assert tracks == []

    def test_get_downloading_empty(self, store: Store) -> None:
        assert store.get_downloading_movie_tracks() == []

    def test_get_pending_empty(self, store: Store) -> None:
        assert store.get_pending_movie_tracks() == []


# ---------------------------------------------------------------------------
# TMDB client tests
# ---------------------------------------------------------------------------


class TestTMDBMovieMethods:
    def test_search_returns_upcoming_movie(self, tvmeta: TVMetadataClient) -> None:
        seen_params: list[dict[str, Any]] = []
        calls = 0

        def fake_get_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            seen_params.append(dict(params or {}))
            if calls == 1:
                return {"results": []}
            return {
                "results": [
                    {"id": 123, "title": "Scary Movie 6", "release_date": "", "overview": "", "popularity": 1.0}
                ]
            }

        with patch.object(tvmeta, "_get_json", side_effect=fake_get_json):
            results = tvmeta.search_movies("Scary Movie 6")

        assert results
        assert results[0]["title"] == "Scary Movie 6"
        assert calls == 2
        assert all("primary_release_year" not in p for p in seen_params)
        assert all("region" not in p for p in seen_params)

    def test_search_movies_returns_top5(self, tvmeta: TVMetadataClient) -> None:
        fake_results = [
            {
                "id": i,
                "title": f"Movie {i}",
                "release_date": "2024-06-15",
                "overview": "desc",
                "popularity": 10.0,
            }
            for i in range(10)
        ]
        fake_response: dict[str, Any] = {"results": fake_results}
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            results = tvmeta.search_movies("test")
        assert len(results) == 5
        assert results[0]["tmdb_id"] == 0

    def test_search_movies_empty_on_error(self, tvmeta: TVMetadataClient) -> None:
        with patch.object(tvmeta, "_get_json", side_effect=RuntimeError("HTTP 500")):
            results = tvmeta.search_movies("test")
        assert results == []

    def test_search_movies_no_api_key(self) -> None:
        client = TVMetadataClient(tmdb_api_key=None)
        results = client.search_movies("test")
        assert results == []

    def test_get_release_dates_us(self, tvmeta: TVMetadataClient) -> None:
        fake_response: dict[str, Any] = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 3, "release_date": "2024-07-04T00:00:00.000Z"},
                        {"type": 4, "release_date": "2024-09-15T00:00:00.000Z"},
                    ],
                },
                {
                    "iso_3166_1": "GB",
                    "release_dates": [
                        {"type": 3, "release_date": "2024-07-11T00:00:00.000Z"},
                    ],
                },
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            dates = tvmeta.get_movie_release_dates(12345, "US")
        assert "theatrical" in dates
        assert "digital" in dates
        assert "physical" not in dates
        assert isinstance(dates["theatrical"], int)
        assert dates["theatrical"] > 0

    def test_get_release_dates_region_missing(self, tvmeta: TVMetadataClient) -> None:
        fake_response: dict[str, Any] = {
            "results": [
                {
                    "iso_3166_1": "GB",
                    "release_dates": [{"type": 3, "release_date": "2024-07-11T00:00:00.000Z"}],
                },
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            dates = tvmeta.get_movie_release_dates(12345, "US")
        assert dates == {}

    def test_get_release_dates_no_api_key(self) -> None:
        client = TVMetadataClient(tmdb_api_key=None)
        dates = client.get_movie_release_dates(12345, "US")
        assert dates == {}

    def test_get_release_dates_error_returns_empty(self, tvmeta: TVMetadataClient) -> None:
        with patch.object(tvmeta, "_get_json", side_effect=RuntimeError("HTTP 401")):
            dates = tvmeta.get_movie_release_dates(12345, "US")
        assert dates == {}

    def test_search_movies_result_fields(self, tvmeta: TVMetadataClient) -> None:
        """Each result must have the expected keys."""
        fake_response: dict[str, Any] = {
            "results": [
                {
                    "id": 42,
                    "title": "Inception",
                    "release_date": "2010-07-16",
                    "overview": "A thief who enters dreams.",
                    "popularity": 88.5,
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            results = tvmeta.search_movies("inception")
        assert len(results) == 1
        r = results[0]
        assert r["tmdb_id"] == 42
        assert r["title"] == "Inception"
        assert r["year"] == 2010
        assert r["overview"] == "A thief who enters dreams."
        assert r["popularity"] == 88.5

    def test_search_movies_missing_release_date_year_is_none(self, tvmeta: TVMetadataClient) -> None:
        """Results with missing or blank release_date must have year=None."""
        fake_response: dict[str, Any] = {
            "results": [{"id": 99, "title": "Unknown Year", "release_date": "", "overview": "", "popularity": 1.0}]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            results = tvmeta.search_movies("unknown")
        assert results[0]["year"] is None

    def test_get_release_dates_physical_type(self, tvmeta: TVMetadataClient) -> None:
        """Type 5 = physical should be mapped to 'physical' key."""
        fake_response: dict[str, Any] = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 5, "release_date": "2024-11-20T00:00:00.000Z"},
                    ],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            dates = tvmeta.get_movie_release_dates(999, "US")
        assert "physical" in dates
        assert "theatrical" not in dates
        assert "digital" not in dates

    def test_get_release_dates_unknown_type_ignored(self, tvmeta: TVMetadataClient) -> None:
        """Unknown release type numbers (e.g. 1, 2, 6) must be silently ignored."""
        fake_response: dict[str, Any] = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 1, "release_date": "2024-01-01T00:00:00.000Z"},
                        {"type": 2, "release_date": "2024-02-01T00:00:00.000Z"},
                    ],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            dates = tvmeta.get_movie_release_dates(999, "US")
        assert dates == {}

    def test_search_movies_fewer_than_5_results(self, tvmeta: TVMetadataClient) -> None:
        """When TMDB returns fewer than 5 results, all are returned."""
        fake_response: dict[str, Any] = {
            "results": [
                {"id": i, "title": f"Film {i}", "release_date": "2022-01-01", "overview": "", "popularity": 5.0}
                for i in range(3)
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            results = tvmeta.search_movies("film")
        assert len(results) == 3

    def test_search_movies_empty_results_list(self, tvmeta: TVMetadataClient) -> None:
        fake_response: dict[str, Any] = {"results": []}
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            results = tvmeta.search_movies("nothing")
        assert results == []


# ---------------------------------------------------------------------------
# MovieReleaseDates / get_movie_home_release tests
# ---------------------------------------------------------------------------


class TestMovieReleaseDates:
    def test_home_available_past_digital(self, tvmeta: TVMetadataClient) -> None:
        """Digital date in the past → HOME_AVAILABLE."""
        past_date = "2020-01-15T00:00:00.000Z"
        fake_response = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 3, "release_date": "2019-10-01T00:00:00.000Z"},
                        {"type": 4, "release_date": past_date},
                    ],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.HOME_AVAILABLE
        assert result.digital_ts is not None
        assert result.home_release_ts is not None
        assert not result.digital_estimated

    def test_waiting_home_future_digital(self, tvmeta: TVMetadataClient) -> None:
        """Digital date in the future → WAITING_HOME."""
        future_date = "2099-06-01T00:00:00.000Z"
        fake_response = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 3, "release_date": "2020-01-01T00:00:00.000Z"},
                        {"type": 4, "release_date": future_date},
                    ],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.WAITING_HOME
        assert result.digital_ts is not None
        assert result.home_release_ts is not None

    def test_in_theaters_fallback_45_days(self, tvmeta: TVMetadataClient) -> None:
        """Theatrical date exists, no digital → estimated digital = theatrical + 45 days."""
        import time
        from datetime import datetime

        # Theatrical 10 days ago; estimated digital = 35 days from now → WAITING_HOME
        theatrical_ts = int(time.time()) - 10 * 86400
        theatrical_iso = datetime.fromtimestamp(theatrical_ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        fake_response = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 3, "release_date": theatrical_iso},
                    ],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.WAITING_HOME
        assert result.digital_estimated is True
        assert result.digital_ts is not None
        # Estimated digital should be ~45 days after theatrical
        assert abs(result.digital_ts - (theatrical_ts + 45 * 86400)) < 86400

    def test_pre_theatrical_no_dates(self, tvmeta: TVMetadataClient) -> None:
        """No theatrical date at all → PRE_THEATRICAL."""
        fake_response = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.PRE_THEATRICAL

    def test_pre_theatrical_future_theatrical(self, tvmeta: TVMetadataClient) -> None:
        """Theatrical in the future → PRE_THEATRICAL."""
        fake_response = {
            "results": [
                {
                    "iso_3166_1": "US",
                    "release_dates": [
                        {"type": 3, "release_date": "2099-12-25T00:00:00.000Z"},
                    ],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.PRE_THEATRICAL

    def test_api_error_returns_unknown(self, tvmeta: TVMetadataClient) -> None:
        """TMDB HTTP error → UNKNOWN status, no exception raised."""
        with patch.object(tvmeta, "_get_json", side_effect=RuntimeError("HTTP 500")):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.UNKNOWN
        assert result.tmdb_id == 123

    def test_no_api_key_returns_unknown(self) -> None:
        """No API key → UNKNOWN status."""
        client = TVMetadataClient(tmdb_api_key=None)
        result = client.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.UNKNOWN

    def test_region_not_found_returns_unknown(self, tvmeta: TVMetadataClient) -> None:
        """Region not in results → UNKNOWN."""
        fake_response = {
            "results": [
                {
                    "iso_3166_1": "GB",
                    "release_dates": [{"type": 3, "release_date": "2024-01-01T00:00:00.000Z"}],
                }
            ]
        }
        with patch.object(tvmeta, "_get_json", return_value=fake_response):
            result = tvmeta.get_movie_home_release(123, "US")
        assert result.status == MovieReleaseStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Release gate store tests
# ---------------------------------------------------------------------------


class TestReleaseGateStore:
    def test_update_and_read_release_dates(self, store: Store) -> None:
        tid = store.create_movie_track(100, 456, "Test Movie", 2024, "theatrical", 1700000000, "Test 2024")
        store.update_movie_release_dates(tid, 1700000000, 1703888000, None, 1703888000, False, "waiting_home")
        track = store.get_movie_track(tid)
        assert track is not None
        assert track["theatrical_ts"] == 1700000000
        assert track["digital_ts"] == 1703888000
        assert track["physical_ts"] is None
        assert track["home_release_ts"] == 1703888000
        assert track["digital_estimated"] == 0
        assert track["release_status"] == "waiting_home"
        assert track["last_release_check_ts"] is not None

    def test_update_estimated_flag(self, store: Store) -> None:
        tid = store.create_movie_track(100, 457, "Est Movie", 2024, "theatrical", 1700000000, "Est 2024")
        store.update_movie_release_dates(tid, 1700000000, 1703888000, None, 1703888000, True, "waiting_home", True)
        track = store.get_movie_track(tid)
        assert track["digital_estimated"] == 1
        assert track["home_date_is_inferred"] == 1

    def test_home_date_is_inferred_column_exists(self, store: Store) -> None:
        cols = {
            row[1] for row in store._conn.execute("PRAGMA table_info(movie_tracks)").fetchall()  # type: ignore[attr-defined]
        }
        assert "home_date_is_inferred" in cols

    def test_get_movies_due_release_check_returns_unchecked(self, store: Store) -> None:
        """Tracks with no last_release_check_ts should be returned."""
        tid = store.create_movie_track(100, 458, "Unchecked", 2024, "theatrical", 1700000000, "q")
        due = store.get_movies_due_release_check(now_ts(), 3600)
        tids = [t["track_id"] for t in due]
        assert tid in tids

    def test_get_movies_due_release_check_respects_interval(self, store: Store) -> None:
        """Recently checked tracks should NOT be returned."""
        tid = store.create_movie_track(100, 459, "Recent", 2024, "theatrical", 1700000000, "q")
        store.update_movie_release_dates(tid, None, None, None, None, False, "in_theaters")
        due = store.get_movies_due_release_check(now_ts(), 3600)
        tids = [t["track_id"] for t in due]
        assert tid not in tids  # Just checked, within interval

    def test_get_movies_due_excludes_home_available(self, store: Store) -> None:
        """Tracks with home_available status should NOT be returned."""
        tid = store.create_movie_track(100, 460, "Available", 2024, "theatrical", 1700000000, "q")
        store.update_movie_release_dates(tid, 1700000000, 1700000000, None, 1700000000, False, "home_available")
        # interval=0 means cutoff == now, so only last_release_check_ts strictly < now passes —
        # but home_available is excluded by the WHERE clause regardless of timing.
        due = store.get_movies_due_release_check(now_ts() + 7200, 0)
        tids = [t["track_id"] for t in due]
        assert tid not in tids


# ---------------------------------------------------------------------------
# Callback flow tests — TestMovieScheduleCallbacks
# ---------------------------------------------------------------------------

# Reuse FakeBotApp pattern from test_callbacks.py — minimal stand-in that
# records render calls and exposes the flow dict.


class FakeBotApp:
    """Minimal BotApp stand-in for testing msch:* callback handlers."""

    def __init__(self, ctx: HandlerContext) -> None:
        self._ctx = ctx
        self.store = ctx.store
        self.cfg = ctx.cfg
        self.qbt = ctx.qbt
        self.plex = ctx.plex
        self.flow: dict[int, dict[str, Any]] = {}
        self.render_calls: list[tuple[str, tuple, dict]] = []
        # Wire render/navigate helpers onto ctx so handlers can call them.
        ctx.render_command_center = self._render_command_center
        ctx.navigate_to_command_center = self._navigate_to_command_center

    # -- Flow management --

    def _set_flow(self, user_id: int, flow: dict[str, Any]) -> None:
        self.flow[user_id] = flow

    def _get_flow(self, user_id: int) -> dict[str, Any] | None:
        return self.flow.get(user_id)

    def _clear_flow(self, user_id: int) -> None:
        self.flow.pop(user_id, None)

    def _cancel_pending_trackers_for_user(self, user_id: int) -> None:
        pass

    # -- Render stubs (record every call) --

    async def _render_schedule_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("schedule_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = 12345
        m.message_id = 1
        return m

    async def _render_nav_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("nav_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = 12345
        m.message_id = 1
        return m

    async def _render_command_center(self, *args: Any, **kwargs: Any) -> None:
        self.render_calls.append(("command_center", args, kwargs))

    async def _navigate_to_command_center(self, msg: Any, user_id: int, **kwargs: Any) -> None:
        self.render_calls.append(("command_center", (msg,), {"user_id": user_id, **kwargs}))

    async def _cleanup_private_user_message(self, msg: Any) -> None:
        pass

    # -- Keyboard/footer helpers --

    def _nav_footer(self, **kwargs: Any) -> list[list[Any]]:
        return [[]]

    def _home_only_keyboard(self) -> MagicMock:
        return MagicMock()


@pytest.fixture
def fake_app(mock_ctx: HandlerContext) -> FakeBotApp:
    return FakeBotApp(mock_ctx)


@pytest.fixture
def query() -> MagicMock:
    """Mock Telegram CallbackQuery."""
    q = MagicMock()
    q.data = "msch:add"
    q.answer = AsyncMock()
    reply_msg = MagicMock()
    reply_msg.chat_id = 12345
    reply_msg.message_id = 999
    q.message = MagicMock()
    q.message.edit_text = AsyncMock()
    q.message.reply_text = AsyncMock(return_value=reply_msg)
    q.message.delete = AsyncMock()
    q.message.chat_id = 12345
    q.message.message_id = 100
    q.message.get_bot = MagicMock(return_value=MagicMock())
    return q


@pytest.fixture
def msg() -> MagicMock:
    """Mock Telegram Message for on_text_movie_schedule."""
    m = MagicMock()
    m.from_user = MagicMock()
    m.from_user.id = 12345
    reply_msg = MagicMock()
    reply_msg.chat_id = 12345
    reply_msg.message_id = 999
    m.reply_text = AsyncMock(return_value=reply_msg)
    m.edit_text = AsyncMock()
    m.delete = AsyncMock()
    m.chat_id = 12345
    m.message_id = 100
    return m


USER_ID = 12345


class TestMovieScheduleCallbacks:
    @pytest.mark.asyncio
    async def test_msch_add_prompts_for_title(self, fake_app: FakeBotApp, query: MagicMock) -> None:
        """msch:add sets flow to msch_add/title and renders schedule UI."""
        await on_cb_movie_schedule(fake_app, data="msch:add", q=query, user_id=USER_ID)

        flow = fake_app._get_flow(USER_ID)
        assert flow is not None
        assert flow["mode"] == "msch_add"
        assert flow["stage"] == "title"
        assert any(name == "schedule_ui" for name, _, _ in fake_app.render_calls)
        # The rendered text should ask the user to enter a movie name
        rendered_texts = [
            args[3] for name, args, kwargs in fake_app.render_calls if name == "schedule_ui" and len(args) > 3
        ]
        assert any("Enter the name of the movie" in t for t in rendered_texts)

    @pytest.mark.asyncio
    async def test_msch_pick_stores_selection(
        self,
        fake_app: FakeBotApp,
        query: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """msch:pick:<tmdb_id> stores release state and advances straight to confirm_date."""
        # Seed flow with candidates
        fake_app._set_flow(
            USER_ID,
            {
                "mode": "msch_add",
                "stage": "title",
                "candidates": [
                    {"tmdb_id": 42, "title": "Inception", "year": 2010},
                ],
            },
        )

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr("patchy_bot.handlers.schedule.asyncio.to_thread", passthrough)
        fake_app._ctx.tvmeta.get_movie_release_status.return_value = MovieReleaseDates(
            tmdb_id=42,
            theatrical_ts=1_690_000_000,
            digital_ts=1_700_000_000,
            home_release_ts=1_700_000_000,
            home_date_is_inferred=False,
            status=MovieReleaseStatus.WAITING_HOME,
        )

        await on_cb_movie_schedule(fake_app, data="msch:pick:42", q=query, user_id=USER_ID)

        flow = fake_app._get_flow(USER_ID)
        assert flow is not None
        assert flow["tmdb_id"] == 42
        assert flow["title"] == "Inception"
        assert flow["year"] == 2010
        assert flow["stage"] == "confirm_date"
        assert flow["release_date_type"] == "home_release"
        assert flow["home_date_is_inferred"] is False
        assert any(name == "schedule_ui" for name, _, _ in fake_app.render_calls)

    @pytest.mark.asyncio
    async def test_msch_confirm_creates_track(
        self,
        fake_app: FakeBotApp,
        query: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """msch:confirm creates a movie_track row in the store and clears flow."""
        fake_app._set_flow(
            USER_ID,
            {
                "mode": "msch_add",
                "stage": "confirm_date",
                "tmdb_id": 99,
                "title": "Dune Part Two",
                "year": 2024,
                "release_status": "waiting_home",
                "release_date_type": "home_release",
                "release_date_ts": 1_710_000_000,
                "home_release_ts": 1_710_000_000,
                "home_date_is_inferred": True,
                "theatrical_ts": 1_700_000_000,
                "digital_ts": None,
                "physical_ts": None,
            },
        )

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr("patchy_bot.handlers.schedule.asyncio.to_thread", passthrough)

        await on_cb_movie_schedule(fake_app, data="msch:confirm:99", q=query, user_id=USER_ID)

        # Flow should be cleared after confirm
        assert fake_app._get_flow(USER_ID) is None
        # Store should now have the track
        tracks = fake_app.store.get_movie_tracks_for_user(USER_ID)
        assert len(tracks) == 1
        assert tracks[0]["tmdb_id"] == 99
        assert tracks[0]["title"] == "Dune Part Two"
        assert tracks[0]["release_date_type"] == "home_release"
        assert tracks[0]["home_date_is_inferred"] == 1
        # nav_ui rendered with confirmation message
        assert any(name == "nav_ui" for name, _, _ in fake_app.render_calls)

    @pytest.mark.asyncio
    async def test_msch_confirm_duplicate_rejected(
        self,
        fake_app: FakeBotApp,
        query: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """msch:confirm shows 'already tracked' and clears flow when the movie is a duplicate."""
        # Pre-create the track so it already exists
        fake_app.store.create_movie_track(
            USER_ID, 77, "Already Tracked", 2023, "theatrical", 1_700_000_000, "Already Tracked 2023"
        )
        fake_app._set_flow(
            USER_ID,
            {
                "mode": "msch_add",
                "stage": "confirm_date",
                "tmdb_id": 77,
                "title": "Already Tracked",
                "year": 2023,
                "release_status": "waiting_home",
                "release_date_type": "home_release",
                "release_date_ts": 1_700_000_000,
                "home_release_ts": 1_700_000_000,
                "home_date_is_inferred": True,
            },
        )

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr("patchy_bot.handlers.schedule.asyncio.to_thread", passthrough)
        await on_cb_movie_schedule(fake_app, data="msch:confirm:77", q=query, user_id=USER_ID)

        # Flow should be cleared
        assert fake_app._get_flow(USER_ID) is None
        # nav_ui rendered with "already being tracked" message
        assert any(name == "nav_ui" for name, _, _ in fake_app.render_calls)
        nav_texts = [args[2] for name, args, kwargs in fake_app.render_calls if name == "nav_ui" and len(args) > 2]
        assert any("already being tracked" in t for t in nav_texts)

    @pytest.mark.asyncio
    async def test_html_escape_in_movie_title(
        self,
        fake_app: FakeBotApp,
        query: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Titles containing < and > must be HTML-escaped in rendered messages."""
        fake_app._set_flow(
            USER_ID,
            {
                "mode": "msch_add",
                "stage": "confirm_date",
                "tmdb_id": 55,
                "title": "Movie <Special> & Co",
                "year": 2025,
                "release_status": "waiting_home",
                "release_date_type": "home_release",
                "release_date_ts": 1_800_000_000,
                "home_release_ts": 1_800_000_000,
                "home_date_is_inferred": False,
            },
        )

        async def passthrough(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        monkeypatch.setattr("patchy_bot.handlers.schedule.asyncio.to_thread", passthrough)

        await on_cb_movie_schedule(fake_app, data="msch:confirm:55", q=query, user_id=USER_ID)

        # Collect all text args sent to nav_ui
        nav_texts = [args[2] for name, args, kwargs in fake_app.render_calls if name == "nav_ui" and len(args) > 2]
        combined = " ".join(nav_texts)
        # Raw < and > must NOT appear; escaped forms must be present
        assert "<Special>" not in combined
        assert "&lt;Special&gt;" in combined


def _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex):
    mock_config.tmdb_api_key = "test-tmdb-key"
    mock_config.tmdb_region = "US"
    with (
        patch("patchy_bot.bot.QBClient", return_value=mock_qbt),
        patch("patchy_bot.bot.Store", return_value=mock_store),
        patch("patchy_bot.bot.PlexInventoryClient", return_value=mock_plex),
        patch("patchy_bot.bot.PatchyLLMClient", return_value=MagicMock()),
        patch("patchy_bot.bot.TVMetadataClient", return_value=mock_tvmeta),
    ):
        from patchy_bot.bot import BotApp

        app = BotApp(mock_config)
    app.store = mock_store
    app.qbt = mock_qbt
    app.tvmeta = mock_tvmeta
    app.plex = mock_plex
    return app


@pytest.mark.asyncio
async def test_inferred_date_replaced_by_confirmed(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex)
    tid = mock_store.create_movie_track(12345, 321, "Future Film", 2026, "home_release", now_ts(), "Future Film 2026")
    mock_store.update_movie_release_dates(tid, 1_700_000_000, 1_704_000_000, None, 1_704_000_000, True, "waiting_home", True)
    mock_store._conn.execute("UPDATE movie_tracks SET last_release_check_ts = 0 WHERE track_id = ?", (tid,))  # type: ignore[attr-defined]
    mock_store._conn.commit()  # type: ignore[attr-defined]
    track = mock_store.get_movie_track(tid)
    assert track is not None
    mock_tvmeta.get_movie_home_release.return_value = MovieReleaseDates(
        tmdb_id=321,
        theatrical_ts=1_700_000_000,
        digital_ts=now_ts() - 60,
        home_release_ts=now_ts() - 60,
        home_date_is_inferred=False,
        status=MovieReleaseStatus.HOME_AVAILABLE,
    )

    should_search = await bot._check_movie_release_gate(track)

    assert should_search is True
    refreshed = mock_store.get_movie_track(tid)
    assert refreshed is not None
    assert refreshed["home_date_is_inferred"] == 0
    assert refreshed["release_status"] == "home_available"


@pytest.mark.asyncio
async def test_inferred_date_unchanged_when_none_available(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex)
    tid = mock_store.create_movie_track(12345, 654, "Waiting Film", 2026, "home_release", now_ts(), "Waiting Film 2026")
    mock_store.update_movie_release_dates(tid, 1_700_000_000, 1_704_000_000, None, 1_704_000_000, True, "waiting_home", True)
    mock_store._conn.execute("UPDATE movie_tracks SET last_release_check_ts = 0 WHERE track_id = ?", (tid,))  # type: ignore[attr-defined]
    mock_store._conn.commit()  # type: ignore[attr-defined]
    track = mock_store.get_movie_track(tid)
    assert track is not None
    mock_tvmeta.get_movie_home_release.return_value = MovieReleaseDates(
        tmdb_id=654,
        theatrical_ts=1_700_000_000,
        digital_ts=1_704_000_000,
        home_release_ts=1_704_000_000,
        home_date_is_inferred=True,
        status=MovieReleaseStatus.WAITING_HOME,
    )

    should_search = await bot._check_movie_release_gate(track)

    assert should_search is False
    refreshed = mock_store.get_movie_track(tid)
    assert refreshed is not None
    assert refreshed["home_date_is_inferred"] == 1
    assert refreshed["home_release_ts"] == 1_704_000_000


@pytest.mark.asyncio
async def test_auto_remove_when_in_plex(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex):
    bot = _make_bot(mock_config, mock_store, mock_qbt, mock_tvmeta, mock_plex)
    tid = mock_store.create_movie_track(12345, 777, "Already In Plex", 2024, "home_release", now_ts(), "Already In Plex 2024")
    mock_store.update_movie_release_dates(tid, 1_700_000_000, None, None, 1_704_000_000, True, "waiting_home", True)
    track = mock_store.get_movie_track(tid)
    assert track is not None
    mock_plex.ready.return_value = True
    mock_plex.movie_exists.return_value = True

    removed = await bot._remove_movie_track_if_in_plex(track)

    assert removed is True
    assert mock_store.get_movie_track(tid) is None
