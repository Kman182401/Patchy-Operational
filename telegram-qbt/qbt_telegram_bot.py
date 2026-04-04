#!/usr/bin/env python3
"""
Telegram <-> qBittorrent command center for Plex workflows.

This file is a backward-compatibility shim. The actual implementation
lives in the patchy_bot package. All public names are re-exported here
so existing tests and scripts continue to work.
"""

from patchy_bot import *  # noqa: F401,F403
from patchy_bot import (
    _ACTIVE_DL_STATES,
    _JsonFormatter,
    _PM,
    _h,
    _relative_time,
    BotApp,
    Config,
    PatchyLLMClient,
    PlexInventoryClient,
    QBClient,
    RateLimiter,
    REMOVE_MEDIA_FILE_EXTENSIONS,
    Store,
    TVMetadataClient,
    build_requests_session,
    discover_openai_compatible_provider,
    episode_code,
    episode_number_from_code,
    exception_tuple,
    extract_episode_codes,
    extract_episode_number,
    extract_season_number,
    format_local_ts,
    format_remove_episode_label,
    format_remove_season_label,
    human_size,
    is_remove_media_file,
    normalize_title,
    now_ts,
    parse_bool,
    parse_env_optional,
    parse_env_text,
    parse_release_ts,
    parse_size_to_bytes,
    quality_tier,
    remove_tv_item_sort_key,
    strip_summary_html,
)
from patchy_bot.__main__ import main

if __name__ == "__main__":
    main()
