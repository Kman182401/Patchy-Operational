"""Builder functions for test data objects.

Each function returns a plain dict matching the structure used by
qBittorrent API responses, Store rows, or internal data models.
All parameters have sensible defaults — override only what your test needs.
"""

from __future__ import annotations

import json
import secrets
from typing import Any


def make_torrent_info(
    *,
    name: str = "Test.Torrent.1080p.WEB-DL",
    hash: str = "",
    state: str = "downloading",
    progress: float = 0.5,
    size: int = 2_000_000_000,
    completed: int = 0,
    dlspeed: int = 5_000_000,
    upspeed: int = 500_000,
    eta: int = 300,
    seeds: int = 10,
    category: str = "TV",
    save_path: str = "/mnt/nvme/TV",
    content_path: str = "",
    amount_left: int = -1,
    added_on: int = 0,
) -> dict[str, Any]:
    """Build a torrent info dict matching qBittorrent API response shape."""
    h = hash or secrets.token_hex(20)
    return {
        "name": name,
        "hash": h,
        "state": state,
        "progress": progress,
        "size": size,
        "total_size": size,
        "completed": completed or int(size * progress),
        "downloaded": completed or int(size * progress),
        "dlspeed": dlspeed,
        "upspeed": upspeed,
        "eta": eta,
        "num_seeds": seeds,
        "category": category,
        "save_path": save_path,
        "content_path": content_path or save_path,
        "amount_left": amount_left if amount_left >= 0 else int(size * (1 - progress)),
        "added_on": added_on,
    }


def make_schedule_track(
    *,
    track_id: str = "",
    user_id: int = 12345,
    chat_id: int = 12345,
    show_name: str = "Test Show",
    season: int = 1,
    tvmaze_id: int = 1,
    tmdb_id: int | None = None,
    imdb_id: str | None = None,
    enabled: bool = True,
    pending_codes: list[str] | None = None,
    auto_state: dict[str, Any] | None = None,
    next_check_at: int = 0,
    next_air_ts: int | None = None,
    created_at: int = 1_700_000_000,
) -> dict[str, Any]:
    """Build a schedule track dict matching the schedule_tracks table shape."""
    tid = track_id or f"track-{secrets.token_hex(4)}"
    return {
        "track_id": tid,
        "user_id": user_id,
        "chat_id": chat_id,
        "created_at": created_at,
        "updated_at": created_at,
        "enabled": 1 if enabled else 0,
        "show_name": show_name,
        "year": None,
        "season": season,
        "tvmaze_id": tvmaze_id,
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "show_json": json.dumps({"name": show_name, "id": tvmaze_id}),
        "pending_json": json.dumps(pending_codes or []),
        "auto_state_json": json.dumps(auto_state or {}),
        "skipped_signature": None,
        "last_missing_signature": None,
        "last_probe_json": json.dumps({}),
        "last_probe_at": None,
        "next_check_at": next_check_at,
        "next_air_ts": next_air_ts,
    }


def make_search_result(
    *,
    name: str = "Result.1080p.WEB-DL",
    seeds: int = 50,
    leechers: int = 10,
    size: int = 2_000_000_000,
    site: str = "test_plugin",
    url: str = "",
    file_url: str = "",
    descr_link: str = "",
    hash: str = "",
) -> dict[str, Any]:
    """Build a search result dict matching the results table shape."""
    h = hash or secrets.token_hex(20)
    return {
        "name": name,
        "seeds": seeds,
        "leechers": leechers,
        "size": size,
        "site": site,
        "url": url or f"magnet:?xt=urn:btih:{h}&dn={name}",
        "file_url": file_url,
        "descr_link": descr_link,
        "hash": h,
    }
