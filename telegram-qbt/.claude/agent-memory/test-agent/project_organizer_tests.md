---
name: Organizer test coverage
description: 31 tests covering patchy_bot/plex_organizer.py — parsing, file moves, edge cases
type: project
---

tests/test_organizer.py has 31 tests covering plex_organizer.py:
- _parse_tv: 8 tests (standard, multi-ep, season pack, site prefix, uppercase, year stripping, tracker tags)
- _parse_movie: 6 tests (scene, parens, brackets, no-year, old year, site prefix)
- _strip_site_prefix: 3 tests
- organize_download with tmp_path: 9 tests (movie file, TV file, TV dir with subs, junk skipping, movie dir, nonexistent path, unknown category, empty dir)
- organize_tv existing dir: 2 tests (reuse existing show dir, auto-create season)
- organize_movie already organized: 1 test
- Edge cases: 2 tests (empty/None content_path)

Key finding: _parse_movie strips ALL bracket content including year — so "[2024]" in brackets makes it unparseable. Tests reflect actual behavior.

**Why:** plex_organizer.py had zero test coverage before this.
**How to apply:** When modifying organizer logic, run `pytest tests/test_organizer.py -v` to catch regressions.
