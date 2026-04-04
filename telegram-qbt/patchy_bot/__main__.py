"""Entry point for the Patchy Bot package.

Run with: python -m patchy_bot
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from .bot import BotApp
from .config import Config
from .logging_config import _JsonFormatter

LOG = logging.getLogger("qbtg")


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text").lower()

    if log_format == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logging.root.setLevel(log_level)
        logging.root.addHandler(handler)
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    cfg = Config.from_env()
    bot = BotApp(cfg)
    bot.store.cleanup()
    bot.rate_limiter.prune_stale()

    ok = False
    reason = "unknown"
    for attempt in range(1, 11):
        ok, reason = bot._ensure_media_categories()
        if ok:
            if attempt > 1:
                LOG.info("Storage/category routing ready after %d startup retries", attempt)
            else:
                LOG.info("Storage/category routing ready")
            break
        if attempt < 10:
            time.sleep(2)

    if not ok:
        LOG.warning("Storage/category routing not ready on startup after retries: %s", reason)

    try:
        max_dl = max(1, int(os.getenv("QBT_MAX_ACTIVE_DOWNLOADS", "8")))
        max_torrents = max(1, int(os.getenv("QBT_MAX_ACTIVE_TORRENTS", "15")))
        max_ul = max(1, int(os.getenv("QBT_MAX_ACTIVE_UPLOADS", "8")))
        startup_prefs: dict[str, Any] = {
            "max_active_downloads": max_dl,
            "max_active_torrents": max_torrents,
            "max_active_uploads": max_ul,
        }
        if cfg.vpn_required_for_downloads and cfg.vpn_interface_name:
            startup_prefs["current_network_interface"] = cfg.vpn_interface_name
            LOG.info("Binding qBittorrent to VPN interface: %s", cfg.vpn_interface_name)
        bot.qbt.set_preferences(startup_prefs)
        LOG.info("qBittorrent preferences applied (%d active DL, %d active torrents, %d active UL, interface=%s)",
                 max_dl, max_torrents, max_ul, startup_prefs.get("current_network_interface", "unchanged"))
    except Exception as e:
        LOG.warning("Failed to apply qBittorrent preferences: %s", e)

    LOG.info("Starting Telegram qBittorrent command center bot")
    app = bot.build_application()
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
