# Community 18 — Delete Safety

**45 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `_make_bot()` | `telegram-qbt/tests/test_delete_safety.py:L91` | 24 |
| `._delete_remove_candidate()` | `telegram-qbt/patchy_bot/bot.py:L3910` | 22 |
| `test_delete_safety.py` | `telegram-qbt/tests/test_delete_safety.py:L1` | 11 |
| `TestMovieDeletion` | `telegram-qbt/tests/test_delete_safety.py:L103` | 7 |
| `TestTVEpisodeDeletion` | `telegram-qbt/tests/test_delete_safety.py:L311` | 6 |
| `TestTVSeasonDeletion` | `telegram-qbt/tests/test_delete_safety.py:L257` | 5 |
| `_make_config()` | `telegram-qbt/tests/test_delete_safety.py:L29` | 4 |
| `.test_nested_movie_path_is_rejected()` | `telegram-qbt/tests/test_delete_safety.py:L160` | 4 |
| `.test_root_path_itself_is_rejected()` | `telegram-qbt/tests/test_delete_safety.py:L176` | 4 |
| `TestTVShowDeletion` | `telegram-qbt/tests/test_delete_safety.py:L221` | 4 |
| `.test_show_root_as_season_is_rejected()` | `telegram-qbt/tests/test_delete_safety.py:L277` | 4 |
| `.test_episode_path_as_season_is_rejected()` | `telegram-qbt/tests/test_delete_safety.py:L293` | 4 |
| `.test_directory_as_episode_is_rejected()` | `telegram-qbt/tests/test_delete_safety.py:L348` | 4 |
| `.test_too_deep_episode_is_rejected()` | `telegram-qbt/tests/test_delete_safety.py:L364` | 4 |
| `TestEdgeCases` | `telegram-qbt/tests/test_delete_safety.py:L424` | 4 |

## Connected Communities

- [[Community 1 — BotApp & Command Flow]] (2 edges)
- [[Community 4 — Parsing & Utilities]] (1 edges)
- [[Community 13 — Completion Security]] (1 edges)
- [[Community 0 — Core Types & Clients]] (1 edges)

## All Nodes (45)

- `_make_bot()` — `telegram-qbt/tests/test_delete_safety.py` (24)
- `._delete_remove_candidate()` — `telegram-qbt/patchy_bot/bot.py` (22)
- `test_delete_safety.py` — `telegram-qbt/tests/test_delete_safety.py` (11)
- `TestMovieDeletion` — `telegram-qbt/tests/test_delete_safety.py` (7)
- `TestTVEpisodeDeletion` — `telegram-qbt/tests/test_delete_safety.py` (6)
- `TestTVSeasonDeletion` — `telegram-qbt/tests/test_delete_safety.py` (5)
- `_make_config()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_nested_movie_path_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_root_path_itself_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `TestTVShowDeletion` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_show_root_as_season_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_episode_path_as_season_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_directory_as_episode_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_too_deep_episode_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `TestEdgeCases` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_symlink_inside_movie_dir_still_allows_dir_delete()` — `telegram-qbt/tests/test_delete_safety.py` (4)
- `.test_valid_movie_folder_is_deleted()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_path_traversal_dot_dot_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_symlink_target_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_valid_spam_folder_is_deleted()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_valid_show_folder_is_deleted()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_nested_path_as_show_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_valid_season_folder_is_deleted()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_valid_episode_file_depth_2_is_deleted()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_valid_episode_file_depth_3_is_deleted()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `TestUnsupportedRootKey` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_unknown_root_key_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_unsupported_tv_remove_kind_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_nonexistent_target_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_empty_path_is_rejected()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `TestSpamDeletion` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `Unit tests for the _delete_remove_candidate path-safety guards.  These tests ver` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Build a Config whose media roots point into tmp_path.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Build a BotApp whose Plex client reports not-ready (skips Plex calls).` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Tests for movies root_key — expects exactly depth 1 (one folder).` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Movies must be exactly 1 level deep — a subfolder inside a movie dir is rejected` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Trying to delete the media root itself must fail.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `TV show removal (remove_kind='show') expects depth 1.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `TV season removal (remove_kind='season') expects depth 2.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Depth 1 path with remove_kind='season' must be rejected.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Depth 3 path with remove_kind='season' must be rejected.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `TV episode removal (remove_kind='episode') expects depth 1-3, must be a file.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `A directory cannot be deleted as an 'episode' — only files.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `Depth 4+ must be rejected.` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `The symlink check is on the target path itself, not contents inside it.` — `telegram-qbt/tests/test_delete_safety.py` (1)
