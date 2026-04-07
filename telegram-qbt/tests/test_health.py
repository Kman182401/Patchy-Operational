"""Tests for patchy_bot.health — VPN, qBT, and disk space checks."""

from __future__ import annotations

import collections
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from patchy_bot.health import (
    check_disk_space,
    check_qbt_connection,
    check_vpn,
    run_preflight,
)

_DiskUsage = collections.namedtuple("usage", ["total", "used", "free"])


class _FakeCfg:
    """Minimal Config stand-in."""

    def __init__(
        self,
        vpn_required_for_downloads: bool = True,
        vpn_interface_name: str = "tun0",
        preflight_min_disk_gb: float = 5.0,
    ):
        self.vpn_required_for_downloads = vpn_required_for_downloads
        self.vpn_interface_name = vpn_interface_name
        self.preflight_min_disk_gb = preflight_min_disk_gb


# ---------------------------------------------------------------------------
# check_vpn
# ---------------------------------------------------------------------------


class TestCheckVpn:
    def test_disabled(self):
        r = check_vpn(_FakeCfg(vpn_required_for_downloads=False))
        assert r.passed is True
        assert r.severity == "ok"

    @patch("os.path.exists", return_value=False)
    def test_interface_missing(self, _):
        r = check_vpn(_FakeCfg())
        assert r.passed is False
        assert r.severity == "block"
        assert "not found" in r.message.lower()

    def test_interface_down(self):
        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", return_value=StringIO("down\n")),
        ):
            r = check_vpn(_FakeCfg())
        assert r.passed is False
        assert r.severity == "block"
        assert "down" in r.message.lower()

    def test_no_ip(self):
        import subprocess

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", return_value=StringIO("up\n")),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout=""),
            ),
        ):
            r = check_vpn(_FakeCfg())
        assert r.severity == "warn"
        assert "no ipv4" in r.message.lower()

    def test_dns_failure(self):
        import socket
        import subprocess

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", return_value=StringIO("up\n")),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout="inet 10.0.0.1"),
            ),
            patch(
                "patchy_bot.health.socket.getaddrinfo",
                side_effect=socket.gaierror("dns fail"),
            ),
        ):
            r = check_vpn(_FakeCfg())
        assert r.passed is False
        assert r.severity == "block"
        assert "dns" in r.message.lower()

    def test_all_ok(self):
        import subprocess

        with (
            patch("os.path.exists", return_value=True),
            patch("builtins.open", return_value=StringIO("up\n")),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess([], 0, stdout="inet 10.0.0.1"),
            ),
            patch(
                "patchy_bot.health.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("1.2.3.4", 6969))],
            ),
        ):
            r = check_vpn(_FakeCfg())
        assert r.passed is True
        assert r.severity == "ok"


# ---------------------------------------------------------------------------
# check_qbt_connection
# ---------------------------------------------------------------------------


class TestCheckQbtConnection:
    def test_connected(self):
        qbt = MagicMock()
        qbt.get_transfer_info.return_value = {"connection_status": "connected", "dht_nodes": 42}
        r = check_qbt_connection(qbt)
        assert r.passed is True
        assert r.severity == "ok"

    def test_firewalled(self):
        qbt = MagicMock()
        qbt.get_transfer_info.return_value = {"connection_status": "firewalled", "dht_nodes": 10}
        r = check_qbt_connection(qbt)
        assert r.passed is True
        assert r.severity == "warn"

    def test_disconnected(self):
        qbt = MagicMock()
        qbt.get_transfer_info.return_value = {"connection_status": "disconnected", "dht_nodes": 0}
        r = check_qbt_connection(qbt)
        assert r.passed is False
        assert r.severity == "block"

    def test_unreachable(self):
        qbt = MagicMock()
        qbt.get_transfer_info.side_effect = RuntimeError("Connection refused")
        r = check_qbt_connection(qbt)
        assert r.passed is False
        assert r.severity == "block"
        assert "unreachable" in r.message.lower()


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------


class TestCheckDiskSpace:
    @patch("shutil.disk_usage")
    def test_plenty_of_space(self, mock_usage):
        mock_usage.return_value = _DiskUsage(total=500 * 1024**3, used=100 * 1024**3, free=400 * 1024**3)
        r = check_disk_space("/mnt/data", 5.0)
        assert r.passed is True
        assert r.severity == "ok"

    @patch("shutil.disk_usage")
    def test_low_space_warning(self, mock_usage):
        # Free = 8 GB, threshold = 5 GB, warn_threshold = 10 GB → warn
        mock_usage.return_value = _DiskUsage(total=500 * 1024**3, used=492 * 1024**3, free=8 * 1024**3)
        r = check_disk_space("/mnt/data", 5.0)
        assert r.passed is True
        assert r.severity == "warn"

    @patch("shutil.disk_usage")
    def test_critical_block(self, mock_usage):
        # Free = 2 GB, threshold = 5 GB → block
        mock_usage.return_value = _DiskUsage(total=500 * 1024**3, used=498 * 1024**3, free=2 * 1024**3)
        r = check_disk_space("/mnt/data", 5.0)
        assert r.passed is False
        assert r.severity == "block"

    @patch("shutil.disk_usage", side_effect=OSError("No such path"))
    def test_oserror_graceful(self, _):
        r = check_disk_space("/nonexistent", 5.0)
        assert r.passed is True
        assert r.severity == "warn"


# ---------------------------------------------------------------------------
# run_preflight
# ---------------------------------------------------------------------------


class TestRunPreflight:
    @pytest.mark.asyncio
    async def test_all_pass(self):
        cfg = _FakeCfg(vpn_required_for_downloads=False)
        qbt = MagicMock()
        qbt.get_transfer_info.return_value = {"connection_status": "connected", "dht_nodes": 42}
        with patch("shutil.disk_usage", return_value=_DiskUsage(500 * 1024**3, 100 * 1024**3, 400 * 1024**3)):
            report = await run_preflight(cfg, qbt, "/mnt/data")
        assert report.can_proceed is True
        assert len(report.blockers) == 0
        assert len(report.checks) == 3

    @pytest.mark.asyncio
    async def test_one_blocker(self):
        cfg = _FakeCfg(vpn_required_for_downloads=False)
        qbt = MagicMock()
        qbt.get_transfer_info.return_value = {"connection_status": "disconnected", "dht_nodes": 0}
        with patch("shutil.disk_usage", return_value=_DiskUsage(500 * 1024**3, 100 * 1024**3, 400 * 1024**3)):
            report = await run_preflight(cfg, qbt, "/mnt/data")
        assert report.can_proceed is False
        assert len(report.blockers) == 1

    @pytest.mark.asyncio
    async def test_warnings_only(self):
        cfg = _FakeCfg(vpn_required_for_downloads=False)
        qbt = MagicMock()
        qbt.get_transfer_info.return_value = {"connection_status": "firewalled", "dht_nodes": 10}
        with patch("shutil.disk_usage", return_value=_DiskUsage(500 * 1024**3, 100 * 1024**3, 400 * 1024**3)):
            report = await run_preflight(cfg, qbt, "/mnt/data")
        assert report.can_proceed is True
        assert len(report.warnings) == 1
        assert len(report.blockers) == 0
