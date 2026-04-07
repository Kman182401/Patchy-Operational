"""Tests for the movie schedule tracking feature."""

from __future__ import annotations

from datetime import UTC
from typing import Any
from unittest.mock import patch

import pytest

from patchy_bot.clients.tv_metadata import MovieReleaseStatus, TVMetadataClient
from patchy_bot.store import Store
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
        store.update_movie_release_dates(tid, 1700000000, 1703888000, None, 1703888000, True, "waiting_home")
        track = store.get_movie_track(tid)
        assert track["digital_estimated"] == 1

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
