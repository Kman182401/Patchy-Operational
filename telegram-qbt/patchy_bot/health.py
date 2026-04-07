"""Download health checks — VPN, qBT connectivity, disk space.

Provides structured HealthResult / PreflightReport dataclasses used
by the download pipeline to gate downloads and log health events.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clients.qbittorrent import QBClient
    from .config import Config

LOG = logging.getLogger("qbtg.health")

_SAFE_IFACE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class HealthResult:
    """Result of a single health check."""

    check_name: str
    passed: bool
    severity: str  # 'ok', 'warn', 'block'
    message: str
    detail: dict = field(default_factory=dict)


@dataclass
class PreflightReport:
    """Aggregated pre-flight check results."""

    checks: list[HealthResult] = field(default_factory=list)
    can_proceed: bool = True
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def check_vpn(cfg: Config) -> HealthResult:
    """Check VPN interface status and DNS resolution."""
    if not cfg.vpn_required_for_downloads:
        return HealthResult("vpn", True, "ok", "VPN check disabled", {"skipped": True})

    iface = cfg.vpn_interface_name
    if not iface or not _SAFE_IFACE_RE.match(iface):
        return HealthResult("vpn", False, "block", f"Invalid VPN interface name: {iface!r}", {"iface": iface})

    # Check interface exists via sysfs (no subprocess needed)
    iface_dir = f"/sys/class/net/{iface}"
    if not os.path.exists(iface_dir):
        return HealthResult(
            "vpn", False, "block", f"VPN interface {iface} not found", {"iface": iface, "exists": False}
        )

    # Check interface state
    try:
        with open(f"{iface_dir}/operstate", encoding="utf-8") as f:
            state = f.read().strip().lower()
    except OSError:
        state = "unknown"

    if state == "down":
        return HealthResult("vpn", False, "block", f"VPN interface {iface} is down", {"iface": iface, "state": state})

    # Check for IP assignment
    try:
        ip_result = subprocess.run(
            ["ip", "-4", "addr", "show", "dev", iface],
            capture_output=True,
            text=True,
            timeout=5,
        )
        has_ip = "inet " in (ip_result.stdout or "")
    except Exception:
        has_ip = False

    if not has_ip:
        return HealthResult(
            "vpn",
            False,
            "warn",
            f"VPN interface {iface} has no IPv4 address",
            {"iface": iface, "state": state, "has_ip": False},
        )

    # DNS resolution check — getaddrinfo uses system resolver timeout.
    # This runs in a thread executor so it won't block the event loop.
    try:
        socket.getaddrinfo("tracker.opentrackr.org", 6969, proto=socket.IPPROTO_TCP)
        dns_ok = True
    except (socket.gaierror, OSError):
        dns_ok = False

    if not dns_ok:
        return HealthResult(
            "vpn",
            False,
            "block",
            "DNS resolution failing through VPN",
            {"iface": iface, "state": state, "has_ip": True, "dns_ok": False},
        )

    return HealthResult(
        "vpn", True, "ok", f"VPN ready ({iface} up)", {"iface": iface, "state": state, "has_ip": True, "dns_ok": True}
    )


def check_qbt_connection(qbt: QBClient) -> HealthResult:
    """Check qBittorrent connection status."""
    try:
        info = qbt.get_transfer_info()
    except Exception as e:
        return HealthResult("qbt_connection", False, "block", f"qBittorrent unreachable: {e}", {"error": str(e)})

    status = str(info.get("connection_status") or "unknown").strip().lower()
    dht_nodes = int(info.get("dht_nodes") or 0)
    detail = {"connection_status": status, "dht_nodes": dht_nodes}

    if status == "disconnected":
        return HealthResult(
            "qbt_connection", False, "block", f"qBittorrent is disconnected (dht_nodes={dht_nodes})", detail
        )

    if status == "firewalled":
        return HealthResult(
            "qbt_connection",
            True,
            "warn",
            f"qBittorrent is firewalled — downloads may be slower (dht_nodes={dht_nodes})",
            detail,
        )

    return HealthResult("qbt_connection", True, "ok", f"qBittorrent connected (dht_nodes={dht_nodes})", detail)


def check_disk_space(save_path: str, min_gb: float) -> HealthResult:
    """Check available disk space at the save path."""
    try:
        usage = shutil.disk_usage(save_path)
    except OSError as e:
        return HealthResult(
            "disk_space", True, "warn", f"Cannot check disk space: {e}", {"error": str(e), "path": save_path}
        )

    free_bytes = usage.free
    total_bytes = usage.total
    threshold_bytes = int(min_gb * (1024**3))
    warn_threshold = threshold_bytes * 2
    detail = {
        "free_bytes": free_bytes,
        "total_bytes": total_bytes,
        "threshold_bytes": threshold_bytes,
        "path": save_path,
    }

    if free_bytes < threshold_bytes:
        free_gb = free_bytes / (1024**3)
        return HealthResult(
            "disk_space",
            False,
            "block",
            f"Disk space critically low: {free_gb:.1f} GB free (need {min_gb:.1f} GB)",
            detail,
        )

    if free_bytes < warn_threshold:
        free_gb = free_bytes / (1024**3)
        return HealthResult("disk_space", True, "warn", f"Disk space getting low: {free_gb:.1f} GB free", detail)

    return HealthResult("disk_space", True, "ok", "Disk space OK", detail)


async def run_preflight(cfg: Config, qbt: QBClient, save_path: str) -> PreflightReport:
    """Run all pre-flight checks and aggregate results."""
    loop = asyncio.get_running_loop()

    vpn_result, qbt_result, disk_result = await asyncio.gather(
        loop.run_in_executor(None, check_vpn, cfg),
        loop.run_in_executor(None, check_qbt_connection, qbt),
        loop.run_in_executor(None, check_disk_space, save_path, cfg.preflight_min_disk_gb),
    )

    checks = [vpn_result, qbt_result, disk_result]
    warnings: list[str] = []
    blockers: list[str] = []

    for check in checks:
        if check.severity == "block":
            blockers.append(check.message)
        elif check.severity == "warn":
            warnings.append(check.message)

    can_proceed = len(blockers) == 0

    return PreflightReport(
        checks=checks,
        can_proceed=can_proceed,
        warnings=warnings,
        blockers=blockers,
    )
