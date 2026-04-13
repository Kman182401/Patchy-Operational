"""Tests for the completion-security gate: ClamAV scanning and the
``_apply_completion_security_gate`` flow that pauses/deletes infected torrents.

Mocks ``subprocess.run`` for clamdscan/clamscan invocation branches, and the
HandlerContext for the gate orchestration flow. Asserts health logging,
path safety, and deletion behavior.
"""

from __future__ import annotations

import shutil as _shutil_mod
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import patchy_bot.handlers.download as _dl_mod
from patchy_bot.handlers.download import (
    CompletionSecurityResult,
    _apply_completion_security_gate,
    _clamd_available,
    _run_clamav_scan,
)


# ---------------------------------------------------------------------------
# _run_clamav_scan — subprocess branches
# ---------------------------------------------------------------------------


class TestRunClamavScan:
    def _fake_run(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
        cp = MagicMock()
        cp.returncode = returncode
        cp.stdout = stdout
        cp.stderr = stderr
        return cp

    def test_clean_returns_clean(self) -> None:
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(0)):
                status, reasons = _run_clamav_scan("/tmp/foo", 10)
        assert status == "clean"
        assert reasons == []

    def test_infected_returns_infected(self) -> None:
        stdout = "/tmp/foo/bad.exe: Win.Trojan.Test FOUND\n"
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(1, stdout=stdout)):
                status, reasons = _run_clamav_scan("/tmp/foo", 10)
        assert status == "infected"
        assert any("FOUND" in r for r in reasons)

    def test_infected_no_stdout_fallback(self) -> None:
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(1, stdout="")):
                status, reasons = _run_clamav_scan("/tmp/foo", 10)
        assert status == "infected"
        assert reasons == ["ClamAV reported infected content"]

    def test_error_returns_error(self) -> None:
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(2, stderr="scan failed badly")):
                status, reasons = _run_clamav_scan("/tmp/foo", 10)
        assert status == "error"
        assert any("scan failed badly" in r for r in reasons)

    def test_timeout_returns_error(self) -> None:
        def _raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="clamscan", timeout=5)

        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", side_effect=_raise_timeout):
                status, reasons = _run_clamav_scan("/tmp/foo", 5)
        assert status == "error"
        assert any("timed out" in r for r in reasons)

    def test_exception_returns_error(self) -> None:
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", side_effect=RuntimeError("boom")):
                status, reasons = _run_clamav_scan("/tmp/foo", 5)
        assert status == "error"
        assert any("failed" in r.lower() for r in reasons)

    def test_empty_path_returns_error(self) -> None:
        status, reasons = _run_clamav_scan("", 10)
        assert status == "error"
        assert any("path missing" in r for r in reasons)

    def test_no_db_returns_unavailable(self) -> None:
        stderr = "ERROR: No supported database files found"
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(2, stderr=stderr)):
                status, _ = _run_clamav_scan("/tmp/foo", 10)
        assert status == "unavailable"

    def test_cant_open_returns_unavailable(self) -> None:
        stderr = "ERROR: Can't open file or directory"
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(2, stderr=stderr)):
                status, _ = _run_clamav_scan("/tmp/foo", 10)
        assert status == "unavailable"


# ---------------------------------------------------------------------------
# _clamd_available — availability cache + ping behavior
# ---------------------------------------------------------------------------


class TestClamdAvailable:
    def setup_method(self) -> None:
        # Reset module cache before each test
        _dl_mod._clamd_cache = (False, 0.0)

    def test_clamdscan_not_installed(self) -> None:
        with patch.object(_dl_mod.shutil, "which", return_value=None):
            assert _clamd_available() is False

    def test_daemon_responsive(self) -> None:
        cp = MagicMock(returncode=0, stdout="PONG", stderr="")
        with patch.object(_dl_mod.shutil, "which", return_value="/usr/bin/clamdscan"):
            with patch.object(subprocess, "run", return_value=cp):
                assert _clamd_available() is True

    def test_daemon_down(self) -> None:
        cp = MagicMock(returncode=2, stdout="", stderr="cannot connect")
        with patch.object(_dl_mod.shutil, "which", return_value="/usr/bin/clamdscan"):
            with patch.object(subprocess, "run", return_value=cp):
                assert _clamd_available() is False

    def test_cache_ttl(self) -> None:
        """A second call within the TTL window returns cached result."""
        cp = MagicMock(returncode=0, stdout="PONG", stderr="")
        with patch.object(_dl_mod.shutil, "which", return_value="/usr/bin/clamdscan"):
            with patch.object(subprocess, "run", return_value=cp) as spy:
                _clamd_available()
                _clamd_available()
                # Second call should be served from cache — run called only once
                assert spy.call_count == 1

    def test_ping_timeout(self) -> None:
        def _raise(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="clamdscan", timeout=3)

        with patch.object(_dl_mod.shutil, "which", return_value="/usr/bin/clamdscan"):
            with patch.object(subprocess, "run", side_effect=_raise):
                assert _clamd_available() is False


# ---------------------------------------------------------------------------
# Clamd vs clamscan argv fallback
# ---------------------------------------------------------------------------


class TestClamdVsClamscanFallback:
    def _fake_run(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
        cp = MagicMock()
        cp.returncode = returncode
        cp.stdout = stdout
        cp.stderr = stderr
        return cp

    def test_daemon_available_uses_clamdscan(self) -> None:
        with patch.object(_dl_mod, "_clamd_available", return_value=True):
            with patch.object(subprocess, "run", return_value=self._fake_run(0)) as spy:
                _run_clamav_scan("/tmp/foo", 10)
        argv = spy.call_args[0][0]
        assert argv[0] == "clamdscan"

    def test_daemon_unavailable_uses_clamscan(self) -> None:
        with patch.object(_dl_mod, "_clamd_available", return_value=False):
            with patch.object(subprocess, "run", return_value=self._fake_run(0)) as spy:
                _run_clamav_scan("/tmp/foo", 10)
        argv = spy.call_args[0][0]
        assert argv[0] == "clamscan"


# ---------------------------------------------------------------------------
# _apply_completion_security_gate — end-to-end flow
# ---------------------------------------------------------------------------


@pytest.fixture
def gate_ctx(mock_ctx):
    """HandlerContext with the bits _apply_completion_security_gate touches.

    Adds: qbt.pause_torrents, qbt.delete_torrent, store.log_malware_block,
    store.log_health_event. cfg.malware_scan_timeout_s and cfg media paths
    come from mock_ctx already.
    """
    mock_ctx.qbt.pause_torrents = MagicMock(return_value=None)
    mock_ctx.qbt.delete_torrent = MagicMock(return_value=None)
    mock_ctx.store.log_malware_block = MagicMock(return_value=None)
    mock_ctx.store.log_health_event = MagicMock(return_value=None)
    # ensure timeout attribute exists (Config defines it)
    if not hasattr(mock_ctx.cfg, "malware_scan_timeout_s"):
        mock_ctx.cfg.malware_scan_timeout_s = 60
    return mock_ctx


class TestCompletionSecurityGate:
    @pytest.mark.asyncio
    async def test_clean_allows(self, gate_ctx, tmp_path) -> None:
        media_path = str(tmp_path / "movies" / "foo")
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("clean", [])):
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="Movie.2024.mkv",
                media_path=media_path,
            )
        assert result.allowed is True
        assert result.notice_text is None

    @pytest.mark.asyncio
    async def test_unavailable_allows(self, gate_ctx) -> None:
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("unavailable", ["no db"])):
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="Movie.mkv",
                media_path="/tmp/foo",
            )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_error_pauses_and_blocks(self, gate_ctx) -> None:
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("error", ["scan crashed"])):
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="Movie.mkv",
                media_path="/tmp/foo",
            )
        assert result.allowed is False
        gate_ctx.qbt.pause_torrents.assert_called_once()
        assert result.notice_text is not None
        assert "Security Hold" in result.notice_text

    @pytest.mark.asyncio
    async def test_error_logs_health_event(self, gate_ctx) -> None:
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("error", ["oops"])):
            await _apply_completion_security_gate(
                gate_ctx,
                user_id=99,
                torrent_hash="h" * 40,
                name="Movie.mkv",
                media_path="/tmp/foo",
            )
        assert gate_ctx.store.log_health_event.called
        call = gate_ctx.store.log_health_event.call_args
        # positional args: (user_id, torrent_hash, stage, severity, json_payload, name)
        pos = call.args
        assert pos[2] == "malware_scan_error"
        assert pos[3] == "warn"

    @pytest.mark.asyncio
    async def test_infected_deletes_torrent(self, gate_ctx, tmp_path) -> None:
        # Use a path inside cfg.movies_path so _validate_safe_path returns True
        media_path = str(tmp_path / "Movies" / "dangerous")
        (tmp_path / "Movies" / "dangerous").mkdir(parents=True)
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["Win.Trojan.FOUND"])):
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="Movie.mkv",
                media_path=media_path,
            )
        assert result.allowed is False
        gate_ctx.qbt.delete_torrent.assert_called_once()
        call = gate_ctx.qbt.delete_torrent.call_args
        assert call.kwargs.get("delete_files") is True or True in call.args

    @pytest.mark.asyncio
    async def test_infected_rmtree_fallback(self, gate_ctx, tmp_path) -> None:
        """When qBT delete leaves the dir behind, rmtree fallback removes it."""
        media_dir = tmp_path / "Movies" / "evil"
        media_dir.mkdir(parents=True)
        (media_dir / "bad.exe").write_text("evil")
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND"])):
            await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="evil",
                media_path=str(media_dir),
            )
        assert not media_dir.exists()

    @pytest.mark.asyncio
    async def test_infected_validates_path(self, gate_ctx, tmp_path) -> None:
        media_dir = tmp_path / "Movies" / "bad"
        media_dir.mkdir(parents=True)
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND"])):
            with patch.object(_dl_mod, "_validate_safe_path", wraps=_dl_mod._validate_safe_path) as spy:
                await _apply_completion_security_gate(
                    gate_ctx,
                    user_id=1,
                    torrent_hash="h" * 40,
                    name="bad",
                    media_path=str(media_dir),
                )
        assert spy.called

    @pytest.mark.asyncio
    async def test_infected_logs_malware_block(self, gate_ctx, tmp_path) -> None:
        media_dir = tmp_path / "Movies" / "bad"
        media_dir.mkdir(parents=True)
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND: test.virus"])):
            await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="bad",
                media_path=str(media_dir),
            )
        assert gate_ctx.store.log_malware_block.called
        call = gate_ctx.store.log_malware_block.call_args
        # signature: (torrent_hash, name, stage, reasons)
        assert "download" in call.args

    @pytest.mark.asyncio
    async def test_infected_logs_health_event(self, gate_ctx, tmp_path) -> None:
        media_dir = tmp_path / "Movies" / "bad"
        media_dir.mkdir(parents=True)
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND"])):
            await _apply_completion_security_gate(
                gate_ctx,
                user_id=42,
                torrent_hash="h" * 40,
                name="bad",
                media_path=str(media_dir),
            )
        assert gate_ctx.store.log_health_event.called
        call = gate_ctx.store.log_health_event.call_args
        pos = call.args
        assert pos[2] == "malware_delete"
        assert pos[3] == "critical"

    @pytest.mark.asyncio
    async def test_infected_notifies_users(self, gate_ctx, tmp_path) -> None:
        media_dir = tmp_path / "Movies" / "bad"
        media_dir.mkdir(parents=True)
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND"])):
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="bad",
                media_path=str(media_dir),
            )
        assert result.notice_text is not None
        assert "Malware Detected" in result.notice_text

    @pytest.mark.asyncio
    async def test_empty_path_blocks(self, gate_ctx) -> None:
        result = await _apply_completion_security_gate(
            gate_ctx,
            user_id=1,
            torrent_hash="h" * 40,
            name="foo",
            media_path="",
        )
        assert result.allowed is False
        assert result.notice_text is not None

    @pytest.mark.asyncio
    async def test_deletion_error_doesnt_crash(self, gate_ctx, tmp_path) -> None:
        media_dir = tmp_path / "Movies" / "bad"
        media_dir.mkdir(parents=True)
        gate_ctx.qbt.delete_torrent = MagicMock(side_effect=RuntimeError("qbt offline"))
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND"])):
            # Must not raise
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="bad",
                media_path=str(media_dir),
            )
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_log_failure_doesnt_crash(self, gate_ctx, tmp_path) -> None:
        media_dir = tmp_path / "Movies" / "bad"
        media_dir.mkdir(parents=True)
        gate_ctx.store.log_health_event = MagicMock(side_effect=RuntimeError("db gone"))
        with patch.object(_dl_mod, "_run_clamav_scan", return_value=("infected", ["FOUND"])):
            result = await _apply_completion_security_gate(
                gate_ctx,
                user_id=1,
                torrent_hash="h" * 40,
                name="bad",
                media_path=str(media_dir),
            )
        assert result.allowed is False


# ---------------------------------------------------------------------------
# Optional real ClamAV smoke tests (L7)
# ---------------------------------------------------------------------------


clamav_available = pytest.mark.skipif(
    not _shutil_mod.which("clamdscan") and not _shutil_mod.which("clamscan"),
    reason="ClamAV not installed",
)


class TestRealClamav:
    @clamav_available
    def test_clean_scan_zero_byte_file(self, tmp_path) -> None:
        test_file = tmp_path / "empty.dat"
        test_file.write_bytes(b"")
        status, _ = _run_clamav_scan(str(test_file), timeout_s=30)
        assert status in ("clean", "unavailable")

    @clamav_available
    def test_clean_scan_text_file(self, tmp_path) -> None:
        test_file = tmp_path / "note.txt"
        test_file.write_text("hello world")
        status, _ = _run_clamav_scan(str(test_file), timeout_s=30)
        assert status in ("clean", "unavailable")

    @clamav_available
    def test_eicar_detected(self, tmp_path) -> None:
        eicar = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        test_file = tmp_path / "eicar.com"
        test_file.write_text(eicar)
        status, _ = _run_clamav_scan(str(test_file), timeout_s=30)
        assert status in ("infected", "unavailable")
