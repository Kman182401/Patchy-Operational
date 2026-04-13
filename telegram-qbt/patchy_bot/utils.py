"""Pure utility functions and constants used across the bot."""

from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

_PM = "HTML"

_ACTIVE_DL_STATES = {
    "downloading", "forcedDL", "stalledDL",
    "metaDL", "forcedMetaDL",
    "queuedDL", "checkingDL",
    "moving", "checkingResumeData",
}


def _h(text: Any) -> str:
    """Escape user-provided text for safe HTML parse_mode rendering."""
    return html.escape(str(text))


def now_ts() -> int:
    return int(time.time())


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_env_text(value: str | None, default: str = "") -> str:
    if value is None:
        return default
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1]
    return cleaned or default


def parse_env_optional(value: str | None) -> str | None:
    cleaned = parse_env_text(value, "")
    return cleaned or None


def build_requests_session(
    user_agent: str,
    *,
    retries: int = 3,
    backoff_factor: float = 0.6,
    pool_connections: int = 8,
    pool_maxsize: int = 8,
) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS", "POST"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def exception_tuple(err: BaseException) -> tuple[type[BaseException], BaseException, Any]:
    return (type(err), err, err.__traceback__)


def parse_size_to_bytes(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip().upper().replace(" ", "")
    if not raw:
        return None

    units = {
        "B": 1,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
    }

    for unit in sorted(units.keys(), key=len, reverse=True):
        if raw.endswith(unit):
            num = float(raw[: -len(unit)])
            return int(num * units[unit])

    return int(float(raw))


def human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    units = ["KiB", "MiB", "GiB", "TiB", "PiB"]
    val = float(size_bytes)
    for unit in units:
        val /= 1024.0
        if val < 1024:
            return f"{val:.2f} {unit}"
    return f"{val:.2f} EiB"


def quality_tier(name: str) -> int:
    n = name.lower()
    if "2160" in n or "4k" in n or "uhd" in n:
        return 2160
    if "1080" in n:
        return 1080
    if "720" in n:
        return 720
    if "480" in n:
        return 480
    return 0


def discover_openai_compatible_provider() -> tuple[str | None, str | None]:
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return None, None

    providers = cfg.get("models", {}).get("providers", {})
    if not isinstance(providers, dict):
        return None, None

    # Prefer explicitly configured provider first (if present).
    preferred = str(os.getenv("PATCHY_LLM_PROVIDER", "")).strip()
    ordered_keys: list[str] = []
    if preferred and preferred in providers:
        ordered_keys.append(preferred)
    ordered_keys.extend(k for k in providers.keys() if k not in ordered_keys)

    for key in ordered_keys:
        p = providers.get(key) or {}
        if not isinstance(p, dict):
            continue
        base_url = str(p.get("baseUrl") or "").strip()
        api_key = str(p.get("apiKey") or "").strip()
        api_kind = str(p.get("api") or "").strip().lower()
        if not base_url or not api_key:
            continue
        if api_kind and "openai" not in api_kind:
            continue
        return base_url.rstrip("/"), api_key

    return None, None


def normalize_title(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", value or "")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned.lower())
    cleaned = re.sub(r"\b(the|a|an)\b", " ", cleaned)
    return " ".join(cleaned.split())


def strip_summary_html(value: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return " ".join(text.split())


def episode_code(season: int, episode: int) -> str:
    return f"S{season:02d}E{episode:02d}"


def episode_number_from_code(code: str) -> int | None:
    m = re.fullmatch(r"[sS](\d{1,2})[eE](\d{1,2})", str(code or "").strip())
    if not m:
        return None
    try:
        return int(m.group(2))
    except Exception:
        return None


def extract_episode_codes(text: str) -> set[str]:
    out: set[str] = set()
    raw = text or ""
    for season_txt, episode_txt in re.findall(r"[Ss](\d{1,2})[ ._-]?[Ee](\d{1,2})", raw):
        out.add(episode_code(int(season_txt), int(episode_txt)))
    for season_txt, episode_txt in re.findall(r"\b(\d{1,2})x(\d{1,2})\b", raw, flags=re.I):
        out.add(episode_code(int(season_txt), int(episode_txt)))
    return out


def extract_season_number(text: str) -> int | None:
    raw = str(text or "")
    patterns = (
        r"\bseason[\s._-]*(\d{1,2})\b",
        r"\b[sS](\d{1,2})(?!\d*[eE]\d{1,2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
    return None


def extract_episode_number(text: str) -> int | None:
    raw = str(text or "")
    patterns = (
        r"\bepisode[\s._-]*(\d{1,3})\b",
        r"\bep[\s._-]*(\d{1,3})\b",
        r"\be[\s._-]*(\d{1,3})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
    return None


def format_remove_season_label(name: str) -> str:
    season = extract_season_number(name)
    if season is None:
        return str(name or "Season")
    return f"Season {season}"


def format_remove_episode_label(name: str, season: int | None = None) -> str:
    codes = sorted(extract_episode_codes(name))
    if codes:
        code = codes[0]
        match = re.fullmatch(r"[sS](\d{1,2})[eE](\d{1,2})", code)
        if match:
            return f"S{int(match.group(1))} Episode {int(match.group(2))}"
    episode = extract_episode_number(name)
    if episode is None:
        return str(name or "Episode")
    if season is not None:
        return f"S{season} Episode {episode}"
    return f"Episode {episode}"


REMOVE_MEDIA_FILE_EXTENSIONS = frozenset(
    {
        ".3gp",
        ".asf",
        ".avi",
        ".divx",
        ".flv",
        ".m2ts",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".mts",
        ".mxf",
        ".ogm",
        ".ogv",
        ".rm",
        ".rmvb",
        ".ts",
        ".vob",
        ".webm",
        ".wmv",
    }
)


def is_remove_media_file(name: str) -> bool:
    return os.path.splitext(str(name or ""))[1].lower() in REMOVE_MEDIA_FILE_EXTENSIONS


def remove_tv_item_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    kind = str(item.get("remove_kind") or "").strip().lower()
    source_name = str(item.get("source_name") or item.get("name") or "")
    name_key = str(item.get("name") or source_name).lower()
    if kind == "season":
        season_number = int(item.get("season_number") or 0) or extract_season_number(source_name) or 9999
        return (0, season_number, 0, name_key)
    if kind == "episode":
        codes = sorted(extract_episode_codes(source_name))
        if codes:
            match = re.fullmatch(r"[sS](\d{1,2})[eE](\d{1,2})", codes[0])
            if match:
                return (1, int(match.group(1)), int(match.group(2)), name_key)
        episode_number = extract_episode_number(source_name) or 9999
        season_number = int(item.get("season_number") or 0) or extract_season_number(source_name) or 9999
        return (1, season_number, episode_number, name_key)
    return (2, 9999, 9999, name_key)


def parse_release_ts(airstamp: str | None, airdate: str | None) -> int | None:
    if airstamp:
        try:
            return int(datetime.fromisoformat(airstamp.replace("Z", "+00:00")).timestamp())
        except Exception:
            pass
    if airdate:
        try:
            dt = datetime.strptime(airdate, "%Y-%m-%d").replace(tzinfo=UTC) + timedelta(hours=23, minutes=59)
            return int(dt.timestamp())
        except Exception:
            pass
    return None


def format_local_ts(ts: int | None) -> str:
    if ts is None:
        return "TBD"
    return datetime.fromtimestamp(int(ts), tz=UTC).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _relative_time(ts: int | None, *, from_ts: int | None = None) -> str:
    """Return a human-readable relative time string: 'in 3h', '2d ago', 'just now', 'TBD'."""
    if ts is None:
        return "TBD"
    reference = from_ts if from_ts is not None else now_ts()
    delta = int(ts) - reference
    abs_delta = abs(delta)
    future = delta > 0
    if abs_delta < 60:
        return "just now"
    elif abs_delta < 3600:
        label = f"{abs_delta // 60}m"
    elif abs_delta < 86400:
        label = f"{abs_delta // 3600}h"
    elif abs_delta < 7 * 86400:
        label = f"{abs_delta // 86400}d"
    else:
        return format_local_ts(int(ts))
    return f"in {label}" if future else f"{label} ago"

