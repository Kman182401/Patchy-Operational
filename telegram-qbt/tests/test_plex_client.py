"""Tests for patchy_bot.clients.plex.PlexInventoryClient."""

from __future__ import annotations

import pytest

from patchy_bot.clients.plex import PlexInventoryClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, text: str = "<MediaContainer />", status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


def _make_client(
    monkeypatch,
    responses: list[FakeResponse] | None = None,
    *,
    base_url: str = "http://plex:32400",
    token: str = "test-token",
    tv_root: str = "/mnt/tv",
) -> PlexInventoryClient:
    """Return a PlexInventoryClient whose HTTP layer is fully faked."""
    client = PlexInventoryClient(base_url, token, tv_root)
    if responses is None:
        responses = []
    call_log: list[tuple] = []
    idx = [0]

    def fake_request(*args, **kwargs):
        call_log.append((args, kwargs))
        i = idx[0]
        idx[0] += 1
        if i < len(responses):
            resp = responses[i]
        else:
            resp = FakeResponse()
        if resp.status_code >= 400:
            raise RuntimeError(f"Plex API error {resp.status_code}: {resp.text[:240]}")
        return resp

    monkeypatch.setattr(client.session, "request", fake_request)
    # Expose call log for assertions that need it
    client._test_call_log = call_log  # type: ignore[attr-defined]
    return client


# ---- XML snippets --------------------------------------------------------

SECTIONS_XML = """\
<MediaContainer>
  <Directory type="show" key="2" title="TV Shows">
    <Location path="/mnt/tv" />
  </Directory>
  <Directory type="movie" key="1" title="Movies">
    <Location path="/mnt/movies" />
  </Directory>
</MediaContainer>
"""

SECTIONS_MOVIE_ONLY_XML = """\
<MediaContainer>
  <Directory type="movie" key="1" title="Movies">
    <Location path="/mnt/movies" />
  </Directory>
</MediaContainer>
"""

SECTIONS_NO_PATH_MATCH_XML = """\
<MediaContainer>
  <Directory type="show" key="5" title="Anime">
    <Location path="/mnt/anime" />
  </Directory>
  <Directory type="show" key="6" title="Kids">
    <Location path="/mnt/kids" />
  </Directory>
</MediaContainer>
"""

SHOW_SEARCH_XML = """\
<MediaContainer>
  <Directory ratingKey="100" type="show" title="Test Show" year="2024" />
</MediaContainer>
"""

SHOW_SEARCH_TWO_XML = """\
<MediaContainer>
  <Directory ratingKey="100" type="show" title="Test Show" year="2020" />
  <Directory ratingKey="101" type="show" title="Test Show" year="2024" />
</MediaContainer>
"""

ALL_LEAVES_XML = """\
<MediaContainer>
  <Video ratingKey="200" parentIndex="1" index="1" />
  <Video ratingKey="201" parentIndex="1" index="2" />
  <Video ratingKey="202" parentIndex="2" index="1" />
</MediaContainer>
"""

EMPTY_CONTAINER_XML = "<MediaContainer />"


# ===========================================================================
# ready()
# ===========================================================================


class TestReady:
    def test_plex_ready_true(self) -> None:
        client = PlexInventoryClient("http://plex:32400", "tok", "/mnt/tv")
        assert client.ready() is True

    def test_plex_ready_false_no_url(self) -> None:
        client = PlexInventoryClient("", "tok", "/mnt/tv")
        assert client.ready() is False

    def test_plex_ready_false_no_token(self) -> None:
        client = PlexInventoryClient("http://plex:32400", "", "/mnt/tv")
        assert client.ready() is False


# ===========================================================================
# _norm_media_path()
# ===========================================================================


class TestNormMediaPath:
    def test_norm_media_path_strips_and_normalizes(self) -> None:
        assert PlexInventoryClient._norm_media_path("  /mnt/tv//Show/  ") == "/mnt/tv/Show"

    def test_norm_media_path_empty(self) -> None:
        assert PlexInventoryClient._norm_media_path("") == "."


# ===========================================================================
# _path_matches_remove_target()
# ===========================================================================


class TestPathMatchesRemoveTarget:
    def test_path_matches_episode_exact_match(self) -> None:
        assert (
            PlexInventoryClient._path_matches_remove_target(
                "/mnt/tv/Show/S01E01.mkv", "/mnt/tv/Show/S01E01.mkv", "episode"
            )
            is True
        )

    def test_path_matches_episode_no_prefix(self) -> None:
        # For episode kind, a sub-path should NOT match
        assert (
            PlexInventoryClient._path_matches_remove_target("/mnt/tv/Show/S01E01.mkv", "/mnt/tv/Show", "episode")
            is False
        )

    def test_path_matches_directory_prefix(self) -> None:
        assert (
            PlexInventoryClient._path_matches_remove_target(
                "/mnt/tv/Show/Season 1/ep.mkv", "/mnt/tv/Show/Season 1", "season"
            )
            is True
        )

    def test_path_matches_directory_exact(self) -> None:
        assert (
            PlexInventoryClient._path_matches_remove_target("/mnt/tv/Show/Season 1", "/mnt/tv/Show/Season 1", "season")
            is True
        )

    def test_path_matches_empty_returns_false(self) -> None:
        assert PlexInventoryClient._path_matches_remove_target("", "/mnt/tv/Show", "episode") is False


# ===========================================================================
# _tv_section()
# ===========================================================================


class TestTvSection:
    def test_tv_section_matches_by_path(self, monkeypatch) -> None:
        client = _make_client(monkeypatch, [FakeResponse(SECTIONS_XML)])
        assert client._tv_section() == "2"

    def test_tv_section_falls_back_to_first_show(self, monkeypatch) -> None:
        client = _make_client(monkeypatch, [FakeResponse(SECTIONS_NO_PATH_MATCH_XML)])
        # No location matches /mnt/tv, so falls back to first show section
        assert client._tv_section() == "5"

    def test_tv_section_returns_none_no_show_sections(self, monkeypatch) -> None:
        client = _make_client(monkeypatch, [FakeResponse(SECTIONS_MOVIE_ONLY_XML)])
        assert client._tv_section() is None

    def test_tv_section_caches_result(self, monkeypatch) -> None:
        client = _make_client(monkeypatch, [FakeResponse(SECTIONS_XML)])
        first = client._tv_section()
        second = client._tv_section()
        assert first == second == "2"
        # Only one HTTP call should have been made
        assert len(client._test_call_log) == 1  # type: ignore[attr-defined]


# ===========================================================================
# episode_inventory()
# ===========================================================================


class TestEpisodeInventory:
    def test_episode_inventory_returns_codes(self, monkeypatch) -> None:
        client = _make_client(
            monkeypatch,
            [
                FakeResponse(SECTIONS_XML),  # _tv_section
                FakeResponse(SHOW_SEARCH_XML),  # search
                FakeResponse(ALL_LEAVES_XML),  # allLeaves
            ],
        )
        codes, source = client.episode_inventory("Test Show")
        assert source == "plex"
        assert codes == {"S01E01", "S01E02", "S02E01"}

    def test_episode_inventory_show_not_found(self, monkeypatch) -> None:
        client = _make_client(
            monkeypatch,
            [
                FakeResponse(SECTIONS_XML),  # _tv_section
                FakeResponse(EMPTY_CONTAINER_XML),  # search returns nothing
            ],
        )
        codes, source = client.episode_inventory("Nonexistent Show")
        assert codes == set()
        assert "not found" in source

    def test_episode_inventory_year_boosts_selection(self, monkeypatch) -> None:
        # Two shows with same title, different years. Passing year=2024
        # should pick ratingKey 101 (year 2024) over 100 (year 2020).
        client = _make_client(
            monkeypatch,
            [
                FakeResponse(SECTIONS_XML),  # _tv_section
                FakeResponse(SHOW_SEARCH_TWO_XML),  # search returns two
                FakeResponse(ALL_LEAVES_XML),  # allLeaves for selected show
            ],
        )
        codes, source = client.episode_inventory("Test Show", year=2024)
        assert source == "plex"
        # Verify we got episodes (the selection logic picked the right show)
        assert len(codes) == 3
        # Check the HTTP call used ratingKey 101 (year-matched show)
        call_args = client._test_call_log[2]  # type: ignore[attr-defined]
        url = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("url", "")
        assert "101" in url

    def test_episode_inventory_no_tv_section_raises(self, monkeypatch) -> None:
        client = _make_client(monkeypatch, [FakeResponse(SECTIONS_MOVIE_ONLY_XML)])
        with pytest.raises(RuntimeError, match="No Plex TV library section"):
            client.episode_inventory("Any Show")


# ===========================================================================
# verify_remove_identity_absent()
# ===========================================================================


class TestVerifyRemoveIdentityAbsent:
    def test_verify_rating_keys_metadata_gone(self, monkeypatch) -> None:
        """When all rating_keys 404, the item is confirmed absent."""
        client = _make_client(
            monkeypatch,
            [
                # _metadata_exists for rk "50" will raise RuntimeError with 404
                FakeResponse("Not Found", status_code=404),
            ],
        )
        verification = {
            "verification_mode": "rating_keys",
            "rating_keys": ["50"],
            "title": "Test Movie",
        }
        absent, msg = client.verify_remove_identity_absent("/mnt/movies/test.mkv", "movie", verification)
        assert absent is True
        assert "removed" in msg

    def test_verify_rating_keys_metadata_exists(self, monkeypatch) -> None:
        """When metadata still returns 200, item is NOT absent."""
        client = _make_client(
            monkeypatch,
            [
                FakeResponse("<MediaContainer />", status_code=200),
            ],
        )
        verification = {
            "verification_mode": "rating_keys",
            "rating_keys": ["50"],
            "title": "Test Movie",
        }
        absent, msg = client.verify_remove_identity_absent("/mnt/movies/test.mkv", "movie", verification)
        assert absent is False
        assert "still has" in msg

    def test_verify_path_fallback_no_matching_parts(self, monkeypatch) -> None:
        """path_fallback mode with no section_key scans all sections -- none match."""
        sections_xml = SECTIONS_MOVIE_ONLY_XML
        # Movies section returns empty container (no media parts)
        empty_movies = "<MediaContainer />"
        client = _make_client(
            monkeypatch,
            [
                FakeResponse(sections_xml),  # _sections() call
                FakeResponse(empty_movies),  # movie section /all
            ],
        )
        verification = {
            "verification_mode": "path_fallback",
            "rating_keys": [],
            "title": "Gone Movie",
        }
        absent, msg = client.verify_remove_identity_absent("/mnt/movies/gone.mkv", "movie", verification)
        assert absent is True
        assert "removed" in msg


# ===========================================================================
# _request() error handling
# ===========================================================================


class TestRequestErrors:
    def test_request_raises_when_not_configured(self) -> None:
        client = PlexInventoryClient("", "", "/mnt/tv")
        with pytest.raises(RuntimeError, match="not configured"):
            client._request("GET", "/library/sections")

    def test_get_xml_raises_on_bad_xml(self, monkeypatch) -> None:
        client = _make_client(monkeypatch, [FakeResponse("<<<not xml>>>")])
        with pytest.raises(RuntimeError, match="invalid XML"):
            client._get_xml("/library/sections")
