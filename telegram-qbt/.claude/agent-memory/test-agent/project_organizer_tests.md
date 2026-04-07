---
name: Organizer test coverage
description: 37 tests covering patchy_bot/plex_organizer.py — parsing, file moves, path containment guard
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

tests/test_plex_organizer.py has 6 tests covering _try_remove_empty_tree (TestTryRemoveEmptyTree class):
- removes empty dir inside allowed root (non-media file present)
- keeps dir with media files (.mkv)
- rejects path outside allowed roots — dir preserved, warning logged ("outside media roots")
- rejects symlinked path — dir preserved, warning logged ("symlinked path")
- rejects path equal to root itself — root preserved, warning logged ("outside media roots")
- no allowed_roots — backward-compat removal of empty dir still works

Key finding: _parse_movie strips ALL bracket content including year — so "[2024]" in brackets makes it unparseable. Tests reflect actual behavior.
Symlink log message: "Refusing to remove symlinked path: %s -> %s" — test checks lowercase "symlinked path".
Root-equal rejection uses same "outside media roots" message as out-of-bounds — path must startswith(root + os.sep), not just startswith(root).

**Why:** plex_organizer.py had zero test coverage before this; _try_remove_empty_tree gained allowed_roots guard.
**How to apply:** When modifying organizer logic, run `pytest tests/test_organizer.py tests/test_plex_organizer.py -v` to catch regressions.
