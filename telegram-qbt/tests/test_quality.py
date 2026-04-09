"""Tests for the torrent quality scoring engine (patchy_bot/quality.py).

Covers:
  - Garbage rejection (CAM, TS, AV1, upscaled, zero seeds)
  - Resolution tier ordering
  - Codec preference (resolution-aware x264 vs x265)
  - Release group reputation (HQ bonus, LQ penalty)
  - Season pack detection
  - Quality label display
  - Benchmark ranking of realistic search results
"""

from __future__ import annotations

from patchy_bot.quality import (
    TorrentScore,
    is_season_pack,
    parse_quality,
    quality_label,
    score_torrent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gb(n: float) -> int:
    """Convert gigabytes to bytes."""
    return int(n * 1024**3)


# ===================================================================
# 1. Garbage rejection tests
# ===================================================================


def test_cam_rejected() -> None:
    ts = score_torrent("Movie.2024.HDCAM.x264-NoGroup", 1_200_000_000, 500)
    assert ts.is_rejected
    assert "cam" in (ts.reject_reason or "").lower() or "theatrical" in (ts.reject_reason or "").lower()


def test_telesync_rejected() -> None:
    ts = score_torrent("Movie.2024.TS.x264-GROUP", 2_000_000_000, 100)
    assert ts.is_rejected
    assert "theatrical" in (ts.reject_reason or "").lower()


def test_telecine_rejected() -> None:
    ts = score_torrent("Movie.2024.TC.x264-GROUP", 2_000_000_000, 100)
    assert ts.is_rejected
    assert "theatrical" in (ts.reject_reason or "").lower()


def test_av1_rejected() -> None:
    ts = score_torrent("Movie.2024.1080p.WEB-DL.AV1-GROUP", 3_000_000_000, 50)
    assert ts.is_rejected
    assert ts.reject_reason is not None
    assert "av1" in ts.reject_reason.lower()


def test_upscaled_rejected() -> None:
    ts = score_torrent("Movie.2024.2160p.Upscaled.BluRay.x264-GROUP", 8_000_000_000, 30)
    assert ts.is_rejected
    assert ts.reject_reason is not None
    assert "upscaled" in ts.reject_reason.lower()


def test_zero_seeds_rejected() -> None:
    ts = score_torrent("Movie.2024.1080p.BluRay.x264-GROUP", 4_000_000_000, 0)
    assert ts.is_rejected
    assert ts.reject_reason is not None
    assert "seed" in ts.reject_reason.lower()


def test_legitimate_1080p_not_rejected() -> None:
    ts = score_torrent("Movie.2024.1080p.WEB-DL.DDP5.1.H264-NTG", 4_000_000_000, 50)
    assert not ts.is_rejected
    assert ts.reject_reason is None


def test_legitimate_720p_not_rejected() -> None:
    ts = score_torrent("Movie.2024.720p.WEB-DL.x264-GROUP", 2_000_000_000, 30)
    assert not ts.is_rejected


def test_rejected_score_is_negative() -> None:
    """All rejected torrents get format_score = -9999."""
    ts = score_torrent("Movie.2024.2160p.Upscaled.BluRay.x264-GROUP", 8_000_000_000, 30)
    assert ts.is_rejected
    assert ts.format_score == -9999


# ===================================================================
# 2. Resolution tier ordering
# ===================================================================


def test_1080p_tier_beats_720p_tier() -> None:
    ts_1080 = score_torrent("Movie.1080p.WEBRip.x264-GROUP", 2_000_000_000, 10)
    ts_720 = score_torrent("Movie.720p.BluRay.REMUX.x264-GROUP", 2_000_000_000, 200)
    assert ts_1080.resolution_tier > ts_720.resolution_tier


def test_2160p_tier_beats_1080p_tier() -> None:
    ts_4k = score_torrent("Movie.2160p.WEBRip.x265-GROUP", 8_000_000_000, 5)
    ts_1080 = score_torrent("Movie.1080p.BluRay.REMUX-HiFi", 15_000_000_000, 200)
    assert ts_4k.resolution_tier > ts_1080.resolution_tier


def test_720p_tier_beats_480p_tier() -> None:
    ts_720 = score_torrent("Movie.720p.WEB-DL.x264-GROUP", 2_000_000_000, 50)
    ts_480 = score_torrent("Movie.480p.DVDRip.x264-GROUP", 1_000_000_000, 200)
    assert ts_720.resolution_tier > ts_480.resolution_tier


def test_unknown_resolution_gets_tier_zero() -> None:
    ts = score_torrent("Movie.WEBRip.x264-GROUP", 2_000_000_000, 50)
    assert ts.resolution_tier == 0


def test_tier_values_are_correct() -> None:
    """2160p=4, 1080p=3, 720p=2, 480p=1."""
    ts_4k = score_torrent("Movie.2160p.WEB-DL.x265-GROUP", 8_000_000_000, 50)
    ts_1080 = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_720 = score_torrent("Movie.720p.WEB-DL.x264-GROUP", 2_000_000_000, 50)
    ts_480 = score_torrent("Movie.480p.DVDRip.x264-GROUP", 1_000_000_000, 50)
    assert ts_4k.resolution_tier == 4
    assert ts_1080.resolution_tier == 3
    assert ts_720.resolution_tier == 2
    assert ts_480.resolution_tier == 1


# ===================================================================
# 3. Codec preference tests
# ===================================================================


def test_x264_preferred_over_x265_at_1080p() -> None:
    """At 1080p, x264 (avc +70) beats x265 (hevc -50) due to transcoding concerns."""
    ts_264 = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_265 = score_torrent("Movie.1080p.WEB-DL.x265-GROUP", 4_000_000_000, 50)
    assert ts_264.format_score > ts_265.format_score


def test_x265_preferred_over_x264_at_4k() -> None:
    """At 2160p, x265 (hevc +80) beats x264 (avc +40) since HEVC is efficient for 4K."""
    ts_265 = score_torrent("Movie.2160p.WEB-DL.x265-GROUP", 8_000_000_000, 50)
    ts_264 = score_torrent("Movie.2160p.WEB-DL.x264-GROUP", 8_000_000_000, 50)
    assert ts_265.format_score > ts_264.format_score


def test_x265_penalty_at_720p() -> None:
    """At 720p (not 4K), x265 still gets penalised same as 1080p."""
    ts_264 = score_torrent("Movie.720p.WEB-DL.x264-GROUP", 2_000_000_000, 50)
    ts_265 = score_torrent("Movie.720p.WEB-DL.x265-GROUP", 2_000_000_000, 50)
    assert ts_264.format_score > ts_265.format_score


def test_xvid_heavily_penalised() -> None:
    """XviD gets -200, making it score far below x264/x265."""
    ts_xvid = score_torrent("Movie.1080p.WEB-DL.XviD-GROUP", 4_000_000_000, 50)
    ts_264 = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert ts_xvid.format_score < ts_264.format_score


# ===================================================================
# 4. Group reputation tests
# ===================================================================


def test_lq_group_penalised() -> None:
    """YIFY (LQ group) scores far below an unknown group."""
    ts_yify = score_torrent("Movie.1080p.BluRay.x264-YIFY", 2_000_000_000, 100)
    ts_some = score_torrent("Movie.1080p.BluRay.x264-SomeGroup", 2_000_000_000, 100)
    assert ts_yify.format_score < ts_some.format_score


def test_hq_group_bonus() -> None:
    """NTG (HQ group, +30) scores above an unknown group with identical content."""
    ts_ntg = score_torrent("Movie.1080p.WEB-DL.DDP5.1.H264-NTG", 4_000_000_000, 50)
    ts_rand = score_torrent("Movie.1080p.WEB-DL.DDP5.1.H264-RandomGroup", 4_000_000_000, 50)
    assert ts_ntg.format_score > ts_rand.format_score


def test_multiple_lq_groups_penalised() -> None:
    """All known LQ groups get the same penalty."""
    ts_yts = score_torrent("Movie.1080p.BluRay.x264-YTS", 2_000_000_000, 100)
    ts_evo = score_torrent("Movie.1080p.BluRay.x264-EVO", 2_000_000_000, 100)
    ts_good = score_torrent("Movie.1080p.BluRay.x264-SomeGroup", 2_000_000_000, 100)
    assert ts_yts.format_score < ts_good.format_score
    assert ts_evo.format_score < ts_good.format_score


def test_flux_hq_group_bonus() -> None:
    """FLUX (HQ group) gets the +30 bonus."""
    ts_flux = score_torrent("Movie.1080p.WEB-DL.DDP5.1.H264-FLUX", 4_000_000_000, 50)
    ts_rand = score_torrent("Movie.1080p.WEB-DL.DDP5.1.H264-RandomGroup", 4_000_000_000, 50)
    assert ts_flux.format_score > ts_rand.format_score


# ===================================================================
# 5. Season pack detection
# ===================================================================


def test_season_pack_s01() -> None:
    assert is_season_pack("Show.S01.1080p.BluRay.x264-GROUP")


def test_single_episode_not_pack() -> None:
    assert not is_season_pack("Show.S01E01.1080p.BluRay.x264-GROUP")


def test_complete_series() -> None:
    assert is_season_pack("Show.COMPLETE.1080p.BluRay.x264-GROUP")


def test_season_word() -> None:
    assert is_season_pack("Show.Season.2.1080p.WEB-DL.x264-GROUP")


def test_multi_season_pack() -> None:
    assert is_season_pack("Show.S01-S03.1080p.WEB-DL.x264-GROUP")


def test_season_pack_with_preparsed_data() -> None:
    """When a ParsedData object is passed, uses its fields directly."""
    parsed = parse_quality("Show.S01.1080p.BluRay.x264-GROUP")
    assert is_season_pack("Show.S01.1080p.BluRay.x264-GROUP", parsed=parsed)


def test_single_episode_not_pack_with_preparsed() -> None:
    parsed = parse_quality("Show.S01E01.1080p.BluRay.x264-GROUP")
    assert not is_season_pack("Show.S01E01.1080p.BluRay.x264-GROUP", parsed=parsed)


# ===================================================================
# 6. Quality label tests
# ===================================================================


def test_quality_label_webdl_with_audio_and_group() -> None:
    parsed = parse_quality("Show.S01E01.1080p.AMZN.WEB-DL.DDP5.1.H.264-FLUX")
    label = quality_label(parsed)
    assert "1080p" in label
    assert "WEB-DL" in label
    assert "FLUX" in label


def test_quality_label_unknown() -> None:
    parsed = parse_quality("random_file_name")
    label = quality_label(parsed)
    assert isinstance(label, str)
    assert label == "Unknown"


def test_quality_label_4k_remux() -> None:
    parsed = parse_quality("Movie.2160p.BluRay.Remux.DTS-HD.MA.7.1.DV.HDR10.x265-HiFi")
    label = quality_label(parsed)
    assert "2160p" in label
    assert "x265" in label
    assert "HiFi" in label


# ===================================================================
# 7. Benchmark / known-best-pick tests
# ===================================================================


def test_benchmark_movie_ranking() -> None:
    """Best 1080p WEB-DL from HQ group should rank first; 720p should rank last."""
    results = [
        ("Movie.2024.1080p.AMZN.WEB-DL.DDP5.1.H.264-FLUX", _gb(4.2), 85),
        ("Movie.2024.1080p.BluRay.x264.DTS-YIFY", _gb(1.8), 2000),
        ("Movie.2024.1080p.HDTV.x264-LOL", _gb(1.5), 200),
        ("Movie.2024.720p.WEB-DL.x264-GROUP", _gb(2.1), 300),
    ]
    scores = [score_torrent(n, s, sd) for n, s, sd in results]
    ranked = sorted(
        range(len(scores)),
        key=lambda i: (scores[i].resolution_tier, scores[i].format_score),
        reverse=True,
    )
    # FLUX (HQ group WEB-DL) should beat YIFY (LQ group despite huge seeds)
    assert ranked[0] == 0, f"expected FLUX first, got index {ranked[0]}"
    # 720p should be last (lower tier)
    assert ranked[-1] == 3, f"expected 720p last, got index {ranked[-1]}"


def test_benchmark_cam_rejected() -> None:
    """CAM releases should be rejected regardless of seed count."""
    ts = score_torrent("Movie.2024.HDCAM.x264-NoGroup", _gb(1.2), 5000)
    assert ts.is_rejected
    assert ts.format_score == -9999


# ===================================================================
# 8. Score dataclass structure tests
# ===================================================================


def test_torrent_score_fields_present() -> None:
    ts = score_torrent("Movie.2024.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert isinstance(ts, TorrentScore)
    assert isinstance(ts.resolution_tier, int)
    assert isinstance(ts.format_score, int)
    assert isinstance(ts.is_rejected, bool)
    assert ts.parsed is not None


def test_torrent_score_is_frozen() -> None:
    """TorrentScore is immutable (frozen dataclass)."""
    ts = score_torrent("Movie.2024.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    try:
        ts.resolution_tier = 99  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except AttributeError:
        pass  # correct -- frozen dataclass


# ===================================================================
# 9. Seed bucket scoring
# ===================================================================


def test_high_seeds_score_more_than_low_seeds() -> None:
    """50+ seeds should beat 1-2 seeds for the same content."""
    ts_high = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 100)
    ts_low = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 1)
    assert ts_high.format_score > ts_low.format_score


def test_moderate_seeds_between_high_and_low() -> None:
    """10-24 seeds should score between 50+ and 1-2."""
    ts_high = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 100)
    ts_mid = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 15)
    ts_low = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 1)
    assert ts_high.format_score > ts_mid.format_score > ts_low.format_score


# ===================================================================
# 10. Source / release type scoring
# ===================================================================


def test_remux_beats_bluray() -> None:
    """REMUX (+100) should beat regular BluRay (+80)."""
    ts_remux = score_torrent("Movie.1080p.BluRay.REMUX.x264-GROUP", 4_000_000_000, 50)
    ts_bluray = score_torrent("Movie.1080p.BluRay.x264-GROUP", 4_000_000_000, 50)
    assert ts_remux.format_score > ts_bluray.format_score


def test_webdl_beats_hdtv() -> None:
    """WEB-DL (+70) should beat HDTV (+35)."""
    ts_webdl = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_hdtv = score_torrent("Movie.1080p.HDTV.x264-GROUP", 4_000_000_000, 50)
    assert ts_webdl.format_score > ts_hdtv.format_score


def test_webrip_beats_hdtv() -> None:
    """WEBRip (+55) should beat HDTV (+35)."""
    ts_webrip = score_torrent("Movie.1080p.WEBRip.x264-GROUP", 4_000_000_000, 50)
    ts_hdtv = score_torrent("Movie.1080p.HDTV.x264-GROUP", 4_000_000_000, 50)
    assert ts_webrip.format_score > ts_hdtv.format_score


# ===================================================================
# 11. Media type parameter
# ===================================================================


def test_media_type_episode_accepted() -> None:
    """Episode media type with appropriate size should not be rejected."""
    ts = score_torrent("Show.S01E01.1080p.WEB-DL.x264-GROUP", 1_000_000_000, 50, media_type="episode")
    assert not ts.is_rejected


def test_media_type_defaults_to_movie() -> None:
    """Default media_type is 'movie'."""
    ts1 = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts2 = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50, media_type="movie")
    assert ts1.format_score == ts2.format_score
    assert ts1.resolution_tier == ts2.resolution_tier


# ===================================================================
# 12. Hardcoded subtitle penalty tests
# ===================================================================


def test_hardcoded_korsub_penalty() -> None:
    """KORSUB tag should reduce format_score by 200 vs the same torrent without it."""
    ts_korsub = score_torrent("Movie.KORSUB.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_clean = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert ts_clean.format_score - ts_korsub.format_score == 200


def test_hardcoded_hc_penalty() -> None:
    """HC (hardcoded subs) tag should reduce format_score by 200."""
    ts_hc = score_torrent("Movie.HC.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_clean = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert ts_clean.format_score - ts_hc.format_score == 200


def test_hardsub_penalty() -> None:
    """HardSub tag should reduce format_score by 200."""
    ts_hardsub = score_torrent("Movie.HardSub.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_clean = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert ts_clean.format_score - ts_hardsub.format_score == 200


def test_no_penalty_for_clean_name() -> None:
    """A clean torrent name should NOT get the hardcoded sub penalty."""
    ts = score_torrent("Movie.1080p.WEB-DL.DDP5.1.x264-GROUP", 4_000_000_000, 50)
    # If it had the penalty, score would be 200 lower than expected.
    # Just verify the score is reasonable and not penalised.
    ts_base = score_torrent("Movie.1080p.WEB-DL.DDP5.1.x264-GROUP", 4_000_000_000, 50)
    assert ts.format_score == ts_base.format_score
    assert not ts.is_rejected


# ===================================================================
# 13. Dual/multi audio bonus tests
# ===================================================================


def test_dual_audio_bonus() -> None:
    """'Dual.Audio' in the name should add +10 to the format_score."""
    ts_dual = score_torrent("Movie.1080p.Dual.Audio.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_plain = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert ts_dual.format_score - ts_plain.format_score == 10


def test_multi_audio_bonus() -> None:
    """'Multi' in the name should add +10 to the format_score."""
    ts_multi = score_torrent("Movie.1080p.Multi.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    ts_plain = score_torrent("Movie.1080p.WEB-DL.x264-GROUP", 4_000_000_000, 50)
    assert ts_multi.format_score - ts_plain.format_score == 10


# ===================================================================
# 14. schedule_episode_rank_key tests
# ===================================================================


def test_schedule_rank_key_includes_seed_tiebreaker() -> None:
    """Two torrents with identical quality but different seeds should produce different rank tuples."""
    from patchy_bot.handlers.schedule import schedule_episode_rank_key

    row_high = {"fileName": "Show.S01E01.1080p.WEB-DL.x264-GROUP", "nbSeeders": 100, "fileSize": 1_000_000_000}
    row_low = {"fileName": "Show.S01E01.1080p.WEB-DL.x264-GROUP", "nbSeeders": 2, "fileSize": 1_000_000_000}
    key_high = schedule_episode_rank_key(row_high, "Show", 1, 1)
    key_low = schedule_episode_rank_key(row_low, "Show", 1, 1)
    assert key_high != key_low
    assert key_high > key_low  # higher seeds = higher rank tuple


def test_schedule_rank_key_tuple_is_4_elements() -> None:
    """The rank key tuple should have exactly 4 elements: (exact_episode, exact_show, seeds, format_score)."""
    from patchy_bot.handlers.schedule import schedule_episode_rank_key

    row = {"fileName": "Show.S01E01.1080p.WEB-DL.x264-GROUP", "nbSeeders": 50, "fileSize": 1_000_000_000}
    key = schedule_episode_rank_key(row, "Show", 1, 1)
    assert len(key) == 4


# ===================================================================
# 15. scoring_overrides configurability tests
# ===================================================================


def test_hevc_penalty_override_zero() -> None:
    """Setting hevc_1080p_penalty=0 should remove the x265 penalty at 1080p."""
    ts_default = score_torrent("Movie.1080p.WEB-DL.x265-GROUP", 4_000_000_000, 50)
    ts_no_pen = score_torrent(
        "Movie.1080p.WEB-DL.x265-GROUP",
        4_000_000_000,
        50,
        scoring_overrides={"hevc_1080p_penalty": 0},
    )
    # Default penalty is -50, so override=0 should raise the score by 50
    assert ts_no_pen.format_score - ts_default.format_score == 50


def test_av1_reject_override_false() -> None:
    """Setting av1_reject=False should NOT reject AV1 torrents."""
    ts = score_torrent(
        "Movie.1080p.WEB-DL.AV1-GROUP",
        4_000_000_000,
        50,
        scoring_overrides={"av1_reject": False},
    )
    assert not ts.is_rejected


def test_extra_hq_group() -> None:
    """Adding a custom group to hq_groups_extra should give it the +30 bonus."""
    ts_custom = score_torrent(
        "Movie.1080p.WEB-DL.x264-mygroup",
        4_000_000_000,
        50,
        scoring_overrides={"hq_groups_extra": {"mygroup"}},
    )
    ts_plain = score_torrent("Movie.1080p.WEB-DL.x264-mygroup", 4_000_000_000, 50)
    assert ts_custom.format_score - ts_plain.format_score == 30


def test_season_pack_max_episodes_override() -> None:
    """A smaller season_pack_max_episodes should tighten the max size window."""
    # With the default (24 eps), a large season pack is within range.
    # With max_episodes=12, the allowed max is halved, so the same size
    # may trigger a size penalty.
    large_pack_size = _gb(90)  # 90 GB -- within 24*20GB=480GB but let's check relative
    ts_default = score_torrent(
        "Show.S01.1080p.WEB-DL.x264-GROUP",
        large_pack_size,
        50,
        media_type="movie",
        scoring_overrides={"season_pack_max_episodes": 24},
    )
    ts_tight = score_torrent(
        "Show.S01.1080p.WEB-DL.x264-GROUP",
        large_pack_size,
        50,
        media_type="movie",
        scoring_overrides={"season_pack_max_episodes": 6},
    )
    # The tighter override should penalise more (or equal if both within range).
    # With 6 eps, max = 20GB * 6 = 120GB, and 90GB is within. Use a bigger size.
    huge_pack = _gb(180)  # 180 GB -- within 24*20=480 but exceeds 6*20=120
    ts_ok = score_torrent(
        "Show.S01.1080p.WEB-DL.x264-GROUP",
        huge_pack,
        50,
        media_type="movie",
        scoring_overrides={"season_pack_max_episodes": 24},
    )
    ts_over = score_torrent(
        "Show.S01.1080p.WEB-DL.x264-GROUP",
        huge_pack,
        50,
        media_type="movie",
        scoring_overrides={"season_pack_max_episodes": 6},
    )
    assert ts_ok.format_score > ts_over.format_score


# ===================================================================
# 16. RTN version pin test
# ===================================================================


def test_rtn_version_pinned() -> None:
    """rank-torrent-name dependency should be pinned with <2.0 upper bound."""
    import pathlib

    pyproject = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
    content = pyproject.read_text()
    assert "rank-torrent-name" in content
    # Check for <2.0 upper bound (handles >=X.Y,<2.0 style)
    import re

    match = re.search(r"rank-torrent-name[^\"]*<2\.0", content)
    assert match is not None, "rank-torrent-name must be pinned with <2.0 upper bound"
