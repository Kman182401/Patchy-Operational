"""Bot configuration loaded from environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .utils import discover_openai_compatible_provider, parse_bool, parse_env_optional, parse_env_text


@dataclass
class Config:
    telegram_token: str
    allowed_user_ids: set[int]
    allow_group_chats: bool
    access_password: str
    access_session_ttl_s: int
    vpn_required_for_downloads: bool
    vpn_service_name: str
    vpn_interface_name: str
    qbt_base_url: str
    qbt_username: str | None
    qbt_password: str | None
    tmdb_api_key: str | None
    plex_base_url: str | None
    plex_token: str | None
    db_path: str
    page_size: int
    search_timeout_s: int
    poll_interval_s: float
    search_early_exit_min_results: int
    search_early_exit_idle_s: float
    search_early_exit_max_wait_s: float
    default_limit: int
    default_sort: str
    default_order: str
    default_min_quality: int
    default_min_seeds: int
    movies_category: str
    tv_category: str
    spam_category: str
    movies_path: str
    tv_path: str
    spam_path: str
    nvme_mount_path: str
    require_nvme_mount: bool
    patchy_chat_enabled: bool
    patchy_chat_name: str
    patchy_chat_model: str
    patchy_chat_fallback_model: str
    patchy_chat_timeout_s: int
    patchy_chat_max_tokens: int
    patchy_chat_temperature: float
    patchy_chat_history_turns: int
    patchy_llm_base_url: str | None
    patchy_llm_api_key: str | None
    progress_refresh_s: float
    progress_edit_min_s: float
    progress_smoothing_alpha: float
    progress_track_timeout_s: int
    backup_dir: str | None

    _DANGEROUS_ROOTS: frozenset[str] = frozenset(
        {
            "/",
            "/bin",
            "/boot",
            "/dev",
            "/etc",
            "/home",
            "/lib",
            "/lib64",
            "/opt",
            "/proc",
            "/root",
            "/run",
            "/sbin",
            "/srv",
            "/sys",
            "/tmp",
            "/usr",
            "/var",
        }
    )

    _SAFE_IFACE_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_-]+$")

    def __post_init__(self) -> None:
        if self.vpn_interface_name and not self._SAFE_IFACE_RE.match(self.vpn_interface_name):
            raise RuntimeError(
                f"Refusing to start: VPN_INTERFACE_NAME={self.vpn_interface_name!r} contains invalid characters. "
                "Only alphanumeric, underscore, and hyphen are allowed."
            )
        for attr in ("movies_path", "tv_path", "spam_path"):
            raw = getattr(self, attr, "")
            resolved = os.path.realpath(raw) if raw else ""
            if resolved in self._DANGEROUS_ROOTS:
                raise RuntimeError(
                    f"Refusing to start: {attr}={raw!r} resolves to system-critical directory {resolved!r}. "
                    "Set it to a dedicated media directory instead."
                )

    @staticmethod
    def from_env() -> Config:
        token = parse_env_text(os.getenv("TELEGRAM_BOT_TOKEN"), "")
        if not token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

        allowed_raw = parse_env_text(os.getenv("ALLOWED_TELEGRAM_USER_IDS"), "")
        allowed: set[int] = set()
        if allowed_raw:
            for x in allowed_raw.split(","):
                x = x.strip()
                if x:
                    allowed.add(int(x))

        min_q = int(os.getenv("DEFAULT_MIN_QUALITY", "1080"))
        if min_q not in {0, 480, 720, 1080, 2160}:
            min_q = 1080

        chat_enabled = parse_bool(os.getenv("PATCHY_CHAT_ENABLED", "true"), default=True)
        llm_base_url = parse_env_optional(os.getenv("PATCHY_LLM_BASE_URL"))
        llm_api_key = parse_env_optional(os.getenv("PATCHY_LLM_API_KEY"))
        if chat_enabled and (not llm_base_url or not llm_api_key):
            auto_base, auto_key = discover_openai_compatible_provider()
            llm_base_url = llm_base_url or auto_base
            llm_api_key = llm_api_key or auto_key

        return Config(
            telegram_token=token,
            allowed_user_ids=allowed,
            allow_group_chats=parse_bool(os.getenv("ALLOW_GROUP_CHATS", "false"), default=False),
            access_password=parse_env_text(os.getenv("BOT_ACCESS_PASSWORD"), ""),
            access_session_ttl_s=int(os.getenv("ACCESS_SESSION_TTL_SECONDS", "0")),
            vpn_required_for_downloads=parse_bool(os.getenv("REQUIRE_VPN_FOR_DOWNLOADS", "true"), default=True),
            vpn_service_name=parse_env_text(os.getenv("VPN_SERVICE_NAME"), "surfshark-vpn.service"),
            vpn_interface_name=parse_env_text(os.getenv("VPN_INTERFACE_NAME"), "tun0"),
            qbt_base_url=parse_env_text(os.getenv("QBT_BASE_URL"), "http://127.0.0.1:8080").rstrip("/"),
            qbt_username=parse_env_optional(os.getenv("QBT_USERNAME")),
            qbt_password=parse_env_optional(os.getenv("QBT_PASSWORD")),
            tmdb_api_key=parse_env_optional(os.getenv("TMDB_API_KEY")),
            plex_base_url=(parse_env_optional(os.getenv("PLEX_BASE_URL")) or "").rstrip("/") or None,
            plex_token=parse_env_optional(os.getenv("PLEX_TOKEN")),
            db_path=parse_env_text(os.getenv("DB_PATH"), "./state.sqlite3"),
            page_size=max(3, int(os.getenv("RESULT_PAGE_SIZE", "5"))),
            search_timeout_s=max(10, int(os.getenv("SEARCH_TIMEOUT_SECONDS", "45"))),
            poll_interval_s=max(0.4, float(os.getenv("POLL_INTERVAL_SECONDS", "0.6"))),
            search_early_exit_min_results=max(0, int(os.getenv("SEARCH_EARLY_EXIT_MIN_RESULTS", "20"))),
            search_early_exit_idle_s=max(1.0, float(os.getenv("SEARCH_EARLY_EXIT_IDLE_SECONDS", "2.5"))),
            search_early_exit_max_wait_s=max(2.0, float(os.getenv("SEARCH_EARLY_EXIT_MAX_WAIT_SECONDS", "12.0"))),
            default_limit=max(1, min(50, int(os.getenv("DEFAULT_RESULT_LIMIT", "10")))),
            default_sort=parse_env_text(os.getenv("DEFAULT_SORT"), "quality").lower(),
            default_order=parse_env_text(os.getenv("DEFAULT_ORDER"), "desc").lower(),
            default_min_quality=min_q,
            default_min_seeds=max(0, int(os.getenv("DEFAULT_MIN_SEEDS", "5"))),
            movies_category=parse_env_text(os.getenv("MOVIES_CATEGORY"), "Movies"),
            tv_category=parse_env_text(os.getenv("TV_CATEGORY"), "TV"),
            spam_category=parse_env_text(os.getenv("SPAM_CATEGORY"), "Spam"),
            movies_path=parse_env_text(os.getenv("MOVIES_PATH"), "/mnt/nvme/Movies"),
            tv_path=parse_env_text(os.getenv("TV_PATH"), "/mnt/nvme/TV"),
            spam_path=parse_env_text(os.getenv("SPAM_PATH"), os.path.expanduser("~/Downloads/Spam")),
            nvme_mount_path=parse_env_text(os.getenv("NVME_MOUNT_PATH"), "/mnt/nvme"),
            require_nvme_mount=parse_bool(os.getenv("REQUIRE_NVME_MOUNT", "true"), default=True),
            patchy_chat_enabled=chat_enabled,
            patchy_chat_name=parse_env_text(os.getenv("PATCHY_CHAT_NAME"), "Patchy"),
            patchy_chat_model=parse_env_text(os.getenv("PATCHY_CHAT_MODEL"), "gpt-5-chat-latest"),
            patchy_chat_fallback_model=parse_env_text(os.getenv("PATCHY_CHAT_FALLBACK_MODEL"), "gpt-4.1-mini"),
            patchy_chat_timeout_s=max(8, int(os.getenv("PATCHY_CHAT_TIMEOUT_SECONDS", "35"))),
            patchy_chat_max_tokens=max(80, int(os.getenv("PATCHY_CHAT_MAX_TOKENS", "500"))),
            patchy_chat_temperature=max(0.0, min(1.2, float(os.getenv("PATCHY_CHAT_TEMPERATURE", "0.2")))),
            patchy_chat_history_turns=max(1, min(12, int(os.getenv("PATCHY_CHAT_HISTORY_TURNS", "6")))),
            patchy_llm_base_url=llm_base_url,
            patchy_llm_api_key=llm_api_key,
            progress_refresh_s=max(0.6, float(os.getenv("PROGRESS_REFRESH_SECONDS", "1.0"))),
            progress_edit_min_s=max(0.5, float(os.getenv("PROGRESS_EDIT_MIN_SECONDS", "0.9"))),
            progress_smoothing_alpha=min(1.0, max(0.05, float(os.getenv("PROGRESS_SMOOTHING_ALPHA", "0.35")))),
            progress_track_timeout_s=max(60, int(os.getenv("PROGRESS_TRACK_TIMEOUT_SECONDS", "1800"))),
            backup_dir=parse_env_optional(os.getenv("BACKUP_DIR")),
        )
