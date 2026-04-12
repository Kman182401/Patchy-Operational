# API Clients

> Generated from `patchy_bot/clients/` on 2026-04-11. All clients use `build_requests_session()` for retry/backoff.

---

## QBClient

**File:** `clients/qbittorrent.py` (287 lines)
**Wraps:** qBittorrent WebUI API v2
**Thread safety:** `threading.Lock()` — all requests serialized through `_request()`

### Authentication
- Auto-login on first request
- Auto-reauth on HTTP 403 (session expired) — transparent retry

### Key Methods

| Method | API Endpoint | Purpose |
|--------|-------------|---------|
| `search(query, ...)` | `/api/v2/search/*` | Blocking search with early-exit (designed for `asyncio.to_thread()`) |
| `add_url(url, ...)` | `/api/v2/torrents/add` | Add torrent by magnet/URL |
| `get_torrent(hash)` | `/api/v2/torrents/info` | Get single torrent info |
| `delete_torrent(hash)` | `/api/v2/torrents/delete` | Delete torrent + files |
| `pause_torrents(hashes)` | `/api/v2/torrents/pause` | Pause one or more torrents |
| `resume_torrents(hashes)` | `/api/v2/torrents/resume` | Resume one or more torrents |
| `get_torrent_files(hash)` | `/api/v2/torrents/files` | List files inside a torrent |
| `list_torrents(...)` | `/api/v2/torrents/info` | List torrents with filters |
| `get_transfer_info()` | `/api/v2/transfer/info` | Connection status, DHT nodes |
| `get_preferences()` | `/api/v2/app/preferences` | Read qBT preferences |
| `set_preferences(prefs)` | `/api/v2/app/setPreferences` | Write qBT preferences |
| `ensure_category(name, path)` | `/api/v2/torrents/*Category` | Create/update download category |
| `list_search_plugins()` | `/api/v2/search/plugins` | List installed search plugins |
| `get_torrent_trackers(hash)` | `/api/v2/torrents/trackers` | Get tracker list |
| `reannounce_torrent(hash)` | `/api/v2/torrents/reannounce` | Force tracker reannounce |

### Constraints
- Never set `current_network_interface` to VPN interface — breaks libtorrent DNS
- Search uses `time.sleep()` polling — must be called via `asyncio.to_thread()`

---

## PlexInventoryClient

**File:** `clients/plex.py` (409 lines)
**Wraps:** Plex Media Server XML API
**Thread safety:** Not thread-locked — designed for single-threaded async use

### Authentication
- `X-Plex-Token` header on every request
- `ready()` check — returns False if base_url or token missing

### Key Methods

| Method | Purpose |
|--------|---------|
| `episode_inventory(show_name, year)` | Get set of episode codes (`S01E05`) for a show in Plex |
| `movie_exists(title, year)` | Check if Plex already has a movie |
| `refresh_for_path(path)` | Trigger Plex library scan for a specific path |
| `purge_deleted_path(path)` | Scan + empty trash for a deleted path |
| `refresh_all_by_type(types)` | Refresh all sections of given type(s) |
| `resolve_remove_identity(path, kind)` | Find Plex metadata for a path (for removal verification) |
| `verify_remove_identity_absent(...)` | Confirm Plex metadata was cleaned up after deletion |

### Patterns
- XML parsing via `xml.etree.ElementTree`
- Section discovery via `/library/sections` with path matching
- Title matching uses `normalize_title()` from utils
- Wait-for-idle polling during trash operations

---

## TVMetadataClient

**File:** `clients/tv_metadata.py` (339 lines)
**Wraps:** TVMaze API (TV shows) + TMDB API (movies + release dates)
**Thread safety:** No locking needed — stateless HTTP client

### Key Methods

| Method | API | Purpose |
|--------|-----|---------|
| `search_shows(query, limit)` | TVMaze | Search for TV shows |
| `get_show_bundle(show_id)` | TVMaze | Full show + all episodes (with specials) |
| `search_movies(query, page)` | TMDB | Search for movies |
| `get_movie_release_dates(tmdb_id, region)` | TMDB | Raw release dates by type |
| `get_movie_home_release(tmdb_id, region)` | TMDB | Structured release status with home availability |
| `get_movie_release_status(tmdb_id, region)` | TMDB | Alias for `get_movie_home_release` |

### Data Structures
- `MovieReleaseStatus` enum: `PRE_THEATRICAL`, `IN_THEATERS`, `WAITING_HOME`, `HOME_AVAILABLE`, `UNKNOWN`
- `MovieReleaseDates` frozen dataclass: all release timestamps + computed status
- Show bundle includes `available_seasons`, parsed episodes with `air_ts`

### Patterns
- TMDB fallback: if no digital/physical/TV date, estimates digital = theatrical + 45 days
- Movie query normalization: strips punctuation, lowercases for retry

---

## PatchyLLMClient

**File:** `clients/llm.py` (111 lines)
**Wraps:** OpenAI-compatible chat completions API
**Thread safety:** No locking — stateless per-request

### Authentication
- Bearer token via `Authorization` header

### Key Methods

| Method | Purpose |
|--------|---------|
| `chat(messages, model, fallback_model, max_tokens, temperature)` | Send chat completion, returns `(content, model_used)` |
| `ready()` | Check if base_url and api_key are configured |

### Patterns
- Model fallback chain: tries primary model first, then fallback
- Unsupported model caching: marks models that return 400/404 with "model not supported"
- Content extraction handles both string and list content formats
- Auto-discovers OpenAI-compatible provider if env vars not set
