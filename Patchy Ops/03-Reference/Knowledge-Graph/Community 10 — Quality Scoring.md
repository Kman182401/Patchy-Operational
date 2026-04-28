# Community 10 — Quality Scoring

**107 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `score_torrent()` | `telegram-qbt/patchy_bot/quality.py:L153` | 64 |
| `test_quality.py` | `telegram-qbt/tests/test_quality.py:L1` | 58 |
| `TorrentScore` | `telegram-qbt/patchy_bot/quality.py:L85` | 39 |
| `is_season_pack()` | `telegram-qbt/patchy_bot/quality.py:L120` | 12 |
| `quality.py` | `telegram-qbt/patchy_bot/quality.py:L1` | 9 |
| `parse_quality()` | `telegram-qbt/patchy_bot/quality.py:L108` | 8 |
| `schedule_episode_rank_key()` | `telegram-qbt/patchy_bot/handlers/schedule.py:L1210` | 8 |
| `quality_label()` | `telegram-qbt/patchy_bot/quality.py:L423` | 7 |
| `_gb()` | `telegram-qbt/tests/test_quality.py:L28` | 5 |
| `test_season_pack_with_preparsed_data()` | `telegram-qbt/tests/test_quality.py:L228` | 4 |
| `test_benchmark_movie_ranking()` | `telegram-qbt/tests/test_quality.py:L272` | 4 |
| `test_benchmark_cam_rejected()` | `telegram-qbt/tests/test_quality.py:L292` | 4 |
| `test_season_pack_max_episodes_override()` | `telegram-qbt/tests/test_quality.py:L510` | 4 |
| `test_rejected_score_is_negative()` | `telegram-qbt/tests/test_quality.py:L88` | 3 |
| `test_tier_values_are_correct()` | `telegram-qbt/tests/test_quality.py:L123` | 3 |

## Connected Communities

- [[Community 5 — Search & Filters]] (7 edges)
- [[Community 0 — Core Types & Clients]] (6 edges)
- [[Community 3 — Malware Scanning]] (3 edges)
- [[Community 1 — BotApp & Command Flow]] (3 edges)
- [[Community 6 — Movie Scheduling]] (3 edges)
- [[Community 4 — Parsing & Utilities]] (3 edges)
- [[Community 2 — Download Pipeline]] (2 edges)
- [[Community 12 — Full Series Downloads]] (1 edges)

## All Nodes (107)

- `score_torrent()` — `telegram-qbt/patchy_bot/quality.py` (64)
- `test_quality.py` — `telegram-qbt/tests/test_quality.py` (58)
- `TorrentScore` — `telegram-qbt/patchy_bot/quality.py` (39)
- `is_season_pack()` — `telegram-qbt/patchy_bot/quality.py` (12)
- `quality.py` — `telegram-qbt/patchy_bot/quality.py` (9)
- `parse_quality()` — `telegram-qbt/patchy_bot/quality.py` (8)
- `schedule_episode_rank_key()` — `telegram-qbt/patchy_bot/handlers/schedule.py` (8)
- `quality_label()` — `telegram-qbt/patchy_bot/quality.py` (7)
- `_gb()` — `telegram-qbt/tests/test_quality.py` (5)
- `test_season_pack_with_preparsed_data()` — `telegram-qbt/tests/test_quality.py` (4)
- `test_benchmark_movie_ranking()` — `telegram-qbt/tests/test_quality.py` (4)
- `test_benchmark_cam_rejected()` — `telegram-qbt/tests/test_quality.py` (4)
- `test_season_pack_max_episodes_override()` — `telegram-qbt/tests/test_quality.py` (4)
- `test_rejected_score_is_negative()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_tier_values_are_correct()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_x264_preferred_over_x265_at_1080p()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_x265_preferred_over_x264_at_4k()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_x265_penalty_at_720p()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_xvid_heavily_penalised()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_lq_group_penalised()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_hq_group_bonus()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_multiple_lq_groups_penalised()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_flux_hq_group_bonus()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_single_episode_not_pack_with_preparsed()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_quality_label_webdl_with_audio_and_group()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_quality_label_unknown()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_quality_label_4k_remux()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_torrent_score_is_frozen()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_high_seeds_score_more_than_low_seeds()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_moderate_seeds_between_high_and_low()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_remux_beats_bluray()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_webdl_beats_hdtv()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_webrip_beats_hdtv()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_media_type_episode_accepted()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_media_type_defaults_to_movie()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_hardcoded_korsub_penalty()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_hardcoded_hc_penalty()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_hardsub_penalty()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_no_penalty_for_clean_name()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_dual_audio_bonus()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_multi_audio_bonus()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_schedule_rank_key_includes_seed_tiebreaker()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_schedule_rank_key_tuple_is_4_elements()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_hevc_penalty_override_zero()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_av1_reject_override_false()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_extra_hq_group()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_rtn_version_pinned()` — `telegram-qbt/tests/test_quality.py` (3)
- `test_cam_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_telesync_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_telecine_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_av1_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_upscaled_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_zero_seeds_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_legitimate_1080p_not_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_legitimate_720p_not_rejected()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_1080p_tier_beats_720p_tier()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_2160p_tier_beats_1080p_tier()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_720p_tier_beats_480p_tier()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_unknown_resolution_gets_tier_zero()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_season_pack_s01()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_single_episode_not_pack()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_complete_series()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_season_word()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_multi_season_pack()` — `telegram-qbt/tests/test_quality.py` (2)
- `test_torrent_score_fields_present()` — `telegram-qbt/tests/test_quality.py` (2)
- `Tests for the torrent quality scoring engine (patchy_bot/quality.py).  Covers:` — `telegram-qbt/tests/test_quality.py` (2)
- `Convert gigabytes to bytes.` — `telegram-qbt/tests/test_quality.py` (2)
- `All rejected torrents get format_score = -9999.` — `telegram-qbt/tests/test_quality.py` (2)
- `2160p=4, 1080p=3, 720p=2, 480p=1.` — `telegram-qbt/tests/test_quality.py` (2)
- `At 1080p, x264 (avc +70) beats x265 (hevc -50) due to transcoding concerns.` — `telegram-qbt/tests/test_quality.py` (2)
- `At 2160p, x265 (hevc +80) beats x264 (avc +40) since HEVC is efficient for 4K.` — `telegram-qbt/tests/test_quality.py` (2)
- `At 720p (not 4K), x265 still gets penalised same as 1080p.` — `telegram-qbt/tests/test_quality.py` (2)
- `XviD gets -200, making it score far below x264/x265.` — `telegram-qbt/tests/test_quality.py` (2)
- `YIFY (LQ group) scores far below an unknown group.` — `telegram-qbt/tests/test_quality.py` (2)
- `NTG (HQ group, +30) scores above an unknown group with identical content.` — `telegram-qbt/tests/test_quality.py` (2)
- `All known LQ groups get the same penalty.` — `telegram-qbt/tests/test_quality.py` (2)
- `FLUX (HQ group) gets the +30 bonus.` — `telegram-qbt/tests/test_quality.py` (2)
- `When a ParsedData object is passed, uses its fields directly.` — `telegram-qbt/tests/test_quality.py` (2)
- `Best 1080p WEB-DL from HQ group should rank first; 720p should rank last.` — `telegram-qbt/tests/test_quality.py` (2)
- `CAM releases should be rejected regardless of seed count.` — `telegram-qbt/tests/test_quality.py` (2)
- `TorrentScore is immutable (frozen dataclass).` — `telegram-qbt/tests/test_quality.py` (2)
- `50+ seeds should beat 1-2 seeds for the same content.` — `telegram-qbt/tests/test_quality.py` (2)
- `10-24 seeds should score between 50+ and 1-2.` — `telegram-qbt/tests/test_quality.py` (2)
- `REMUX (+100) should beat regular BluRay (+80).` — `telegram-qbt/tests/test_quality.py` (2)
- `WEB-DL (+70) should beat HDTV (+35).` — `telegram-qbt/tests/test_quality.py` (2)
- `WEBRip (+55) should beat HDTV (+35).` — `telegram-qbt/tests/test_quality.py` (2)
- `Episode media type with appropriate size should not be rejected.` — `telegram-qbt/tests/test_quality.py` (2)
- `Default media_type is 'movie'.` — `telegram-qbt/tests/test_quality.py` (2)
- `KORSUB tag should reduce format_score by 200 vs the same torrent without it.` — `telegram-qbt/tests/test_quality.py` (2)
- `HC (hardcoded subs) tag should reduce format_score by 200.` — `telegram-qbt/tests/test_quality.py` (2)
- `HardSub tag should reduce format_score by 200.` — `telegram-qbt/tests/test_quality.py` (2)
- `A clean torrent name should NOT get the hardcoded sub penalty.` — `telegram-qbt/tests/test_quality.py` (2)
- `Dual.Audio' in the name should add +10 to the format_score.` — `telegram-qbt/tests/test_quality.py` (2)
- `Multi' in the name should add +10 to the format_score.` — `telegram-qbt/tests/test_quality.py` (2)
- `Two torrents with identical quality but different seeds should produce different` — `telegram-qbt/tests/test_quality.py` (2)
- `The rank key tuple should have exactly 4 elements: (exact_episode, exact_show, s` — `telegram-qbt/tests/test_quality.py` (2)
- `Setting hevc_1080p_penalty=0 should remove the x265 penalty at 1080p.` — `telegram-qbt/tests/test_quality.py` (2)
- `Setting av1_reject=False should NOT reject AV1 torrents.` — `telegram-qbt/tests/test_quality.py` (2)
- `Adding a custom group to hq_groups_extra should give it the +30 bonus.` — `telegram-qbt/tests/test_quality.py` (2)
- `A smaller season_pack_max_episodes should tighten the max size window.` — `telegram-qbt/tests/test_quality.py` (2)
- `rank-torrent-name dependency should be pinned with <2.0 upper bound.` — `telegram-qbt/tests/test_quality.py` (2)
- `Torrent quality scoring engine backed by RTN (rank-torrent-name).  Two-layer ran` — `telegram-qbt/patchy_bot/quality.py` (1)
- `Immutable scoring result for one torrent.      Attributes:         resolution_ti` — `telegram-qbt/patchy_bot/quality.py` (1)
- `Thin wrapper around RTN parse().      Args:         name: Raw torrent name strin` — `telegram-qbt/patchy_bot/quality.py` (1)
- `Return True if the torrent is a season pack rather than a single episode.      U` — `telegram-qbt/patchy_bot/quality.py` (1)
- `Score a torrent for quality ranking.      Higher ``resolution_tier`` always beat` — `telegram-qbt/patchy_bot/quality.py` (1)
- `Build a short quality label for UI display.      Args:         parsed: RTN Parse` — `telegram-qbt/patchy_bot/quality.py` (1)
