---
name: Quality test coverage
description: tests/test_quality.py covers patchy_bot/quality.py with 56 tests across 16 categories
type: project
---

test_quality.py has 56 function-based tests covering:
- Garbage rejection (CAM, TS, TC, AV1, upscaled, zero seeds) -- 9 tests
- Resolution tier ordering (2160/1080/720/480/unknown) -- 5 tests
- Codec preference (x264 vs x265 resolution-aware, XviD penalty) -- 4 tests
- Release group reputation (HQ bonus, LQ penalty) -- 4 tests
- Season pack detection (S01, S01E01, COMPLETE, Season N, multi-season, pre-parsed) -- 7 tests
- Quality label display (WEB-DL, unknown, 4K REMUX) -- 3 tests
- Benchmark ranking of realistic search results -- 2 tests
- TorrentScore dataclass structure and immutability -- 2 tests
- Seed bucket scoring -- 2 tests
- Source/release type scoring (REMUX > BluRay > WEB-DL > HDTV) -- 3 tests
- Media type parameter handling -- 2 tests
- Hardcoded subtitle penalty (KORSUB, HC, HardSub, clean name) -- 4 tests
- Dual/multi audio bonus -- 2 tests
- schedule_episode_rank_key (seed tiebreaker, 5-element tuple) -- 2 tests
- scoring_overrides configurability (hevc penalty, av1 reject, hq_groups_extra, season_pack_max_episodes) -- 4 tests
- RTN version pin (<2.0 upper bound in pyproject.toml) -- 1 test

**Why:** quality.py had zero test coverage initially; now fully covered including new features.
**How to apply:** When modifying scoring logic in quality.py, run these tests to catch regressions. Add new tests here when new scoring rules are added.
