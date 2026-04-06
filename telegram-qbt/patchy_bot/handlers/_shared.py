"""Shared utility functions used by multiple handler modules.

Canonical implementations of helpers that were previously duplicated across
bot.py, handlers/commands.py, handlers/chat.py, and handlers/download.py.
"""

from __future__ import annotations

import logging
import os
import subprocess

from ..types import HandlerContext

LOG = logging.getLogger("qbtg")


def targets(ctx: HandlerContext) -> dict[str, dict[str, str]]:
    """Return the movies/tv target dict from config."""
    return {
        "movies": {
            "category": ctx.cfg.movies_category,
            "path": ctx.cfg.movies_path,
            "label": "Movies",
            "emoji": "\U0001f3ac",
        },
        "tv": {
            "category": ctx.cfg.tv_category,
            "path": ctx.cfg.tv_path,
            "label": "TV",
            "emoji": "\U0001f4fa",
        },
    }


def norm_path(value: str | None) -> str:
    """Normalize a filesystem path for comparison."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    return os.path.normpath(raw.rstrip("/"))


def storage_status(ctx: HandlerContext) -> tuple[bool, str]:
    """Check NVMe mount + library paths."""
    if ctx.cfg.require_nvme_mount and not os.path.ismount(ctx.cfg.nvme_mount_path):
        return False, f"NVMe mount missing at {ctx.cfg.nvme_mount_path}"
    for key in ("movies", "tv"):
        t = targets(ctx)[key]
        os.makedirs(t["path"], exist_ok=True)
        if not os.path.isdir(t["path"]):
            return False, f"Library path missing: {t['path']}"
    return True, "ready"


def ensure_media_categories(ctx: HandlerContext) -> tuple[bool, str]:
    """Ensure qBittorrent categories exist for movies + tv paths."""
    ok, reason = storage_status(ctx)
    if not ok:
        return False, reason
    try:
        for t in targets(ctx).values():
            ctx.qbt.ensure_category(t["category"], t["path"])
        return True, "ready"
    except Exception as e:
        return False, f"qBittorrent category sync failed: {e}"


def qbt_transport_status(ctx: HandlerContext) -> tuple[bool, str]:
    """Check qBittorrent connection status and bound network interface."""
    info = ctx.qbt.get_transfer_info()
    prefs = ctx.qbt.get_preferences()

    status = str(info.get("connection_status") or "unknown").strip().lower()
    dht_nodes = int(info.get("dht_nodes") or 0)
    iface = str(prefs.get("current_network_interface") or "").strip()
    iface_addr = str(prefs.get("current_interface_address") or "").strip()
    bind_label = iface or "any interface"

    if iface:
        iface_dir = f"/sys/class/net/{iface}"
        if not os.path.exists(iface_dir):
            return False, f"bound interface missing: {iface}"
        try:
            with open(f"{iface_dir}/operstate", encoding="utf-8") as f:
                iface_state = f.read().strip().lower()
        except OSError:
            iface_state = "unknown"
        if iface_state == "down":
            return False, f"bound interface is down: {iface}"
        bind_label = f"{iface} ({iface_state})"

    if iface_addr:
        bind_label = f"{bind_label} @ {iface_addr}"

    summary = f"connection_status={status} via {bind_label}, dht_nodes={dht_nodes}"
    if status == "disconnected":
        return False, summary
    return True, summary


def qbt_category_aliases(ctx: HandlerContext, primary_category: str, save_path: str) -> set[str]:
    """Return all qBittorrent category names mapped to the same save path."""
    aliases: set[str] = {str(primary_category or "").strip()} if primary_category else set()
    want_path = norm_path(save_path)
    if not want_path:
        return aliases
    try:
        categories = ctx.qbt.list_categories()
    except Exception:
        LOG.warning("Failed to inspect qBittorrent category aliases", exc_info=True)
        return aliases
    for name, meta in categories.items():
        current_path = norm_path(str((meta or {}).get("savePath") or ""))
        if current_path and current_path == want_path:
            aliases.add(str(name).strip())
    return {name for name in aliases if name}


def vpn_ready_for_download(ctx: HandlerContext) -> tuple[bool, str]:
    """Check that the VPN interface is up and has an IP before allowing downloads."""
    if not ctx.cfg.vpn_required_for_downloads:
        return True, "vpn check disabled"

    service = ctx.cfg.vpn_service_name
    iface = ctx.cfg.vpn_interface_name

    # Check 1: VPN interface must exist.
    if not os.path.exists(f"/sys/class/net/{iface}"):
        return False, f"VPN interface missing: {iface}"

    # Check 2: Interface must not be down.
    try:
        with open(f"/sys/class/net/{iface}/operstate", encoding="utf-8") as f:
            state = f.read().strip().lower()
    except Exception:
        state = "unknown"
    if state == "down":
        return False, f"VPN interface is down: {iface}"

    # Check 3: Interface must have an IP address assigned.
    try:
        ip_result = subprocess.run(
            ["ip", "-4", "addr", "show", "dev", iface],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ip_result.returncode != 0 or "inet " not in (ip_result.stdout or ""):
            return False, f"VPN interface {iface} has no IPv4 address"
    except Exception as e:
        return False, f"VPN interface IP check failed: {e}"

    # Check 4 (optional): If a systemd service is configured, verify it's active.
    if service:
        svc = subprocess.run(["systemctl", "is-active", "--quiet", service], capture_output=True)
        if svc.returncode != 0:
            # Not a hard failure -- Surfshark Flatpak doesn't use systemd.
            LOG.debug("VPN systemd service %s is not active (may be managed externally)", service)

    return True, f"vpn ready ({iface} up)"
