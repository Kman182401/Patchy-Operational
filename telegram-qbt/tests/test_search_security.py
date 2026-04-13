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


def test_apply_filters_keeps_suspicious_uploader_clean() -> None:
    """v2: uploader-only signal is +10 → clean tier, row passes through unchanged."""
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

    # +10 for uploader alone — clean tier — row is kept without warning marker.
    assert len(out) == 1
    assert out[0].get("_malware_scan") is None


def test_apply_filters_caution_attaches_marker() -> None:
    """A row with multiple signals (caution tier) is kept and flagged for UI."""
    rows = [
        {
            # codec required (hard kw +20) + suspicious uploader (+10) = 30 → caution
            "name": "Movie.2026.codec.required.1080p.WEB-DL.x264",
            "size": 2_000_000_000,
            "seeders": 50,
            "hash": "d" * 40,
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

    assert len(out) == 1
    scan = out[0].get("_malware_scan")
    assert scan is not None, "caution-tier rows must carry _malware_scan"
    assert scan.tier == "caution"


def test_apply_filters_blocks_high_score() -> None:
    """A row with multiple hard signals (blocked tier) is dropped from results."""
    rows = [
        {
            # 3x hard keywords → blocked
            "name": "Movie.codec.required.install.to.watch.requires.registration.1080p",
            "size": 2_000_000_000,
            "seeders": 50,
            "hash": "e" * 40,
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
