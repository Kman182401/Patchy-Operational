from __future__ import annotations

from patchy_bot.handlers.search import apply_filters


def test_apply_filters_blocks_theatrical_sources() -> None:
    rows = [
        {
            "name": "Movie.2026.1080p.TELESYNC.x264",
            "size": 2_000_000_000,
            "seeders": 50,
            "hash": "a" * 40,
        }
    ]

    out = apply_filters(
        rows,
        min_seeds=0,
        min_size=None,
        max_size=None,
        min_quality=0,
        media_type="movie",
    )

    assert out == []


def test_apply_filters_blocks_suspicious_uploader() -> None:
    rows = [
        {
            "name": "Movie.2026.1080p.WEB-DL.x264",
            "size": 2_000_000_000,
            "seeders": 50,
            "hash": "b" * 40,
            "uploader": "anonymous",
        }
    ]

    out = apply_filters(
        rows,
        min_seeds=0,
        min_size=None,
        max_size=None,
        min_quality=0,
        media_type="movie",
    )

    assert out == []


def test_save_search_persists_uploader(mock_store) -> None:
    rows = [
        {
            "name": "Movie.2026.1080p.WEB-DL.x264",
            "size": 2_000_000_000,
            "seeders": 50,
            "hash": "c" * 40,
            "uploader": "TorrentGalaxy",
        }
    ]

    search_id = mock_store.save_search(12345, "Movie 2026", {"sort": "quality"}, rows)
    payload = mock_store.get_search(12345, search_id)
    assert payload is not None
    _, stored_rows = payload
    assert stored_rows[0]["uploader"] == "TorrentGalaxy"
