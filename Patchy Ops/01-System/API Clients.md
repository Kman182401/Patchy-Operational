---
tags:
  - system/clients
aliases:
  - External Clients
created: 2026-04-11
updated: 2026-04-11
---

# API Clients

## Overview

Patchy Bot does not do everything by itself. It talks to four outside services to get its job done.

Each one has a small "client" file inside `telegram-qbt/patchy_bot/clients/` whose only job is to translate Patchy's questions into the right web requests and translate the answers back into Python objects the rest of the bot can use.

An API (Application Programming Interface) is just a set of agreed-upon URLs and message formats that two programs use to talk to each other — like a drive-thru window: you place a structured order, and you get a structured answer back.

**1. TVMaze + TMDB → `TVMetadataClient` (`clients/tv_metadata.py`)**

This is the bot's encyclopedia. TVMaze (a free TV show database) is asked things like "find a show called The Bear" or "give me every episode of season 3."

TMDB (The Movie Database, also free with a key) is asked about movies and especially about release dates — when did Dune 2 come out in theaters, when does it hit digital, when does the Blu-ray ship?

Patchy combines both because TVMaze has the best TV episode data and TMDB has the best movie data. Think of it as keeping two reference books on the same shelf.

**2. qBittorrent → `QBClient` (`clients/qbittorrent.py`)**

qBittorrent is the program that actually downloads torrents. It runs as its own service on the same machine and exposes a small web API.

`QBClient` is how Patchy says things like "log me in," "search for this movie on your installed plugins," "add this torrent and label it with the right category," "tell me the progress of all active downloads," "pause this one," and "delete that one and remove its files."

It is thread-safe — only one Python thread can talk to qBittorrent at a time, which prevents two requests stepping on each other.

**3. Plex → `PlexInventoryClient` (`clients/plex.py`)**

Plex is the streaming server that plays the finished files on your TV. Patchy never streams through Plex, but it does need to ask Plex two questions: "do you already have this episode/movie?" (so it doesn't download duplicates) and "please rescan this folder, I just added/removed something."

Plex's API speaks XML (eXtensible Markup Language — like HTML but for data), so this client parses XML responses into Python dictionaries. Patchy reaches Plex over the local network (sometimes through Tailscale, a private mesh VPN, when away from home).

**4. OpenAI-compatible LLM → `PatchyLLMClient` (`clients/llm.py`)**

This is the chatty pirate brain. It points at any chat-completions endpoint that follows OpenAI's API shape (so the actual provider can be swapped without changing code).

Patchy uses it for free-form chat with the user — answering questions, joking around in character. If the configured model isn't available, it falls back to a second model and remembers any models that have already failed so it doesn't retry them in the same session.

> [!code]- Claude Code Reference
>
> ### `clients/qbittorrent.py` — `QBClient`
> - **Base URL:** `cfg.qbt_base_url` (e.g. `http://127.0.0.1:8080`)
> - **Auth:** username/password POST to `/api/v2/auth/login`, session cookie reused
> - **Retry:** built into `build_requests_session()` (`utils.py`); per-call `retry_auth=True` re-logs in once on 403
> - **Thread safety:** `threading.Lock()` wraps every `_request`; never held across awaits
> - **Endpoints used:**
>   - `/api/v2/auth/login`
>   - `/api/v2/search/start`, `/results`, `/delete`
>   - `/api/v2/torrents/add`, `/info`, `/files`, `/trackers`, `/delete`, `/pause`, `/resume`, `/reannounce`
>   - `/api/v2/torrents/categories`, `/createCategory`, `/editCategory`
>   - `/api/v2/transfer/info`
>   - `/api/v2/app/preferences`, `/setPreferences`
>   - `/api/v2/search/plugins`
> - **Methods (signatures):**
>   ```
>   __init__(base_url, username, password)
>   _login()
>   _request(method, path, *, retry_auth=True, **kwargs) -> requests.Response
>   search(query, *, plugins='enabled', category='all', limit=50, ...)
>   add_url(url, *, category=None, savepath=None, paused=False, ...)
>   list_categories() -> dict[str, dict[str, Any]]
>   create_category(name, save_path=None) -> str
>   edit_category(name, save_path) -> str
>   ensure_category(name, save_path)
>   list_active(limit=10) -> list[dict]
>   get_transfer_info() -> dict
>   get_preferences() -> dict
>   set_preferences(prefs: dict)
>   get_torrent(torrent_hash) -> dict | None
>   delete_torrent(torrent_hash, *, delete_files=True)
>   pause_torrents(hashes)
>   resume_torrents(hashes)
>   get_torrent_files(torrent_hash) -> list[dict]
>   list_torrents(...) -> list[dict]
>   list_search_plugins() -> list[dict]
>   get_torrent_trackers(torrent_hash) -> list[dict]
>   reannounce_torrent(torrent_hash)
>   ```
>
> ### `clients/plex.py` — `PlexInventoryClient`
> - **Base URL:** `cfg.plex_base_url`; **token:** `cfg.plex_token` sent as `X-Plex-Token` header
> - **Format:** XML responses parsed with `xml.etree.ElementTree`
> - **Timeout:** 12 s default
> - **Endpoints used:**
>   - `/library/sections`
>   - `/library/sections/{key}/all`, `/refresh`
>   - `/library/metadata/{rating_key}`
> - **Methods:**
>   ```
>   __init__(base_url, token, tv_root, timeout_s=12)
>   ready() -> bool
>   _request(method, path, *, params=None) -> requests.Response
>   _get_xml(path, *, params=None) -> ET.Element
>   episode_inventory(show_name, year=None) -> tuple[set[str], str]   # returns (S01E02 codes, section_key)
>   movie_exists(title, year=None) -> bool
>   resolve_remove_identity(media_path, remove_kind) -> dict
>   refresh_for_path(media_path) -> str
>   purge_deleted_path(media_path) -> str   # used by remove flow + organizer ghost cleanup
>   refresh_all_by_type(section_types) -> list[str]
>   verify_remove_identity_absent(target_path, remove_kind, verification) -> tuple[bool, str]
>   _wait_for_section_idle(section_key, *, timeout_s=45, poll_s=1.0, min_wait_s=3.0) -> bool
>   ```
> - **Notes:** path containment uses `PurePosixPath.is_relative_to`; never `str.startswith`.
>
> ### `clients/tv_metadata.py` — `TVMetadataClient`
> - **TVMaze base:** `https://api.tvmaze.com` (no auth)
> - **TMDB base:** `https://api.themoviedb.org/3` with `cfg.tmdb_api_key`
> - **Timeout:** 15 s default
> - **Helpers exported:** `MovieReleaseStatus` (Enum), `MovieReleaseDates` (dataclass)
> - **Methods:**
>   ```
>   __init__(tmdb_api_key, timeout_s=15)
>   _get_json(url, *, params=None) -> Any
>   _show_card(show: dict) -> dict
>   search_shows(query, limit=5) -> list[dict]
>   _lookup_tmdb_id(name, year) -> int | None
>   get_show_bundle(show_id, *, lookup_tmdb=False) -> dict
>   search_movies(query, page=1) -> list[dict]
>   _normalize_movie_query(query) -> str
>   get_movie_release_dates(tmdb_id, region) -> dict[str, int]
>   get_movie_home_release(tmdb_id, region) -> MovieReleaseDates
>   get_movie_release_status(tmdb_id, region) -> MovieReleaseDates
>   ```
> - **Caching:** `get_show_bundle` results are persisted in `schedule_show_cache` table for 8 h.
>
> ### `clients/llm.py` — `PatchyLLMClient`
> - **Base URL:** `cfg.patchy_llm_base_url` (any OpenAI-compatible endpoint, e.g. `https://api.openai.com/v1` or a self-hosted gateway)
> - **Auth:** `Authorization: Bearer <api_key>`
> - **Endpoint hit:** `POST {base_url}/chat/completions`
> - **Timeout:** 35 s default
> - **Failure handling:** falls back from `model` → `fallback_model`, caches `_unsupported_models` to avoid retrying broken models in the same process
> - **Methods:**
>   ```
>   __init__(base_url, api_key, timeout_s=35)
>   ready() -> bool
>   _extract_content(data) -> str   # tolerates string OR list-of-parts content
>   chat(*, messages, model, fallback_model, max_tokens, temperature) -> tuple[str, str]
>   ```
> - **All four clients use `build_requests_session()` from `utils.py`, which configures pooled HTTP connections plus exponential-backoff retry on 5xx and connection errors.**
