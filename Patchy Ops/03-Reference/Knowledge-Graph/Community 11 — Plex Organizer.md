# Community 11 — Plex Organizer

**91 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `plex_organizer.py` | `telegram-qbt/patchy_bot/plex_organizer.py:L1` | 15 |
| `_parse_tv()` | `telegram-qbt/patchy_bot/plex_organizer.py:L59` | 15 |
| `organize_download()` | `telegram-qbt/patchy_bot/plex_organizer.py:L324` | 15 |
| `_parse_movie()` | `telegram-qbt/patchy_bot/plex_organizer.py:L94` | 14 |
| `organize_movie()` | `telegram-qbt/patchy_bot/plex_organizer.py:L246` | 11 |
| `organize_tv()` | `telegram-qbt/patchy_bot/plex_organizer.py:L157` | 10 |
| `_try_remove_empty_tree()` | `telegram-qbt/patchy_bot/plex_organizer.py:L352` | 9 |
| `TestParseTv` | `telegram-qbt/tests/test_organizer.py:L22` | 9 |
| `TestOrganizeDownload` | `telegram-qbt/tests/test_organizer.py:L155` | 9 |
| `test_organizer.py` | `telegram-qbt/tests/test_organizer.py:L1` | 8 |
| `TestParseMovie` | `telegram-qbt/tests/test_organizer.py:L87` | 8 |
| `TestTryRemoveEmptyTree` | `telegram-qbt/tests/test_plex_organizer.py:L10` | 8 |
| `_strip_site_prefix()` | `telegram-qbt/patchy_bot/plex_organizer.py:L35` | 7 |
| `_strip_tracker_tags()` | `telegram-qbt/patchy_bot/plex_organizer.py:L40` | 5 |
| `_strip_brackets()` | `telegram-qbt/patchy_bot/plex_organizer.py:L45` | 5 |

## Connected Communities

- [[Community 2 — Download Pipeline]] (1 edges)
- [[Community 3 — Malware Scanning]] (1 edges)

## All Nodes (91)

- `plex_organizer.py` — `telegram-qbt/patchy_bot/plex_organizer.py` (15)
- `_parse_tv()` — `telegram-qbt/patchy_bot/plex_organizer.py` (15)
- `organize_download()` — `telegram-qbt/patchy_bot/plex_organizer.py` (15)
- `_parse_movie()` — `telegram-qbt/patchy_bot/plex_organizer.py` (14)
- `organize_movie()` — `telegram-qbt/patchy_bot/plex_organizer.py` (11)
- `organize_tv()` — `telegram-qbt/patchy_bot/plex_organizer.py` (10)
- `_try_remove_empty_tree()` — `telegram-qbt/patchy_bot/plex_organizer.py` (9)
- `TestParseTv` — `telegram-qbt/tests/test_organizer.py` (9)
- `TestOrganizeDownload` — `telegram-qbt/tests/test_organizer.py` (9)
- `test_organizer.py` — `telegram-qbt/tests/test_organizer.py` (8)
- `TestParseMovie` — `telegram-qbt/tests/test_organizer.py` (8)
- `TestTryRemoveEmptyTree` — `telegram-qbt/tests/test_plex_organizer.py` (8)
- `_strip_site_prefix()` — `telegram-qbt/patchy_bot/plex_organizer.py` (7)
- `_strip_tracker_tags()` — `telegram-qbt/patchy_bot/plex_organizer.py` (5)
- `_strip_brackets()` — `telegram-qbt/patchy_bot/plex_organizer.py` (5)
- `TestOrganizeMovie` — `telegram-qbt/tests/test_plex_organizer.py` (5)
- `OrganizeResult` — `telegram-qbt/patchy_bot/plex_organizer.py` (4)
- `_dots_to_spaces()` — `telegram-qbt/patchy_bot/plex_organizer.py` (4)
- `_find_existing_movie_dir()` — `telegram-qbt/patchy_bot/plex_organizer.py` (4)
- `TestStripSitePrefix` — `telegram-qbt/tests/test_organizer.py` (4)
- `_find_existing_show_dir()` — `telegram-qbt/patchy_bot/plex_organizer.py` (3)
- `TestOrganizeTvExistingDir` — `telegram-qbt/tests/test_organizer.py` (3)
- `TestEdgeCases` — `telegram-qbt/tests/test_organizer.py` (3)
- `test_plex_organizer.py` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_removes_empty_dir_inside_allowed_root()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_keeps_dir_with_media_files()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_rejects_path_outside_allowed_roots()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_rejects_symlinked_path()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_rejects_path_equal_to_root()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_no_allowed_roots_original_behavior()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_single_video_renamed()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_multi_video_not_renamed()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_no_video_files()` — `telegram-qbt/tests/test_plex_organizer.py` (3)
- `.test_standard_single_episode()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_multi_episode()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_season_pack_sXX()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_site_prefix_stripped()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_non_tv_returns_none()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_upper_case()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_year_stripped_from_show_name()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_tracker_tag_stripped()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_scene_format()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_parens_year()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_brackets_year_inside_returns_none()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_brackets_tracker_only()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_no_year_returns_none()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_old_year()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_site_prefix_stripped()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_removes_prefix()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_no_prefix_unchanged()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_dash_variant()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_movie_single_file()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_tv_single_file()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_tv_directory_video_and_subtitle()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_tv_directory_junk_files_skipped()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_movie_directory()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_nonexistent_path()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_unknown_category()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_empty_directory_no_media()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_uses_existing_show_dir()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_season_dir_auto_created()` — `telegram-qbt/tests/test_organizer.py` (2)
- `TestOrganizeMovieAlreadyOrganized` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_already_organized_returns_false()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_empty_content_path()` — `telegram-qbt/tests/test_organizer.py` (2)
- `.test_none_content_path()` — `telegram-qbt/tests/test_organizer.py` (2)
- `Post-download media organizer for Plex.  Parses scene-release torrent names and` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Remove leading site prefixes like 'www.UIndex.org    -    '.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Remove trailing tracker tags like (EZTVx.to), (TGx), etc.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Remove all bracket-enclosed tags like (1080p), (YTS.MX), (BluRay).` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Convert dot-separated scene names to spaces, preserving extensions.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Extract (show_name, season_num, (episode_nums)) from a torrent name.      Return` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Extract (movie_title, year) from a torrent name.      Returns None if not detect` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Find an existing show directory that matches the parsed name.      Handles case` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Find an existing movie directory matching title and year.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Organize a completed TV download into Show/Season XX/ structure.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Organize a completed movie download into Movie Name (Year)/ structure.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Main entry point. Routes to TV or movie organizer based on category.` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Remove a directory tree if it contains no more media files.      When *allowed_r` — `telegram-qbt/patchy_bot/plex_organizer.py` (1)
- `Tests for patchy_bot.plex_organizer — media file organization into Plex structur` — `telegram-qbt/tests/test_organizer.py` (1)
- `Tests for _try_remove_empty_tree path containment guard.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `_try_remove_empty_tree respects allowed_roots and rejects unsafe paths.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Empty dir inside allowed root is removed.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Dir containing media files is NOT removed.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Path outside allowed roots is NOT removed, warning logged.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Symlinked path is NOT removed, warning logged.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Path resolving to the root itself is NOT removed.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Empty allowed_roots — removes empty dir (backward compat).` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `organize_movie handles single and multi-video directories correctly.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Single video file is renamed to match the movie name.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Multiple video files keep their original names.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
- `Directory with no video files is rejected to prevent junk in Plex.` — `telegram-qbt/tests/test_plex_organizer.py` (1)
