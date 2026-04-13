"""Scoring-engine unit tests for the malware v2 detection engine.

Covers ``DetectionSignal``, ``ScanResult``, ``_build_result`` and
``_apply_co_occurrence`` in isolation from any specific signal check.
"""

from __future__ import annotations

import dataclasses

import pytest

from patchy_bot.malware import (
    DetectionSignal,
    ScanResult,
    _apply_co_occurrence,
    _build_result,
)


# ---------------------------------------------------------------------------
# DetectionSignal
# ---------------------------------------------------------------------------


class TestDetectionSignal:
    def test_construction(self) -> None:
        sig = DetectionSignal(signal_id="test.one", points=10, detail="hello")
        assert sig.signal_id == "test.one"
        assert sig.points == 10
        assert sig.detail == "hello"

    def test_frozen(self) -> None:
        sig = DetectionSignal(signal_id="t", points=1, detail="d")
        with pytest.raises(dataclasses.FrozenInstanceError):
            sig.points = 99  # type: ignore[misc]

    def test_slots_no_dict(self) -> None:
        sig = DetectionSignal(signal_id="t", points=1, detail="d")
        assert not hasattr(sig, "__dict__")


# ---------------------------------------------------------------------------
# ScanResult
# ---------------------------------------------------------------------------


def _sig(signal_id: str, points: int, detail: str = "") -> DetectionSignal:
    return DetectionSignal(signal_id=signal_id, points=points, detail=detail or signal_id)


class TestScanResult:
    def test_clean_tier(self) -> None:
        r = _build_result([_sig("a", 29)])
        assert r.tier == "clean"
        assert r.is_blocked is False
        assert r.score == 29

    def test_caution_tier_lower_bound(self) -> None:
        r = _build_result([_sig("a", 30)])
        assert r.tier == "caution"
        assert r.is_blocked is False

    def test_caution_tier_upper_bound(self) -> None:
        r = _build_result([_sig("a", 30), _sig("b", 29)])
        assert r.score == 59
        assert r.tier == "caution"

    def test_blocked_tier(self) -> None:
        r = _build_result([_sig("a", 60)])
        assert r.tier == "blocked"
        assert r.is_blocked is True

    def test_blocked_tier_high(self) -> None:
        r = _build_result([_sig("a", 100)])
        assert r.tier == "blocked"
        assert r.score == 100

    def test_score_cap_at_100(self) -> None:
        r = _build_result([_sig("a", 60), _sig("b", 60), _sig("c", 30)])
        # Raw sum 150 should be capped at 100.
        assert r.score == 100
        assert r.tier == "blocked"

    def test_empty_signals_clean(self) -> None:
        r = _build_result([])
        assert r.score == 0
        assert r.tier == "clean"
        assert not r.is_blocked
        assert r.signals == ()

    def test_backward_compat_is_blocked(self) -> None:
        assert _build_result([_sig("x", 70)]).is_blocked is True
        assert _build_result([_sig("x", 40)]).is_blocked is False
        assert _build_result([_sig("x", 5)]).is_blocked is False

    def test_backward_compat_reasons(self) -> None:
        r = _build_result([_sig("a", 20, "reason one"), _sig("b", 20, "reason two")])
        assert r.reasons == ["reason one", "reason two"]
        assert isinstance(r.reasons, list)

    def test_frozen_result(self) -> None:
        r = _build_result([_sig("a", 10)])
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.score = 99  # type: ignore[misc]

    def test_signals_are_tuple(self) -> None:
        r = _build_result([_sig("a", 10), _sig("b", 5)])
        assert isinstance(r.signals, tuple)
        assert len(r.signals) == 2

    def test_signals_preserve_order(self) -> None:
        r = _build_result([_sig("first", 10), _sig("second", 5), _sig("third", 1)])
        assert [s.signal_id for s in r.signals] == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# _build_result
# ---------------------------------------------------------------------------


class TestBuildResult:
    def test_single_signal(self) -> None:
        r = _build_result([_sig("only", 25)])
        assert r.score == 25
        assert r.tier == "clean"
        assert len(r.signals) == 1

    def test_multiple_signals_sum(self) -> None:
        r = _build_result([_sig("a", 10), _sig("b", 15), _sig("c", 5)])
        assert r.score == 30
        assert r.tier == "caution"

    def test_hard_block_signal(self) -> None:
        r = _build_result([_sig("ext.executable", 100)])
        assert r.is_blocked
        assert r.score == 100

    def test_boundary_29_clean(self) -> None:
        r = _build_result([_sig("a", 29)])
        assert r.tier == "clean"

    def test_boundary_30_caution(self) -> None:
        r = _build_result([_sig("a", 30)])
        assert r.tier == "caution"

    def test_boundary_59_caution(self) -> None:
        r = _build_result([_sig("a", 59)])
        assert r.tier == "caution"

    def test_boundary_60_blocked(self) -> None:
        r = _build_result([_sig("a", 60)])
        assert r.tier == "blocked"


# ---------------------------------------------------------------------------
# _apply_co_occurrence
# ---------------------------------------------------------------------------


class TestCoOccurrence:
    def test_soft_only_removed(self) -> None:
        """Soft keywords alone must not contribute to the final score."""
        signals = [_sig("kw_soft.crack", 15), _sig("kw_soft.patch", 15)]
        out = _apply_co_occurrence(signals)
        assert out == []

    def test_soft_plus_hard_kept(self) -> None:
        """A soft signal paired with a hard signal is retained."""
        signals = [_sig("kw.codec_required", 20, "hard"), _sig("kw_soft.crack", 15, "soft")]
        out = _apply_co_occurrence(signals)
        # Both are kept (one soft ≤ 20 cap so not collapsed).
        ids = [s.signal_id for s in out]
        assert "kw.codec_required" in ids
        assert "kw_soft.crack" in ids

    def test_three_soft_capped_at_20(self) -> None:
        """When total soft points exceeds 20, they collapse into one capped signal."""
        signals = [
            _sig("kw.hard", 20),
            _sig("kw_soft.crack", 15),
            _sig("kw_soft.keygen", 15),
            _sig("kw_soft.patch", 15),
        ]
        out = _apply_co_occurrence(signals)
        soft_out = [s for s in out if s.signal_id.startswith("kw_soft.")]
        assert len(soft_out) == 1
        assert soft_out[0].signal_id == "kw_soft.combined"
        assert soft_out[0].points == 20

    def test_no_soft_signals_unchanged(self) -> None:
        signals = [_sig("kw.codec", 20), _sig("size.below_min", 15)]
        out = _apply_co_occurrence(signals)
        assert out == signals

    def test_single_soft_plus_hard(self) -> None:
        signals = [_sig("kw.codec", 20), _sig("kw_soft.crack", 15)]
        out = _apply_co_occurrence(signals)
        assert len(out) == 2
        # Neither compressed (soft_total <= 20)
        points_sum = sum(s.points for s in out)
        assert points_sum == 35

    def test_three_soft_plus_hard_total_score(self) -> None:
        """The hard 20 + capped 20 soft = 40 total."""
        signals = [
            _sig("kw.hard", 20),
            _sig("kw_soft.a", 15),
            _sig("kw_soft.b", 15),
            _sig("kw_soft.c", 15),
        ]
        out = _apply_co_occurrence(signals)
        assert sum(s.points for s in out) == 40

    def test_empty_signals(self) -> None:
        assert _apply_co_occurrence([]) == []

    def test_hard_only_unchanged(self) -> None:
        signals = [_sig("kw.codec", 20), _sig("kw.serial", 20)]
        out = _apply_co_occurrence(signals)
        assert out == signals

    def test_soft_points_exactly_20_not_capped(self) -> None:
        """Soft total == 20 should NOT trigger the cap collapse."""
        # One soft signal at exactly 15 + a hard
        signals = [_sig("kw.hard", 20), _sig("kw_soft.one", 15)]
        out = _apply_co_occurrence(signals)
        # Original signals preserved (no "combined" replacement).
        ids = [s.signal_id for s in out]
        assert "kw_soft.combined" not in ids
        assert "kw_soft.one" in ids


class TestScanResultType:
    def test_scan_result_is_scan_result(self) -> None:
        r = _build_result([_sig("a", 10)])
        assert isinstance(r, ScanResult)
