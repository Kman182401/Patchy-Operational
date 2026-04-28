# Community 14 — TMDB Metadata

**63 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `TestTMDBMovieMethods` | `telegram-qbt/tests/test_movie_schedule.py:L162` | 21 |
| `.search_movies()` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L191` | 15 |
| `_show_card()` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L65` | 9 |
| `.get_show_bundle()` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L140` | 9 |
| `.get_movie_release_dates()` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L241` | 9 |
| `TestShowCardImageUrl` | `telegram-qbt/tests/test_poster_urls.py:L27` | 9 |
| `TestPosterAllowedHosts` | `telegram-qbt/tests/test_poster_urls.py:L158` | 9 |
| `._make_show()` | `telegram-qbt/tests/test_poster_urls.py:L28` | 7 |
| `TestSearchMoviesPosterUrl` | `telegram-qbt/tests/test_poster_urls.py:L124` | 7 |
| `._get_json()` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L52` | 6 |
| `._get_allowlist()` | `telegram-qbt/tests/test_poster_urls.py:L161` | 6 |
| `test_poster_urls.py` | `telegram-qbt/tests/test_poster_urls.py:L1` | 5 |
| `parse_release_ts()` | `telegram-qbt/patchy_bot/utils.py:L316` | 4 |
| `._lookup_tmdb_id()` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L108` | 4 |
| `.test_show_card_extracts_image_url()` | `telegram-qbt/tests/test_poster_urls.py:L41` | 4 |

## Connected Communities

- [[Community 0 — Core Types & Clients]] (45 edges)
- [[Community 1 — BotApp & Command Flow]] (25 edges)
- [[Community 4 — Parsing & Utilities]] (4 edges)
- [[Community 6 — Movie Scheduling]] (2 edges)

## All Nodes (63)

- `TestTMDBMovieMethods` — `telegram-qbt/tests/test_movie_schedule.py` (21)
- `.search_movies()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (15)
- `_show_card()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (9)
- `.get_show_bundle()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (9)
- `.get_movie_release_dates()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (9)
- `TestShowCardImageUrl` — `telegram-qbt/tests/test_poster_urls.py` (9)
- `TestPosterAllowedHosts` — `telegram-qbt/tests/test_poster_urls.py` (9)
- `._make_show()` — `telegram-qbt/tests/test_poster_urls.py` (7)
- `TestSearchMoviesPosterUrl` — `telegram-qbt/tests/test_poster_urls.py` (7)
- `._get_json()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (6)
- `._get_allowlist()` — `telegram-qbt/tests/test_poster_urls.py` (6)
- `test_poster_urls.py` — `telegram-qbt/tests/test_poster_urls.py` (5)
- `parse_release_ts()` — `telegram-qbt/patchy_bot/utils.py` (4)
- `._lookup_tmdb_id()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (4)
- `.test_show_card_extracts_image_url()` — `telegram-qbt/tests/test_poster_urls.py` (4)
- `.test_show_card_image_url_none_when_image_null()` — `telegram-qbt/tests/test_poster_urls.py` (4)
- `.test_show_card_image_url_none_when_image_missing()` — `telegram-qbt/tests/test_poster_urls.py` (4)
- `.test_show_card_image_url_none_when_medium_missing()` — `telegram-qbt/tests/test_poster_urls.py` (4)
- `.test_show_card_image_url_none_when_medium_empty()` — `telegram-qbt/tests/test_poster_urls.py` (4)
- `.test_search_movies_no_api_key_returns_empty()` — `telegram-qbt/tests/test_poster_urls.py` (4)
- `.search_shows()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (3)
- `tvmeta()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_search_movies_extracts_poster_url()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_search_movies_poster_url_none_when_poster_path_null()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_search_movies_poster_url_none_when_poster_path_empty()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_tvmaze_hostname_is_allowed()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_tmdb_hostname_is_allowed()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_arbitrary_hostname_not_allowed()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_internal_ip_not_allowed()` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `Tests for poster/image URL extraction in TVMetadataClient.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `Return a TVMetadataClient with a dummy API key.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `Build a minimal TVMaze show dict.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `_show_card extracts image.medium URL when present.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `_show_card returns image_url=None when image field is null.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `_show_card returns image_url=None when image field is absent.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `_show_card returns image_url=None when image exists but medium is absent.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `_show_card returns image_url=None when medium is an empty string.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `search_movies builds full poster URL from poster_path.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `search_movies returns poster_url=None when poster_path is null.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `search_movies returns poster_url=None when poster_path is empty string.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `search_movies returns empty list when tmdb_api_key is not configured.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `Verify the hostname allowlist that guards _send_poster_photo.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `Import and return BotApp._POSTER_ALLOWED_HOSTS without instantiating BotApp.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `TVMaze CDN hostname is in the allowlist.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `TMDB image CDN hostname is in the allowlist.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `An arbitrary external hostname is not in the allowlist.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `A private IP address hostname is not in the allowlist.` — `telegram-qbt/tests/test_poster_urls.py` (3)
- `.test_search_movies_no_api_key()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `.test_get_release_dates_no_api_key()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `.test_search_movies_result_fields()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `.test_search_movies_missing_release_date_year_is_none()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `.test_get_release_dates_physical_type()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `.test_get_release_dates_unknown_type_ignored()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `.test_search_movies_fewer_than_5_results()` — `telegram-qbt/tests/test_movie_schedule.py` (3)
- `strip_summary_html()` — `telegram-qbt/patchy_bot/utils.py` (2)
- `_normalize_movie_query()` — `telegram-qbt/patchy_bot/clients/tv_metadata.py` (2)
- `.test_search_returns_upcoming_movie()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
- `.test_search_movies_returns_top5()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
- `.test_search_movies_empty_on_error()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
- `.test_get_release_dates_us()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
- `.test_get_release_dates_region_missing()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
- `.test_get_release_dates_error_returns_empty()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
- `.test_search_movies_empty_results_list()` — `telegram-qbt/tests/test_movie_schedule.py` (2)
