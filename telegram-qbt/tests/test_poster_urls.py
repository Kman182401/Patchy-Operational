"""Tests for poster/image URL extraction in TVMetadataClient."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from patchy_bot.clients.tv_metadata import TVMetadataClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tvmeta() -> TVMetadataClient:
    """Return a TVMetadataClient with a dummy API key."""
    return TVMetadataClient(tmdb_api_key="test-key")


# ---------------------------------------------------------------------------
# _show_card image_url extraction
# ---------------------------------------------------------------------------


class TestShowCardImageUrl:
    def _make_show(self, image: object = "MISSING") -> dict:
        """Build a minimal TVMaze show dict."""
        base: dict = {
            "id": 1,
            "name": "Test Show",
            "premiered": "2020-01-01",
            "status": "Running",
            "externals": {},
        }
        if image != "MISSING":
            base["image"] = image
        return base

    def test_show_card_extracts_image_url(self) -> None:
        """_show_card extracts image.medium URL when present."""
        show = self._make_show(
            image={
                "medium": "https://static.tvmaze.com/uploads/images/medium_portrait/1/1.jpg",
                "original": "https://static.tvmaze.com/uploads/images/original_untouched/1/1.jpg",
            }
        )
        result = TVMetadataClient._show_card(show)
        assert result["image_url"] == "https://static.tvmaze.com/uploads/images/medium_portrait/1/1.jpg"

    def test_show_card_image_url_none_when_image_null(self) -> None:
        """_show_card returns image_url=None when image field is null."""
        show = self._make_show(image=None)
        result = TVMetadataClient._show_card(show)
        assert result["image_url"] is None

    def test_show_card_image_url_none_when_image_missing(self) -> None:
        """_show_card returns image_url=None when image field is absent."""
        show = self._make_show()  # no "image" key
        result = TVMetadataClient._show_card(show)
        assert result["image_url"] is None

    def test_show_card_image_url_none_when_medium_missing(self) -> None:
        """_show_card returns image_url=None when image exists but medium is absent."""
        show = self._make_show(
            image={"original": "https://static.tvmaze.com/uploads/images/original_untouched/1/1.jpg"}
        )
        result = TVMetadataClient._show_card(show)
        assert result["image_url"] is None

    def test_show_card_image_url_none_when_medium_empty(self) -> None:
        """_show_card returns image_url=None when medium is an empty string."""
        show = self._make_show(image={"medium": ""})
        result = TVMetadataClient._show_card(show)
        assert result["image_url"] is None


# ---------------------------------------------------------------------------
# search_movies poster_url extraction
# ---------------------------------------------------------------------------


_TMDB_RESPONSE_WITH_POSTER = {
    "results": [
        {
            "id": 438631,
            "title": "Dune",
            "release_date": "2021-09-15",
            "overview": "A mythic and emotionally charged hero's journey.",
            "popularity": 85.3,
            "poster_path": "/d5NXSklXo0qyIYkgV94XAgMIckC.jpg",
        }
    ]
}

_TMDB_RESPONSE_NO_POSTER = {
    "results": [
        {
            "id": 99999,
            "title": "Obscure Film",
            "release_date": "2010-01-01",
            "overview": "A very obscure film.",
            "popularity": 0.1,
            "poster_path": None,
        }
    ]
}

_TMDB_RESPONSE_EMPTY_POSTER = {
    "results": [
        {
            "id": 11111,
            "title": "Another Film",
            "release_date": "2015-06-15",
            "overview": "Another film.",
            "popularity": 1.2,
            "poster_path": "",
        }
    ]
}


class TestSearchMoviesPosterUrl:
    def test_search_movies_extracts_poster_url(self, tvmeta: TVMetadataClient) -> None:
        """search_movies builds full poster URL from poster_path."""
        with patch.object(tvmeta, "_get_json", return_value=_TMDB_RESPONSE_WITH_POSTER):
            results = tvmeta.search_movies("Dune")
        assert results
        assert results[0]["poster_url"] == "https://image.tmdb.org/t/p/w185/d5NXSklXo0qyIYkgV94XAgMIckC.jpg"

    def test_search_movies_poster_url_none_when_poster_path_null(self, tvmeta: TVMetadataClient) -> None:
        """search_movies returns poster_url=None when poster_path is null."""
        with patch.object(tvmeta, "_get_json", return_value=_TMDB_RESPONSE_NO_POSTER):
            results = tvmeta.search_movies("Obscure Film")
        assert results
        assert results[0]["poster_url"] is None

    def test_search_movies_poster_url_none_when_poster_path_empty(self, tvmeta: TVMetadataClient) -> None:
        """search_movies returns poster_url=None when poster_path is empty string."""
        with patch.object(tvmeta, "_get_json", return_value=_TMDB_RESPONSE_EMPTY_POSTER):
            results = tvmeta.search_movies("Another Film")
        assert results
        assert results[0]["poster_url"] is None

    def test_search_movies_no_api_key_returns_empty(self) -> None:
        """search_movies returns empty list when tmdb_api_key is not configured."""
        client = TVMetadataClient(tmdb_api_key=None)
        results = client.search_movies("Dune")
        assert results == []


# ---------------------------------------------------------------------------
# _POSTER_ALLOWED_HOSTS allowlist (BotApp class attribute)
# ---------------------------------------------------------------------------


class TestPosterAllowedHosts:
    """Verify the hostname allowlist that guards _send_poster_photo."""

    def _get_allowlist(self) -> frozenset[str]:
        """Import and return BotApp._POSTER_ALLOWED_HOSTS without instantiating BotApp."""
        from patchy_bot.bot import BotApp

        return BotApp._POSTER_ALLOWED_HOSTS

    def test_tvmaze_hostname_is_allowed(self) -> None:
        """TVMaze CDN hostname is in the allowlist."""
        allowlist = self._get_allowlist()
        assert "static.tvmaze.com" in allowlist

    def test_tmdb_hostname_is_allowed(self) -> None:
        """TMDB image CDN hostname is in the allowlist."""
        allowlist = self._get_allowlist()
        assert "image.tmdb.org" in allowlist

    def test_arbitrary_hostname_not_allowed(self) -> None:
        """An arbitrary external hostname is not in the allowlist."""
        allowlist = self._get_allowlist()
        assert "evil.example.com" not in allowlist

    def test_internal_ip_not_allowed(self) -> None:
        """A private IP address hostname is not in the allowlist."""
        allowlist = self._get_allowlist()
        assert "192.168.1.1" not in allowlist
