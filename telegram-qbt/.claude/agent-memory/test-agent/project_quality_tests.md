---
name: Quality test coverage
description: tests/test_quality.py covers patchy_bot/quality.py with 43 tests across 11 categories
type: project
---

test_quality.py was created 2026-04-05 with 43 function-based tests covering:
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

**Why:** quality.py had zero test coverage; this closes that gap.
**How to apply:** When modifying scoring logic in quality.py, run these tests to catch regressions. Add new tests here when new scoring rules are added.
