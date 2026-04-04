"""
Patchy Bot — Telegram <-> qBittorrent command center for Plex workflows.

This package provides the modular implementation. Import individual modules
or use the top-level re-exports for backward compatibility.
"""

from .clients.llm import PatchyLLMClient
from .clients.plex import PlexInventoryClient
from .clients.qbittorrent import QBClient
from .clients.tv_metadata import TVMetadataClient
from .config import Config
from .bot import BotApp
from .logging_config import _JsonFormatter
from .rate_limiter import RateLimiter
from .store import Store
from .utils import (
    _ACTIVE_DL_STATES,
    _PM,
    REMOVE_MEDIA_FILE_EXTENSIONS,
    _h,
    _relative_time,
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

__all__ = [
    "BotApp",
    "Config",
    "PatchyLLMClient",
    "PlexInventoryClient",
    "QBClient",
    "RateLimiter",
    "Store",
    "TVMetadataClient",
    "_JsonFormatter",
]
