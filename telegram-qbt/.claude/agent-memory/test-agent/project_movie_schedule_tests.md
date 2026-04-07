---
name: Movie schedule tests
description: 29 tests in tests/test_movie_schedule.py covering the movie release tracking Store CRUD and TVMetadataClient TMDB methods
type: project
---

29 tests in `/home/karson/Patchy_Bot/telegram-qbt/tests/test_movie_schedule.py`.

**Why:** Movie schedule feature added persistent `movie_tracks` table to Store and two TMDB methods to TVMetadataClient — needed dedicated coverage.

**How to apply:** When touching `store.py` movie_tracks methods or `clients/tv_metadata.py` search_movies/get_movie_release_dates, run this file first to catch regressions.

## TestMovieTrackCRUD (15 tests)
- create_and_get — round-trip all fields including status=pending, notified=0
- get_pending_respects_release_date — future release_date_ts excluded, past included
- get_pending_respects_next_check — next_check_ts in the future suppresses row
- update_status — status, torrent_hash, notified, next_check_ts all persist
- delete — row gone after delete_movie_track
- exists_for_tmdb — True only when user_id AND tmdb_id both match
- get_downloading — only status='downloading' rows returned
- get_tracks_for_user — user isolation confirmed
- create_returns_unique_ids — secrets.token_hex(8) uniqueness
- get_nonexistent_track_returns_none
- update_status_error_text — error_text field persists
- get_pending_only_returns_pending_status — downloading rows excluded
- year_can_be_none — NULL year round-trips without error
- get_tracks_for_user_empty — returns [] for unknown user
- get_downloading_empty / get_pending_empty — clean slate assertions

## TestTMDBMovieMethods (14 tests)
- search_movies_returns_top5 — caps at 5 even when TMDB returns 10
- search_movies_empty_on_error — RuntimeError from _get_json → []
- search_movies_no_api_key — tmdb_api_key=None → []
- get_release_dates_us — type 3→theatrical, 4→digital, GB entry ignored
- get_release_dates_region_missing — missing region → {}
- get_release_dates_no_api_key — tmdb_api_key=None → {}
- get_release_dates_error_returns_empty — RuntimeError → {}
- search_movies_result_fields — tmdb_id, title, year, overview, popularity all mapped
- search_movies_missing_release_date_year_is_none — blank release_date → year=None
- get_release_dates_physical_type — type 5 → 'physical' key
- get_release_dates_unknown_type_ignored — types 1,2,6 silently dropped → {}
- search_movies_fewer_than_5_results — 3 results returned as-is
- search_movies_empty_results_list — empty results → []

## Mocking pattern
Uses `patch.object(tvmeta, "_get_json", return_value=...)` to avoid real HTTP calls.
Store uses `Store(":memory:")` with full schema bootstrapped on same connection.
