from __future__ import annotations

from patchy_bot.handlers.search import apply_filters
from patchy_bot.malware import DetectionSignal, ScanResult
from patchy_bot.ui.text import format_risk_badge


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


# ---------------------------------------------------------------------------
# Session 3: 3-tier apply_filters + format_risk_badge
# ---------------------------------------------------------------------------


class TestApplyFiltersTiers:
    def test_blocked_result_dropped(self) -> None:
        rows = [
            {
                "name": "Movie.codec.required.install.to.watch.requires.registration.1080p",
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

    def test_caution_result_kept_with_marker(self) -> None:
        rows = [
            {
                "name": "Movie.2026.codec.required.1080p.WEB-DL.x264",
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
        assert len(out) == 1
        scan = out[0].get("_malware_scan")
        assert scan is not None
        assert scan.tier == "caution"

    def test_clean_result_kept_without_marker(self) -> None:
        rows = [
            {
                "name": "Movie.2026.1080p.WEB-DL.x264",
                "size": 2_000_000_000,
                "seeders": 50,
                "hash": "c" * 40,
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
        assert out[0].get("_malware_scan") is None

    def test_malware_scan_marker_has_score(self) -> None:
        rows = [
            {
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
        scan = out[0]["_malware_scan"]
        assert hasattr(scan, "score")
        assert hasattr(scan, "tier")
        assert hasattr(scan, "signals")


class TestFormatRiskBadge:
    @staticmethod
    def _make_scan(tier: str, score: int, detail: str = "test signal") -> ScanResult:
        return ScanResult(
            score=score,
            tier=tier,
            signals=(DetectionSignal(signal_id="test.sig", points=score, detail=detail),),
            is_blocked=(tier == "blocked"),
        )

    def test_clean_returns_empty(self) -> None:
        scan = self._make_scan("clean", 10)
        assert format_risk_badge(scan) == ""

    def test_none_returns_empty(self) -> None:
        assert format_risk_badge(None) == ""

    def test_caution_returns_warning(self) -> None:
        scan = self._make_scan("caution", 35)
        badge = format_risk_badge(scan)
        assert badge.startswith("⚠️")

    def test_blocked_returns_blocked(self) -> None:
        scan = self._make_scan("blocked", 80)
        badge = format_risk_badge(scan)
        assert badge.startswith("🚫")

    def test_includes_score(self) -> None:
        scan = self._make_scan("caution", 42)
        badge = format_risk_badge(scan)
        assert "42/100" in badge

    def test_includes_top_signal(self) -> None:
        scan = self._make_scan("caution", 35, detail="dangerous thing")
        badge = format_risk_badge(scan)
        assert "dangerous thing" in badge

    def test_html_escaped(self) -> None:
        """HTML-dangerous characters in the signal detail must be escaped."""
        scan = self._make_scan("caution", 35, detail="<script>alert(1)</script>")
        badge = format_risk_badge(scan)
        assert "<script>" not in badge
        assert "&lt;script&gt;" in badge
