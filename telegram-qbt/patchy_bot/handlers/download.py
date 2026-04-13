"""Download tracking, progress monitoring, and completion polling.

Extracted from BotApp — all download-related logic lives here as
module-level functions.  Static/class methods become plain functions.
Instance methods take a HandlerContext as their first argument.
"""

from __future__ import annotations

import asyncio
import errno as _errno
import json
import logging
import re
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..malware import scan_download
from ..plex_organizer import organize_download as _organize_download
from ..types import HandlerContext
from ..ui import flow as flow_mod
from ..ui import rendering as render_mod
from ..utils import _PM, _h, human_size, normalize_title, quality_tier
from ._shared import (
    check_free_space,
    ensure_media_categories,
    normalize_media_choice,
    qbt_transport_status,
    targets,
    vpn_ready_for_download,
)

LOG = logging.getLogger("qbtg")

# In-memory dedup for completion poller — resets on service restart.
# The persistent DB layer (is_completion_notified) is the safety net.
_poller_seen_hashes: set[str] = set()


@dataclass(frozen=True, slots=True)
class CompletionSecurityResult:
    allowed: bool
    media_path: str
    notice_text: str | None = None


@dataclass(frozen=True, slots=True)
class TrackerEditResult:
    ok: bool
    retry_after_s: int = 0


def _torrent_file_names(files: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in files:
        name = str(row.get("name") or row.get("path") or "").strip()
        if name:
            out.append(name)
    return out


def _torrent_file_sizes(files: list[dict[str, Any]]) -> list[int]:
    """Parallel list of per-file sizes (bytes), aligned with _torrent_file_names."""
    out: list[int] = []
    for row in files:
        name = str(row.get("name") or row.get("path") or "").strip()
        if not name:
            continue
        try:
            out.append(int(row.get("size") or 0))
        except (TypeError, ValueError):
            out.append(0)
    return out


_NFO_MAX_BYTES = 50_000


def _read_torrent_nfo(raw_files: list[dict[str, Any]], media_path: str) -> str | None:
    """Read the first .nfo file under *media_path* for malware NFO scanning.

    Returns None if no NFO file is present, the file is too large, the path is
    outside *media_path* (symlink or traversal), or any I/O error occurs.
    Never follows symlinks outside *media_path*.
    """
    if not media_path or not raw_files:
        return None
    from pathlib import Path

    try:
        base = Path(media_path).resolve()
    except (OSError, RuntimeError):
        return None
    for row in raw_files:
        name = str(row.get("name") or row.get("path") or "").strip()
        if not name or not name.lower().endswith(".nfo"):
            continue
        try:
            size = int(row.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        if size <= 0 or size > _NFO_MAX_BYTES:
            continue
        candidate = Path(media_path) / name
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        try:
            if not resolved.is_relative_to(base):
                continue
        except (AttributeError, ValueError):
            continue
        try:
            with open(resolved, encoding="utf-8", errors="replace") as fh:
                return fh.read(_NFO_MAX_BYTES)
        except OSError:
            continue
    return None


def _validate_safe_path(target: str, allowed_roots: list[str]) -> bool:
    """Return True iff *target* resolves inside one of *allowed_roots*.

    Used as a guard before any destructive filesystem operation on download
    payloads.  Symlinks are resolved on both sides.  Roots that fail to
    resolve are silently skipped — never widen the allow-list on error.
    """
    from pathlib import Path

    try:
        resolved = Path(target).resolve()
    except (OSError, RuntimeError):
        return False
    for root in allowed_roots:
        if not root:
            continue
        try:
            root_resolved = Path(root).resolve()
        except (OSError, RuntimeError):
            continue
        try:
            if resolved.is_relative_to(root_resolved):
                return True
        except (AttributeError, ValueError):
            continue
    return False


async def _wait_for_file_inspection(
    ctx: HandlerContext,
    torrent_hash: str,
    *,
    timeout_s: int,
) -> list[dict[str, Any]]:
    """Poll qBittorrent for file metadata; return raw rows once available."""
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            files = await asyncio.to_thread(ctx.qbt.get_torrent_files, torrent_hash)
            if files:
                return files
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(0.8)
    if last_error is not None:
        raise RuntimeError(f"file inspection did not complete: {last_error}")
    raise RuntimeError("file inspection did not complete before timeout")


async def _concurrent_file_scan(
    ctx: HandlerContext,
    user_id: int,
    torrent_hash: str,
    result: "DoAddResult",
    interim_msg: Any,
) -> None:
    """Run file-list inspection + heuristic scan concurrently with active download.

    If the scan detects suspicious content, pauses the torrent and sends a
    Keep/Delete prompt as a **new message** (the progress tracker already owns
    interim_msg).  Otherwise completes silently — ClamAV completion gate is
    the safety net.
    """
    inspection_timeout = (
        ctx.cfg.file_inspection_timeout_s * 3 if result.is_magnet else ctx.cfg.file_inspection_timeout_s
    )
    try:
        raw_files = await _wait_for_file_inspection(ctx, torrent_hash, timeout_s=inspection_timeout)
    except Exception as exc:
        LOG.warning(
            "Concurrent scan: inspection timeout for %s (magnet=%s): %s",
            torrent_hash,
            result.is_magnet,
            exc,
        )
        return  # ClamAV completion gate is the safety net

    files = _torrent_file_names(raw_files)
    file_sizes = _torrent_file_sizes(raw_files)
    malware_scan = scan_download(
        name=result.name,
        size_bytes=result.size,
        quality_tier=quality_tier(result.name),
        media_type=result.media_type,
        files=files,
        uploader=result.uploader,
        file_sizes=file_sizes,
    )
    if not malware_scan.is_blocked:
        return  # Clean — download continues

    # --- Blocked: pause torrent and prompt user ---
    try:
        await asyncio.to_thread(ctx.qbt.pause_torrents, torrent_hash)
    except Exception:
        LOG.warning("Failed to pause blocked torrent %s", torrent_hash, exc_info=True)
    try:
        ctx.store.log_malware_block(
            torrent_hash=torrent_hash,
            torrent_name=result.name,
            stage="download",
            reasons=malware_scan.reasons,
        )
    except Exception:
        pass
    top_signals = sorted(malware_scan.signals, key=lambda s: s.points, reverse=True)[:5]
    signal_lines = "\n".join(f"• <code>{_h(s.signal_id)}</code> (+{s.points}) {_h(s.detail)}" for s in top_signals)
    warn_text = (
        f"🚫 <b>Blocked</b> (Score: {malware_scan.score}/100)\n"
        f"<code>{_h(result.name)}</code>\n\n"
        f"<b>Signals:</b>\n{signal_lines}\n\n"
        "Torrent is <b>paused</b>. Choose an action:"
    )
    warn_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Keep & Resume", callback_data=f"mwblock:keep:{torrent_hash}"),
                InlineKeyboardButton("\U0001f5d1 Delete", callback_data=f"mwblock:delete:{torrent_hash}"),
            ],
        ]
    )
    # Send as NEW message — progress tracker already owns interim_msg.
    try:
        chat_id = getattr(interim_msg, "chat_id", None) or getattr(getattr(interim_msg, "chat", None), "id", None)
        bot = getattr(interim_msg, "get_bot", lambda: None)()
        if bot and chat_id:
            sent = await bot.send_message(chat_id=chat_id, text=warn_text, reply_markup=warn_kb, parse_mode=_PM)
            track_ephemeral_message(ctx, user_id, sent)
    except Exception:
        LOG.warning("Failed to send concurrent scan block alert", exc_info=True)


_clamd_cache: tuple[bool, float] = (False, 0.0)
_CLAMD_CACHE_TTL = 60.0

# Short-lived cache for pre-flight checks (categories, transport, VPN).
# Avoids repeating expensive checks when adding multiple episodes in a batch.
_preflight_cache: dict[str, tuple[Any, float]] = {}
_PREFLIGHT_CACHE_TTL = 30.0


@dataclass(frozen=True, slots=True)
class DoAddResult:
    """Fast-phase result from do_add() — returned before hash resolution / inspection."""

    name: str
    size: int
    hash: str | None
    category: str
    save_path: str
    url: str
    is_magnet: bool
    idx: int
    target_label: str
    resp: str
    media_type: str
    uploader: str | None
    inspection_note: str = ""
    queued: bool = False


def _clamd_available() -> bool:
    global _clamd_cache
    now = time.time()
    if now - _clamd_cache[1] < _CLAMD_CACHE_TTL:
        return _clamd_cache[0]
    if not shutil.which("clamdscan"):
        _clamd_cache = (False, now)
        return False
    try:
        result = subprocess.run(
            ["clamdscan", "--ping=1"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        _clamd_cache = (False, now)
        return False
    available = result.returncode == 0
    _clamd_cache = (available, now)
    return available


def _run_clamav_scan(path: str, timeout_s: int) -> tuple[str, list[str]]:
    if not path:
        return ("error", ["download path missing"])

    if _clamd_available():
        cmd = ["clamdscan", "--multiscan", "--fdpass", "--infected", "--no-summary", path]
    else:
        cmd = ["clamscan", "--recursive", "--infected", "--no-summary", path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ("error", [f"ClamAV scan timed out after {timeout_s}s"])
    except Exception as exc:
        return ("error", [f"ClamAV scan failed: {exc}"])

    stdout_lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    stderr_lines = [line.strip() for line in (result.stderr or "").splitlines() if line.strip()]

    if result.returncode == 0:
        return ("clean", [])
    if result.returncode == 1:
        hits = [line for line in stdout_lines if "FOUND" in line]
        return ("infected", hits or ["ClamAV reported infected content"])

    # ClamAV exits with code 2 for operational errors.  When the virus
    # database is missing / empty the scanner literally cannot work —
    # this is an infrastructure gap, not a suspicious file.  Treat it
    # the same as "scanner not installed" and let the download through
    # so the heuristic malware gate (which already ran at add-time) is
    # the effective safety net.
    all_output = " ".join(stderr_lines + stdout_lines)
    if "No supported database files found" in all_output or "Can't open file or directory" in all_output:
        LOG.warning("ClamAV database unavailable — skipping scan for %s", path)
        return ("unavailable", stderr_lines or stdout_lines)

    reasons = stderr_lines or stdout_lines or [f"ClamAV exited with code {result.returncode}"]
    return ("error", reasons)


async def _apply_completion_security_gate(
    ctx: HandlerContext,
    *,
    user_id: int,
    torrent_hash: str,
    name: str,
    media_path: str,
) -> CompletionSecurityResult:
    if not media_path:
        return CompletionSecurityResult(False, media_path, "Security hold: download path unavailable for scanning.")

    status, reasons = await asyncio.to_thread(_run_clamav_scan, media_path, ctx.cfg.malware_scan_timeout_s)
    if status == "clean":
        return CompletionSecurityResult(True, media_path)

    # --- ClamAV unavailable (no database) → allow through, log warning ---
    if status == "unavailable":
        LOG.warning("ClamAV unavailable for %s — allowing download (heuristic scan already passed)", name)
        return CompletionSecurityResult(True, media_path)

    # --- ClamAV error (timeout / crash) → pause + warn, allow retry next poll ---
    if status == "error":
        try:
            await asyncio.to_thread(ctx.qbt.pause_torrents, torrent_hash)
        except Exception:
            LOG.warning("Failed to pause torrent after scan error: %s", torrent_hash, exc_info=True)
        try:
            await asyncio.to_thread(
                ctx.store.log_health_event,
                user_id,
                torrent_hash,
                "malware_scan_error",
                "warn",
                json.dumps({"reasons": reasons}),
                name,
            )
        except Exception:
            LOG.debug("Failed to log malware health event", exc_info=True)
        reason_lines = "\n".join(f"• {_h(reason)}" for reason in reasons[:8])
        notice = (
            f"⚠️ <b>Security Hold</b>\n<code>{_h(name)}</code>\n\n"
            f"ClamAV could not produce a safe verdict. Torrent paused pending manual review.\n\n"
            f"{reason_lines}"
        )
        # Return allowed=False — caller will skip organization
        # but mark_completion_notified prevents infinite re-scan.
        return CompletionSecurityResult(False, media_path, notice)

    # --- ClamAV infected → delete files, block ---
    allowed_roots = [
        ctx.cfg.tv_path,
        ctx.cfg.movies_path,
        ctx.cfg.spam_path,
        getattr(ctx.cfg, "qbt_download_path", "") or "",
    ]
    safe_to_delete = _validate_safe_path(media_path, allowed_roots) if media_path else False

    try:
        await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
    except Exception:
        LOG.warning("Failed to delete torrent after malware hold: %s", torrent_hash, exc_info=True)

    if safe_to_delete and media_path:
        try:
            await asyncio.to_thread(shutil.rmtree, media_path, True)
        except Exception:
            LOG.warning("rmtree fallback failed for %s", media_path, exc_info=True)
    elif media_path:
        LOG.critical(
            "Refusing to delete suspicious payload outside allowed roots: %s",
            media_path,
        )

    try:
        await asyncio.to_thread(ctx.store.log_malware_block, torrent_hash, name, "download", reasons)
    except Exception:
        LOG.debug("Failed to log malware block", exc_info=True)

    try:
        await asyncio.to_thread(
            ctx.store.log_health_event,
            user_id,
            torrent_hash,
            "malware_delete",
            "critical",
            json.dumps({"reasons": reasons}),
            name,
        )
    except Exception:
        LOG.debug("Failed to log malware health event", exc_info=True)

    reason_lines = "\n".join(f"• {_h(reason)}" for reason in reasons[:8])
    notice = (
        f"⚠️ <b>Malware Detected</b>\n<code>{_h(name)}</code>\n\n"
        f"ClamAV detected malicious content. Files have been deleted.\n\n"
        f"{reason_lines}"
    )
    return CompletionSecurityResult(False, media_path, notice)


# ---------------------------------------------------------------------------
# Progress rendering (pure functions — no ctx needed)
# ---------------------------------------------------------------------------


def progress_bar(progress_pct: float, width: int = 18) -> str:
    """Render a Unicode progress bar with sub-block precision."""
    EIGHTHS = ["\u258f", "\u258e", "\u258d", "\u258c", "\u258b", "\u258a", "\u2589"]
    pct = max(0.0, min(100.0, progress_pct))
    total_eighths = int((pct / 100.0) * width * 8)
    full_blocks = total_eighths // 8
    remainder = total_eighths % 8
    bar = "\u2588" * full_blocks
    if full_blocks < width:
        if remainder > 0:
            bar += EIGHTHS[remainder - 1]
            bar += "\u2591" * (width - full_blocks - 1)
        else:
            bar += "\u2591" * (width - full_blocks)
    return bar


def completed_bytes(info: dict[str, Any]) -> int:
    """Return the number of completed bytes for a torrent info dict."""
    total_bytes = int(info.get("size", 0) or info.get("total_size", 0) or 0)
    completed = int(info.get("completed", 0) or 0)
    downloaded = int(info.get("downloaded", 0) or 0)

    done = completed if completed > 0 else downloaded
    done = max(0, done)
    if total_bytes > 0:
        done = min(done, total_bytes)
    return done


def is_complete_torrent(info: dict[str, Any]) -> bool:
    """Return True if the torrent info indicates a fully downloaded torrent."""
    state = str(info.get("state") or "").strip()
    try:
        progress = float(info.get("progress", 0.0) or 0.0)
    except Exception:
        progress = 0.0

    total_bytes = int(info.get("size", 0) or info.get("total_size", 0) or 0)
    _raw_left = info.get("amount_left")
    amount_left = int(_raw_left) if _raw_left is not None else -1
    completed_b = completed_bytes(info)

    if progress >= 0.999:
        return True

    if total_bytes > 0 and completed_b >= total_bytes:
        return True

    if amount_left == 0 and total_bytes > 0:
        return True

    return state in {"uploading", "stalledUP", "queuedUP", "forcedUP", "pausedUP", "checkingUP"}


def format_eta(eta_seconds: int) -> str:
    """Format ETA seconds into a human-readable string."""
    # qBittorrent uses large sentinel values (e.g. 8640000) for unknown ETA.
    if eta_seconds < 0 or eta_seconds >= 8640000:
        return "\u221e"
    days, rem = divmod(eta_seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if days > 0:
        return f"{days}d {h:02d}:{m:02d}:{s:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"


def state_label(info: dict[str, Any]) -> str:
    """Return a human-readable state label for a torrent info dict."""
    state = str(info.get("state") or "unknown").strip()
    if is_complete_torrent(info):
        return "seeding"
    labels = {
        "metaDL": "getting metadata",
        "forcedMetaDL": "getting metadata",
        "downloading": "downloading",
        "forcedDL": "downloading",
        "stalledDL": "waiting for seeders",
        "queuedDL": "queued",
        "pausedDL": "paused",
        "checkingDL": "checking",
        "checkingResumeData": "checking",
        "moving": "moving",
        "missingFiles": "missing files",
        "error": "error",
    }
    return labels.get(state, state or "unknown")


def eta_label(info: dict[str, Any]) -> str:
    """Return the ETA display text for a torrent info dict."""
    state = str(info.get("state") or "").strip()
    if is_complete_torrent(info):
        return "done"
    if state in {"metaDL", "forcedMetaDL"}:
        return "metadata"
    if state in {"checkingDL", "checkingResumeData", "moving"}:
        return state.replace("DL", "").replace("ResumeData", " resume data").lower()
    _raw_eta = info.get("eta")
    eta = int(_raw_eta) if _raw_eta is not None else -1
    return format_eta(eta)


def render_progress_text(
    name: str,
    info: dict[str, Any],
    tick: int,
    *,
    progress_pct: float | None = None,
    dls_bps: int | None = None,
    uls_bps: int | None = None,
    header: str | None = None,
) -> str:
    """Build the live-progress message text."""
    raw_progress = float(info.get("progress", 0.0) or 0.0) * 100.0
    progress = max(0.0, min(100.0, raw_progress if progress_pct is None else progress_pct))
    bar = progress_bar(progress)

    dls_val = int(info.get("dlspeed", 0) or 0) if dls_bps is None else max(0, int(dls_bps))
    uls_val = int(info.get("upspeed", 0) or 0) if uls_bps is None else max(0, int(uls_bps))
    dls = human_size(dls_val) + "/s"
    uls = human_size(uls_val) + "/s"

    total_bytes = int(info.get("size", 0) or info.get("total_size", 0) or 0)
    done_bytes = completed_bytes(info)
    done = human_size(done_bytes)
    total = human_size(total_bytes) if total_bytes > 0 else "?"
    eta_txt = eta_label(info)
    state_txt = state_label(info)

    monitor = (
        f"<b>Live Download Monitor</b>\n"
        f"<code>{_h(name)}</code>\n"
        f"<code>[{bar}] {progress:.1f}%</code>\n"
        f"State: <b>{state_txt}</b>\n"
        f"\u2193 <code>{dls}</code> \u2022 ETA <code>{eta_txt}</code>\n"
        f"Done: <code>{done}</code> / <code>{total}</code>"
    )
    if header:
        return f"{header}\n\n{monitor}"
    return monitor


def render_batch_monitor_text(entries: list[dict[str, Any]]) -> str:
    """Render the consolidated live-monitor text for all active downloads."""
    if not entries:
        return "<b>⬇️ All downloads complete</b>"

    blocks: list[str] = []
    for entry in entries:
        title = str(entry.get("title") or "Download")
        info = dict(entry.get("info") or {})
        try:
            progress_pct = entry.get("progress_pct")
            progress = float(info.get("progress", 0.0) or 0.0) * 100.0 if progress_pct is None else float(progress_pct)
        except Exception:
            progress = 0.0
        progress = max(0.0, min(100.0, progress))
        bar = progress_bar(progress)
        eta_txt = eta_label(info)
        blocks.append(
            f"<code>{_h(title)}</code>\n<code>[{bar}] {progress:.1f}%</code> · ETA <code>{_h(eta_txt)}</code>"
        )
    return f"<b>⬇️ Downloading</b> · <i>{len(entries)} active</i>\n\n" + "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Keyboard builders
# ---------------------------------------------------------------------------


def stop_download_keyboard(
    torrent_hash: str,
    *,
    post_add_rows: list[list[Any]] | None = None,
) -> InlineKeyboardMarkup:
    """Build the inline keyboard with Home + Stop buttons for a download.

    If post_add_rows is provided, those rows are prepended before the Home/Stop row.
    """
    rows: list[list[Any]] = []
    if post_add_rows:
        rows.extend(post_add_rows)
    rows.append(
        [
            InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home"),
            InlineKeyboardButton("\U0001f6d1 Stop & Delete Download", callback_data=f"stop:{torrent_hash}"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def batch_stop_keyboard(torrent_hashes: list[str]) -> InlineKeyboardMarkup:
    """Build the inline keyboard used by the consolidated batch monitor."""
    prefix = "stop:all:"
    max_hash_bytes = 50
    joined_hashes = []
    total_bytes = 0
    truncated = False
    for raw_hash in torrent_hashes:
        torrent_hash = str(raw_hash or "").strip()
        if not torrent_hash:
            continue
        encoded = torrent_hash.encode("utf-8")
        extra = len(encoded) + (1 if joined_hashes else 0)
        if total_bytes + extra > max_hash_bytes:
            truncated = True
            break
        joined_hashes.append(torrent_hash)
        total_bytes += extra

    if truncated:
        LOG.warning(
            "Batch stop callback truncated from %d to %d hash(es) to fit Telegram callback_data limits",
            len([h for h in torrent_hashes if str(h or "").strip()]),
            len(joined_hashes),
        )

    callback_data = prefix + ",".join(joined_hashes)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home"),
                InlineKeyboardButton("\U0001f6d1 Stop All Downloads", callback_data=callback_data),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# Telegram message helpers (need ctx for ephemeral tracking)
# ---------------------------------------------------------------------------


def track_ephemeral_message(ctx: HandlerContext, user_id: int, message: Any) -> None:
    """Record a message in the user's ephemeral list for later cleanup."""
    chat_id = getattr(message, "chat_id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return
    ctx.user_ephemeral_messages.setdefault(user_id, []).append({"chat_id": int(chat_id), "message_id": int(message_id)})


async def tracker_send_fallback(ctx: HandlerContext, tracker_msg: Any, text: str) -> None:
    """Send a message directly to the chat when tracker_msg was deleted.

    Headless callers pass ``tracker_msg=None`` (no inline monitor message to fall back
    to); in that case the text is logged instead of pushed to the user, since the
    Command Center batch monitor owns all user-visible progress.
    """
    if tracker_msg is None:
        LOG.info("Headless tracker suppressed fallback send: %s", text.splitlines()[0] if text else "")
        return
    chat_id = getattr(tracker_msg, "chat_id", None)
    if not chat_id:
        return
    try:
        bot = tracker_msg.get_bot()
        sent = await bot.send_message(chat_id=chat_id, text=text, parse_mode=_PM)
        track_ephemeral_message(ctx, int(chat_id), sent)
    except Exception as exc:
        retry_after_s = tracker_retry_after_seconds(exc)
        if retry_after_s > 0:
            LOG.warning("Tracker fallback suppressed due to Telegram flood control: retry in %ss", retry_after_s)
            return
        LOG.warning("Tracker fallback send_message also failed", exc_info=True)


def tracker_retry_after_seconds(exc: Exception) -> int:
    raw = getattr(exc, "retry_after", 0) or 0
    try:
        retry_after_s = int(raw)
    except Exception:
        retry_after_s = 0
    if retry_after_s > 0:
        return retry_after_s
    match = re.search(r"retry in (\d+) seconds?", str(exc), re.IGNORECASE)
    if not match:
        return 0
    return int(match.group(1))


async def safe_tracker_edit(tracker_msg: Any, text: str, reply_markup: Any = None) -> TrackerEditResult:
    """Edit a tracker message, handling transient Telegram errors gracefully.

    Headless callers pass ``tracker_msg=None``; in that case the edit is a no-op and
    the result is reported as OK so the tracker loop can continue.
    """
    if tracker_msg is None:
        return TrackerEditResult(True)
    try:
        await tracker_msg.edit_text(text, reply_markup=reply_markup, parse_mode=_PM)
        return TrackerEditResult(True)
    except Exception as e:
        msg = str(e).lower()
        if "message is not modified" in msg:
            return TrackerEditResult(True)
        retry_after_s = tracker_retry_after_seconds(e)
        if retry_after_s > 0:
            LOG.warning("Live monitor Telegram edit paused by flood control: retry in %ss", retry_after_s)
            return TrackerEditResult(False, retry_after_s=retry_after_s)
        if "timed out" in msg or "timeout" in msg:
            LOG.warning("Live monitor Telegram edit transient failure: %s", e)
            return TrackerEditResult(False)
        LOG.warning("Live monitor Telegram edit failed: %s", e)
        return TrackerEditResult(False)


# ---------------------------------------------------------------------------
# Batch monitor lifecycle (one live monitor per user)
# ---------------------------------------------------------------------------


def _active_progress_hashes(ctx: HandlerContext, user_id: int) -> list[str]:
    hashes: list[str] = []
    for (uid, torrent_hash), task in list(ctx.progress_tasks.items()):
        if uid != user_id or task.done():
            continue
        hashes.append(torrent_hash)
    return hashes


async def _delete_batch_monitor_message(ctx: HandlerContext, user_id: int) -> None:
    tracker_msg = ctx.batch_monitor_messages.pop(user_id, None)
    if tracker_msg is None:
        return
    try:
        await tracker_msg.delete()
    except Exception:
        pass


async def _batch_monitor_entries(
    ctx: HandlerContext,
    user_id: int,
    torrent_hashes: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    active_hashes: list[str] = []
    for torrent_hash in torrent_hashes:
        key = (user_id, torrent_hash.lower())
        shared = dict(ctx.batch_monitor_data.get(key) or {})
        try:
            info = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
        except Exception:
            LOG.warning("Batch monitor qBittorrent poll failed for %s", torrent_hash, exc_info=True)
            continue
        if not info:
            continue
        active_hashes.append(torrent_hash.lower())
        entries.append(
            {
                "title": str(shared.get("title") or info.get("name") or torrent_hash),
                "info": info,
                "progress_pct": shared.get("progress_pct"),
            }
        )
    return entries, active_hashes


async def _run_batch_monitor_loop(ctx: HandlerContext, user_id: int, initial_chat_id: int) -> None:
    edit_backoff_until = 0.0
    last_text = ""
    last_callback_data = ""
    try:
        while True:
            incumbent = ctx.batch_monitor_tasks.get(user_id)
            if incumbent is not None and incumbent is not asyncio.current_task():
                return

            torrent_hashes = _active_progress_hashes(ctx, user_id)
            if not torrent_hashes:
                await _delete_batch_monitor_message(ctx, user_id)
                return

            entries, active_hashes = await _batch_monitor_entries(ctx, user_id, torrent_hashes)
            if not entries or not active_hashes:
                await asyncio.sleep(ctx.cfg.progress_refresh_s)
                continue

            tracker_msg = ctx.batch_monitor_messages.get(user_id)
            text = render_batch_monitor_text(entries)
            reply_markup = batch_stop_keyboard(active_hashes)
            callback_data = str(reply_markup.inline_keyboard[0][1].callback_data or "")

            if tracker_msg is None:
                if not ctx.app or not initial_chat_id:
                    return
                tracker_msg = await ctx.app.bot.send_message(
                    chat_id=initial_chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=_PM,
                )
                ctx.batch_monitor_messages[user_id] = tracker_msg
                last_text = text
                last_callback_data = callback_data
                await asyncio.sleep(ctx.cfg.progress_refresh_s)
                continue

            now = time.time()
            if now < edit_backoff_until:
                await asyncio.sleep(min(ctx.cfg.progress_refresh_s, max(0.2, edit_backoff_until - now)))
                continue

            if text != last_text or callback_data != last_callback_data:
                edit_result = await safe_tracker_edit(tracker_msg, text, reply_markup=reply_markup)
                if edit_result.ok:
                    last_text = text
                    last_callback_data = callback_data
                elif edit_result.retry_after_s > 0:
                    edit_backoff_until = max(edit_backoff_until, time.time() + edit_result.retry_after_s)

            await asyncio.sleep(ctx.cfg.progress_refresh_s)
    except asyncio.CancelledError:
        raise
    finally:
        if ctx.batch_monitor_tasks.get(user_id) is asyncio.current_task():
            ctx.batch_monitor_tasks.pop(user_id, None)


def start_batch_monitor(ctx: HandlerContext, user_id: int, initial_chat_id: int) -> None:
    """Start a per-user consolidated live monitor if one is not already running."""
    if initial_chat_id <= 0:
        return
    existing = ctx.batch_monitor_tasks.get(user_id)
    if existing and not existing.done():
        if ctx.batch_monitor_messages.get(user_id) is not None:
            return
        existing.cancel()
    task = asyncio.create_task(
        _run_batch_monitor_loop(ctx, user_id, initial_chat_id),
        name=f"batch-monitor:{user_id}",
    )
    ctx.batch_monitor_tasks[user_id] = task


async def stop_batch_monitor(ctx: HandlerContext, user_id: int) -> None:
    """Cancel the per-user consolidated live monitor and delete its message."""
    task = ctx.batch_monitor_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await _delete_batch_monitor_message(ctx, user_id)
    for key in [key for key in list(ctx.batch_monitor_data) if key[0] == user_id]:
        ctx.batch_monitor_data.pop(key, None)


# ---------------------------------------------------------------------------
# Tracker lifecycle (need ctx for progress_tasks, pending_tracker_tasks, qbt)
# ---------------------------------------------------------------------------


def start_progress_tracker(
    ctx: HandlerContext,
    user_id: int,
    torrent_hash: str,
    tracker_msg: Any,
    title: str,
    *,
    header: str | None = None,
    post_add_rows: list[list[Any]] | None = None,  # TODO: unused after headless monitor refactor
    chat_id: int = 0,
) -> None:
    """Launch a progress-tracking asyncio task for a torrent, keyed by (uid, hash).

    ``tracker_msg`` may be ``None`` for headless tracking — in that mode the tracker
    feeds the Command Center batch monitor without editing a per-download message.
    When headless, ``chat_id`` must be supplied so the batch monitor can be started.
    """
    key = (user_id, torrent_hash.lower())
    existing = ctx.progress_tasks.get(key)
    if existing and not existing.done():
        existing.cancel()

    task = asyncio.create_task(
        track_download_progress(
            ctx,
            user_id,
            torrent_hash,
            tracker_msg,
            title,
            header=header,
            post_add_rows=post_add_rows,
        ),
        name=f"progress:{user_id}:{torrent_hash.lower()}",
    )
    ctx.progress_tasks[key] = task
    if tracker_msg is not None:
        resolved_chat_id = int(getattr(tracker_msg, "chat_id", 0) or 0)
    else:
        resolved_chat_id = int(chat_id or 0)
    if resolved_chat_id > 0:
        start_batch_monitor(ctx, user_id, resolved_chat_id)


def start_pending_progress_tracker(
    ctx: HandlerContext,
    user_id: int,
    title: str,
    category: str,
    base_msg: Any,
    *,
    header: str | None = None,
    post_add_rows: list[list[Any]] | None = None,  # TODO: unused after headless monitor refactor
    headless: bool = False,
) -> None:
    """Launch a pending-monitor task that waits for qBT to assign a hash, then attaches a live monitor.

    When ``headless=True``, the tracker will not send or edit any user-visible
    monitor message once the hash resolves; it just starts feeding the Command
    Center batch monitor. Timeout errors are logged instead of posted to the chat.
    """
    key = (user_id, category.lower(), title.strip().lower())
    existing = ctx.pending_tracker_tasks.get(key)
    if existing and not existing.done():
        return

    task = asyncio.create_task(
        attach_progress_tracker_when_ready(
            ctx,
            user_id,
            title,
            category,
            base_msg,
            header=header,
            post_add_rows=post_add_rows,
            headless=headless,
        )
    )
    ctx.pending_tracker_tasks[key] = task


async def attach_progress_tracker_when_ready(
    ctx: HandlerContext,
    user_id: int,
    title: str,
    category: str,
    base_msg: Any,
    *,
    header: str | None = None,
    post_add_rows: list[list[Any]] | None = None,  # TODO: unused after headless monitor refactor
    headless: bool = False,
) -> None:
    """Poll qBT until the torrent hash is available, then start a live progress tracker.

    When ``headless=True``, no user-visible monitor message is sent — the tracker
    simply starts a headless progress tracker whose data flows into the Command
    Center batch monitor. The ``base_msg``'s chat_id is still used so the batch
    monitor knows where to render.
    """
    key = (user_id, category.lower(), title.strip().lower())
    try:
        torrent_hash = await resolve_hash_by_name(ctx, title, category, wait_s=35)
        if not torrent_hash:
            if not headless:
                try:
                    sent = await base_msg.reply_text(
                        "\u26a0\ufe0f <b>Monitor Could Not Attach</b>\n\n"
                        "Could not find the torrent hash after 35s.\n"
                        "Use <code>/active</code> to check download status.",
                        parse_mode=_PM,
                    )
                    track_ephemeral_message(ctx, user_id, sent)
                except Exception:
                    LOG.warning("Failed to send pending tracker timeout notification", exc_info=True)
            else:
                LOG.info(
                    "Headless pending tracker timeout for %r (%s) — no user message sent",
                    title,
                    category,
                )
            try:
                ctx.store.log_health_event(
                    user_id,
                    None,
                    "pending_tracker_timeout",
                    "warn",
                    json.dumps({"title": title, "category": category, "wait_s": 35, "headless": headless}),
                    title,
                )
            except Exception:
                LOG.debug("Failed to log pending_tracker_timeout health event", exc_info=True)
            return

        if headless:
            # No inline monitor message — feed the Command Center batch monitor directly.
            chat_id = int(getattr(base_msg, "chat_id", 0) or 0)
            start_progress_tracker(
                ctx,
                user_id,
                torrent_hash,
                None,
                title,
                header=header,
                post_add_rows=post_add_rows,
                chat_id=chat_id,
            )
            return

        # Legacy non-headless path — edit or reply with a monitor-attached message.
        stop_kb = stop_download_keyboard(torrent_hash, post_add_rows=post_add_rows)
        initial_text = "<b>\U0001f4e1 Live Monitor Attached</b>\n<i>Tracking download progress\u2026</i>"
        if header:
            initial_text = f"{header}\n\n{initial_text}"
            try:
                await base_msg.edit_text(initial_text, reply_markup=stop_kb, parse_mode=_PM)
            except Exception:
                LOG.debug("Failed to edit base_msg for pending monitor; falling back to reply", exc_info=True)
                base_msg = await base_msg.reply_text(initial_text, reply_markup=stop_kb, parse_mode=_PM)
        else:
            base_msg = await base_msg.reply_text(initial_text, reply_markup=stop_kb, parse_mode=_PM)
        start_progress_tracker(
            ctx,
            user_id,
            torrent_hash,
            base_msg,
            title,
            header=header,
            post_add_rows=post_add_rows,
        )
    except Exception:
        LOG.warning("Deferred live monitor attach failed", exc_info=True)
    finally:
        ctx.pending_tracker_tasks.pop(key, None)


# ---------------------------------------------------------------------------
# Main tracking loop
# ---------------------------------------------------------------------------


async def track_download_progress(
    ctx: HandlerContext,
    user_id: int,
    torrent_hash: str,
    tracker_msg: Any,
    title: str,
    *,
    header: str | None = None,
    post_add_rows: list[list[Any]] | None = None,
) -> None:
    """The main progress-tracking loop: polls qBT and feeds the shared batch monitor state."""
    key = (user_id, torrent_hash.lower())
    start = time.time()
    tick = 0
    qbt_error_streak = 0

    smooth_progress_pct: float | None = None
    smooth_dls: float | None = None
    smooth_uls: float | None = None
    alpha = ctx.cfg.progress_smoothing_alpha

    # Stall detection state
    metadata_stall_start: float | None = None
    zero_progress_start: float | None = None
    stall_warned: bool = False

    try:
        while True:
            # If another tracker replaced us in progress_tasks, exit gracefully.
            incumbent = ctx.progress_tasks.get(key)
            if incumbent is not None and incumbent is not asyncio.current_task():
                return

            elapsed = time.time() - start
            if elapsed > ctx.cfg.progress_track_timeout_s:
                # Fetch final state for diagnostic info
                state_line = ""
                try:
                    final_info = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
                    if final_info:
                        final_state = str(final_info.get("state") or "unknown")
                        final_progress = float(final_info.get("progress", 0) or 0)
                        final_speed = int(final_info.get("dlspeed", 0) or 0)
                        state_line = (
                            f"\n\n<b>Last Known State:</b>\n"
                            f"State: <code>{_h(final_state)}</code>\n"
                            f"Progress: {final_progress * 100:.1f}%\n"
                            f"Speed: {human_size(final_speed)}/s"
                        )
                except Exception:
                    state_line = "\n\n<i>Could not retrieve final torrent state.</i>"

                await tracker_send_fallback(
                    ctx,
                    tracker_msg,
                    f"<b>\u23f1 Monitor Timed Out</b>\nUse <code>/active</code> for current status.{state_line}",
                )
                break

            try:
                info = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
                qbt_error_streak = 0
            except Exception:
                qbt_error_streak += 1
                LOG.warning("Live monitor qBittorrent poll failed (%d/5)", qbt_error_streak, exc_info=True)
                if qbt_error_streak >= 5:
                    await tracker_send_fallback(
                        ctx,
                        tracker_msg,
                        "<b>\u26a0\ufe0f Monitor Paused</b>\n<i>Repeated qBittorrent errors.</i> Use <code>/active</code> for status.",
                    )
                    break
                await asyncio.sleep(ctx.cfg.progress_refresh_s)
                tick += 1
                continue

            if not info:
                if elapsed < 20:
                    await asyncio.sleep(ctx.cfg.progress_refresh_s)
                    tick += 1
                    continue
                notice = (
                    "<b>\u26a0\ufe0f Torrent Not Found</b>\n"
                    "<i>Lost track of download — torrent not found in qBittorrent.</i>\n"
                    "This can happen if qBittorrent rejected the torrent or the magnet link was invalid.\n\n"
                    "Check qBittorrent WebUI directly, or use <code>/active</code>."
                )
                await tracker_send_fallback(ctx, tracker_msg, notice)
                try:
                    ctx.store.log_health_event(
                        user_id,
                        torrent_hash,
                        "hash_resolve_fail",
                        "error",
                        json.dumps({"elapsed_s": int(elapsed)}),
                        title,
                    )
                except Exception:
                    LOG.debug("Failed to log hash_resolve_fail health event", exc_info=True)
                break

            raw_progress_pct = max(0.0, min(100.0, float(info.get("progress", 0.0) or 0.0) * 100.0))
            raw_dls = max(0.0, float(int(info.get("dlspeed", 0) or 0)))
            raw_uls = max(0.0, float(int(info.get("upspeed", 0) or 0)))

            if smooth_progress_pct is None or smooth_dls is None or smooth_uls is None:
                smooth_progress_pct = raw_progress_pct
                smooth_dls = raw_dls
                smooth_uls = raw_uls
            else:
                smooth_progress_pct = ((1.0 - alpha) * smooth_progress_pct) + (alpha * raw_progress_pct)
                smooth_dls = ((1.0 - alpha) * smooth_dls) + (alpha * raw_dls)
                smooth_uls = ((1.0 - alpha) * smooth_uls) + (alpha * raw_uls)

            # --- Stall detection ---
            current_ts = time.time()
            state = str(info.get("state") or "")
            progress = float(info.get("progress", 0) or 0)
            dlspeed = int(info.get("dlspeed", 0) or 0)

            # Metadata stall: stuck in metaDL for too long
            if state in ("metaDL", "forcedMetaDL"):
                if metadata_stall_start is None:
                    metadata_stall_start = current_ts
                elif not stall_warned and (current_ts - metadata_stall_start) >= ctx.cfg.stall_metadata_warn_s:
                    stall_warned = True
                    elapsed_s = int(current_ts - metadata_stall_start)
                    tracker_detail: dict[str, Any] = {
                        "state": state,
                        "elapsed_s": elapsed_s,
                        "reannounce_attempted": True,
                    }
                    try:
                        await asyncio.to_thread(ctx.qbt.reannounce_torrent, torrent_hash)
                    except Exception:
                        tracker_detail["reannounce_attempted"] = False
                        LOG.warning("Reannounce failed for stalled torrent %s", torrent_hash, exc_info=True)
                    try:
                        trackers = await asyncio.to_thread(ctx.qbt.get_torrent_trackers, torrent_hash)
                        failed = [t for t in trackers if t.get("status") == 4]
                        tracker_detail["failed_trackers"] = len(failed)
                        tracker_detail["total_trackers"] = len(trackers)
                        tracker_msg_text = (
                            f"{len(failed)}/{len(trackers)} trackers failing" if failed else "trackers responding"
                        )
                    except Exception:
                        tracker_msg_text = "tracker status unknown"
                    warn_text = (
                        f"\u26a0\ufe0f <b>Download Stalled</b>\n\n"
                        f"<code>{_h(title)}</code>\n\n"
                        f"Stuck getting metadata for {elapsed_s // 60}m {elapsed_s % 60}s ({tracker_msg_text})\n\n"
                        f"Attempted tracker reannounce \u2014 if this doesn\u2019t help, you may want to cancel and try a different torrent."
                    )
                    await tracker_send_fallback(ctx, tracker_msg, warn_text)
                    try:
                        ctx.store.log_health_event(
                            user_id,
                            torrent_hash,
                            "stall_detected",
                            "warn",
                            json.dumps(tracker_detail),
                            title,
                        )
                    except Exception:
                        pass
            else:
                metadata_stall_start = None

            # Zero-progress stall: downloading but no actual progress
            if state in ("downloading", "forcedDL", "stalledDL") and progress < 0.01 and dlspeed == 0:
                if zero_progress_start is None:
                    zero_progress_start = current_ts
                elif not stall_warned and (current_ts - zero_progress_start) >= ctx.cfg.stall_zero_progress_warn_s:
                    stall_warned = True
                    elapsed_s = int(current_ts - zero_progress_start)
                    warn_text = (
                        f"\u26a0\ufe0f <b>Download Stalled</b>\n\n"
                        f"<code>{_h(title)}</code>\n\n"
                        f"Download at 0% with no speed for {elapsed_s // 60}m {elapsed_s % 60}s\n\n"
                        f"You may want to cancel and try a different torrent."
                    )
                    await tracker_send_fallback(ctx, tracker_msg, warn_text)
                    try:
                        ctx.store.log_health_event(
                            user_id,
                            torrent_hash,
                            "stall_detected",
                            "warn",
                            json.dumps({"state": state, "elapsed_s": elapsed_s, "progress": progress}),
                            title,
                        )
                    except Exception:
                        pass
            elif progress > 0.01 or dlspeed > 0:
                zero_progress_start = None
                if stall_warned:
                    stall_warned = False  # Reset warning flag if progress resumes

            ctx.batch_monitor_data[key] = {
                "title": title,
                "info": dict(info),
                "progress_pct": smooth_progress_pct,
                "dls_bps": int(smooth_dls),
            }

            if is_complete_torrent(info):
                ctx.batch_monitor_data.pop(key, None)
                done_text = (
                    render_progress_text(
                        title,
                        info,
                        tick,
                        progress_pct=100.0,
                        dls_bps=int(raw_dls),
                        uls_bps=int(raw_uls),
                        header=header,
                    )
                    + "\n<b>\u2705 Download Complete</b>"
                )
                await safe_tracker_edit(tracker_msg, done_text, reply_markup=None)
                media_path = str(info.get("content_path") or info.get("save_path") or "").strip()
                category = str(info.get("category") or "")
                security = await _apply_completion_security_gate(
                    ctx,
                    user_id=user_id,
                    torrent_hash=torrent_hash,
                    name=title,
                    media_path=media_path,
                )
                await asyncio.to_thread(ctx.store.mark_completion_notified, torrent_hash, title, user_id)
                if not security.allowed:
                    if security.notice_text:
                        await tracker_send_fallback(ctx, tracker_msg, security.notice_text)
                    if tracker_msg is not None:
                        try:
                            await tracker_msg.delete()
                        except Exception:
                            pass
                    break
                media_path = security.media_path
                # Organize download into Plex-standard structure.
                try:
                    org_result = await asyncio.to_thread(
                        _organize_download,
                        media_path,
                        category,
                        ctx.cfg.tv_path,
                        ctx.cfg.movies_path,
                    )
                except OSError as e:
                    if e.errno == _errno.ENOSPC:
                        LOG.error("Disk full during organize for %s: %s", title, e)
                        await tracker_send_fallback(
                            ctx,
                            tracker_msg,
                            f"\u274c <b>Disk Full</b>\n\n"
                            f"<code>{_h(title)}</code>\n\n"
                            f"Cannot move file to Plex library \u2014 disk is full.\n"
                            f"Free up space and the file will be organized on the next completion poll.",
                        )
                        try:
                            ctx.store.log_health_event(
                                user_id,
                                torrent_hash,
                                "organize_error",
                                "critical",
                                json.dumps({"error": "ENOSPC", "path": media_path}),
                                title,
                            )
                        except Exception:
                            pass
                        org_result = None
                    else:
                        raise
                if org_result is not None and org_result.moved:
                    media_path = org_result.new_path
                    # Files have been moved — remove the now-stale qBT entry.
                    try:
                        await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=False)
                        LOG.info("Removed organised torrent from qBT: %s", torrent_hash)
                    except Exception:
                        LOG.debug("Failed to remove organised torrent %s from qBT", torrent_hash, exc_info=True)
                if org_result is not None and not org_result.moved and "unknown category" in org_result.summary:
                    LOG.warning("Unknown category '%s' for torrent %s", category, title)
                    try:
                        ctx.store.log_health_event(
                            user_id,
                            torrent_hash,
                            "category_unknown",
                            "warn",
                            json.dumps({"category": category, "save_path": media_path}),
                            title,
                        )
                    except Exception:
                        LOG.debug("Failed to log category_unknown health event", exc_info=True)
                # Trigger a Plex library scan for the (possibly new) download path.
                plex_added = False
                plex_failed = False
                if ctx.plex.ready() and media_path:
                    try:
                        plex_msg = await asyncio.to_thread(ctx.plex.purge_deleted_path, media_path)
                        LOG.info("Post-download Plex refresh+trash: %s", plex_msg)
                        plex_added = True
                    except Exception:
                        LOG.warning("Post-download Plex refresh failed for %s", media_path, exc_info=True)
                        plex_failed = True
                notif_text = f"<b>\u2705 Download Complete</b>\n<code>{_h(title)}</code>"
                if org_result is not None and org_result.moved:
                    notif_text += f"\n<b>\U0001f4c1 Organized:</b> {_h(org_result.summary)}"
                if plex_added:
                    notif_text += "\n\n<b>\U0001f4da Added to Plex</b>"
                elif plex_failed:
                    notif_text += "\n\n⚠️ <b>Plex scan failed</b> — may need manual refresh"
                if org_result is not None:
                    await tracker_send_fallback(ctx, tracker_msg, notif_text)
                # Delete the monitor message so it doesn't linger in the chat.
                if tracker_msg is not None:
                    try:
                        await tracker_msg.delete()
                    except Exception:
                        pass
                break

            tick += 1
            await asyncio.sleep(ctx.cfg.progress_refresh_s)

    except asyncio.CancelledError:
        return
    except Exception:
        LOG.warning("Live progress tracker failed", exc_info=True)
        await tracker_send_fallback(
            ctx,
            tracker_msg,
            "<b>\u26a0\ufe0f Monitor Error</b>\n<i>Unexpected error.</i> Use <code>/active</code> for status.",
        )
    finally:
        ctx.batch_monitor_data.pop(key, None)
        ctx.progress_tasks.pop(key, None)
        # If this was the active download, advance to the next queued torrent.
        try:
            await _advance_download_queue(ctx, expected_hash=torrent_hash.lower())
        except Exception:
            LOG.warning("Failed to advance download queue", exc_info=True)


# ---------------------------------------------------------------------------
# Sequential download queue — advance to next queued torrent
# ---------------------------------------------------------------------------


async def _advance_download_queue(ctx: HandlerContext, *, expected_hash: str | None = None) -> None:
    """Resume the next queued torrent after the active download finishes or is cancelled.

    If *expected_hash* is given, only advance when the current active hash still
    matches — this prevents a double-advance TOCTOU race when multiple callers
    detect the same completion.
    """
    async with ctx.download_queue_lock:
        if expected_hash is not None and ctx.active_download_hash != expected_hash:
            return  # already advanced by another caller
        ctx.active_download_hash = None
        requeue: list[dict[str, Any]] = []
        try:
            while not ctx.download_queue.empty():
                entry = ctx.download_queue.get_nowait()
                torrent_hash = entry["hash"]
                name = entry["name"]
                # Verify the torrent still exists in qBT (user may have cancelled it).
                try:
                    info = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
                except Exception:
                    # qBT unreachable — keep the entry so we can retry later.
                    requeue.append(entry)
                    LOG.warning("Queue advance: qBT unreachable checking %s, re-queuing", torrent_hash)
                    continue
                if not info:
                    LOG.info("Queued torrent %s (%s) no longer in qBT, skipping", torrent_hash, name)
                    continue
                # Resume this torrent — it becomes the new active download.
                ctx.active_download_hash = torrent_hash
                try:
                    await asyncio.to_thread(ctx.qbt.resume_torrents, torrent_hash)
                    LOG.info("Queue advanced: resumed %s (%s)", torrent_hash, name)
                except Exception:
                    LOG.warning("Failed to resume queued torrent %s, re-queuing", torrent_hash, exc_info=True)
                    ctx.active_download_hash = None
                    requeue.append(entry)
                    continue
                break
        finally:
            # Put back any entries that failed due to qBT errors.
            for entry in requeue:
                ctx.download_queue.put_nowait(entry)


async def _remove_from_download_queue(ctx: HandlerContext, torrent_hash: str) -> None:
    """Remove a specific torrent from the download queue (drain + re-add others)."""
    target = torrent_hash.lower()
    async with ctx.download_queue_lock:
        kept: list[dict[str, Any]] = []
        while not ctx.download_queue.empty():
            try:
                entry = ctx.download_queue.get_nowait()
            except Exception:
                break
            if entry["hash"] != target:
                kept.append(entry)
        for entry in kept:
            await ctx.download_queue.put(entry)


# ---------------------------------------------------------------------------
# Background completion poller
# ---------------------------------------------------------------------------


async def completion_poller_job(ctx: HandlerContext, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job that checks ALL torrents for completions missed by the live monitor."""
    if not ctx.app:
        return
    try:
        torrents = await asyncio.to_thread(ctx.qbt.list_torrents, filter_name="completed", limit=200)
    except Exception:
        LOG.warning("Completion poller: failed to list torrents", exc_info=True)
        return

    now_ts_val = int(time.time())
    COMPLETION_RECENCY_S = 86400  # 24 hours

    for info in torrents:
        torrent_hash = str(info.get("hash") or "").strip().lower()
        if not torrent_hash:
            continue

        # In-memory dedup (fast path — avoids DB query for already-seen hashes)
        if torrent_hash in _poller_seen_hashes:
            continue

        if not is_complete_torrent(info):
            continue

        # Time-bounded: skip completions older than 24h (handled by _recover_missed_completions)
        completion_on = int(info.get("completion_on", 0) or 0)
        if completion_on > 0 and (now_ts_val - completion_on) > COMPLETION_RECENCY_S:
            _poller_seen_hashes.add(torrent_hash)
            continue

        already = await asyncio.to_thread(ctx.store.is_completion_notified, torrent_hash)
        if already:
            _poller_seen_hashes.add(torrent_hash)
            continue

        name = str(info.get("name") or "Unknown")
        size = int(info.get("size", 0) or info.get("total_size", 0) or 0)
        category = str(info.get("category") or "")

        media_path = str(info.get("content_path") or info.get("save_path") or "").strip()

        # File-list heuristics at completion — catches magnets that skipped inspection
        try:
            raw_files = await asyncio.to_thread(ctx.qbt.get_torrent_files, torrent_hash)
            file_names = _torrent_file_names(raw_files)
            file_sizes_list = _torrent_file_sizes(raw_files)
        except Exception:
            file_names = []
            file_sizes_list = []
            raw_files = []
        if file_names:
            cat_lower = category.lower()
            mt = "episode" if cat_lower in ("tv", "shows", "tv shows") else "movie"
            # Read NFO content (if any, ≤50KB) for danger-pattern scan.
            nfo_text = _read_torrent_nfo(raw_files, media_path)
            # Fetch tracker URLs for suspicious-tracker scan.
            try:
                tracker_rows = await asyncio.to_thread(ctx.qbt.get_torrent_trackers, torrent_hash)
                tracker_urls = [str(t.get("url") or "") for t in (tracker_rows or [])]
            except Exception:
                tracker_urls = None
            completion_scan = scan_download(
                name=name,
                size_bytes=size,
                quality_tier=quality_tier(name),
                media_type=mt,
                files=file_names,
                file_sizes=file_sizes_list,
                nfo_text=nfo_text,
                tracker_urls=tracker_urls,
            )
            if completion_scan.is_blocked:
                try:
                    await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
                except Exception:
                    LOG.warning("Failed to delete blocked torrent at completion: %s", torrent_hash, exc_info=True)
                try:
                    await asyncio.to_thread(
                        ctx.store.log_malware_block, torrent_hash, name, "download", completion_scan.reasons
                    )
                except Exception:
                    pass
                top_signals = sorted(completion_scan.signals, key=lambda s: s.points, reverse=True)[:5]
                signal_lines = "\n".join(
                    f"• <code>{_h(s.signal_id)}</code> (+{s.points}) {_h(s.detail)}" for s in top_signals
                )
                notice = (
                    f"🚫 <b>Blocked</b> (Score: {completion_scan.score}/100)\n"
                    f"<code>{_h(name)}</code>\n\n"
                    f"<b>Signals:</b>\n{signal_lines}"
                )
                await asyncio.to_thread(ctx.store.mark_completion_notified, torrent_hash, name)
                for uid in ctx.cfg.allowed_user_ids:
                    try:
                        sent = await ctx.app.bot.send_message(chat_id=uid, text=notice, parse_mode=_PM)
                        track_ephemeral_message(ctx, uid, sent)
                    except Exception:
                        LOG.warning(
                            "Completion poller: failed to send heuristic block alert to user %s", uid, exc_info=True
                        )
                _poller_seen_hashes.add(torrent_hash)
                continue

        security = await _apply_completion_security_gate(
            ctx,
            user_id=0,
            torrent_hash=torrent_hash,
            name=name,
            media_path=media_path,
        )
        await asyncio.to_thread(ctx.store.mark_completion_notified, torrent_hash, name)
        if not security.allowed:
            if security.notice_text:
                for uid in ctx.cfg.allowed_user_ids:
                    try:
                        sent = await ctx.app.bot.send_message(chat_id=uid, text=security.notice_text, parse_mode=_PM)
                        track_ephemeral_message(ctx, uid, sent)
                    except Exception:
                        LOG.warning("Completion poller: failed to send malware alert to user %s", uid, exc_info=True)
            _poller_seen_hashes.add(torrent_hash)
            continue
        media_path = security.media_path
        # Organize download into Plex-standard structure.
        try:
            org_result = await asyncio.to_thread(
                _organize_download,
                media_path,
                category,
                ctx.cfg.tv_path,
                ctx.cfg.movies_path,
            )
        except OSError as e:
            if e.errno == _errno.ENOSPC:
                LOG.error("Disk full during organize for %s: %s", name, e)
                for uid in ctx.cfg.allowed_user_ids:
                    try:
                        await ctx.app.bot.send_message(
                            chat_id=uid,
                            text=f"\u274c <b>Disk Full</b>\n\n"
                            f"<code>{_h(name)}</code>\n\n"
                            f"Cannot move file to Plex library \u2014 disk is full.",
                            parse_mode=_PM,
                        )
                    except Exception:
                        pass
                try:
                    ctx.store.log_health_event(
                        0,
                        torrent_hash,
                        "organize_error",
                        "critical",
                        json.dumps({"error": "ENOSPC", "path": media_path}),
                        name,
                    )
                except Exception:
                    pass
                org_result = None
            else:
                raise
        if org_result is not None and org_result.moved:
            media_path = org_result.new_path
            # Files have been moved — remove the now-stale qBT entry.
            try:
                await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=False)
                LOG.info("Removed organised torrent from qBT: %s", torrent_hash)
            except Exception:
                LOG.debug("Failed to remove organised torrent %s from qBT", torrent_hash, exc_info=True)
        if org_result is not None and not org_result.moved and "unknown category" in org_result.summary:
            LOG.warning("Unknown category '%s' for torrent %s", category, name)
            try:
                ctx.store.log_health_event(
                    0,
                    torrent_hash,
                    "category_unknown",
                    "warn",
                    json.dumps({"category": category, "save_path": media_path}),
                    name,
                )
            except Exception:
                LOG.debug("Failed to log category_unknown health event", exc_info=True)

        # Trigger Plex scan.
        plex_added = False
        plex_failed = False
        if ctx.plex.ready() and media_path:
            try:
                plex_msg = await asyncio.to_thread(ctx.plex.refresh_for_path, media_path)
                LOG.info("Completion poller Plex refresh: %s", plex_msg)
                plex_added = True
            except Exception:
                LOG.warning("Completion poller Plex refresh failed for %s", media_path, exc_info=True)
                plex_failed = True

        # Build notification.
        lines = ["<b>\u2705 Download Complete</b>", f"<code>{_h(name)}</code>"]
        if category:
            lines.append(f"Category: <b>{_h(category)}</b>")
        if size > 0:
            lines.append(f"Size: <b>{human_size(size)}</b>")
        if org_result is not None and org_result.moved:
            lines.append(f"<b>\U0001f4c1 Organized:</b> {_h(org_result.summary)}")
        if plex_added:
            lines.append("")
            lines.append("<b>\U0001f4da Added to Plex</b>")
        elif plex_failed:
            lines.append("")
            lines.append("⚠️ <b>Plex scan failed</b> — may need manual refresh")
        text = "\n".join(lines)

        # Send to all allowed users.
        for uid in ctx.cfg.allowed_user_ids:
            try:
                sent = await ctx.app.bot.send_message(chat_id=uid, text=text, parse_mode=_PM)
                track_ephemeral_message(ctx, uid, sent)
            except Exception:
                LOG.warning("Completion poller: failed to notify user %s for %s", uid, name, exc_info=True)

        LOG.info("Completion poller: notified for '%s' (hash=%s)", name, torrent_hash)
        _poller_seen_hashes.add(torrent_hash)

        # If this was the active download, advance the queue.
        try:
            await _advance_download_queue(ctx, expected_hash=torrent_hash)
        except Exception:
            LOG.warning("Completion poller: failed to advance download queue", exc_info=True)

    # Housekeeping: clean up old records once per run.
    try:
        await asyncio.to_thread(ctx.store.cleanup_old_completion_records)
    except Exception:
        pass

    # Housekeeping: if the active download no longer exists in qBT
    # (e.g. deleted via WebUI), advance the queue so it doesn't stay stuck.
    active = ctx.active_download_hash
    if active:
        try:
            info = await asyncio.to_thread(ctx.qbt.get_torrent, active)
            if not info:
                LOG.info("Active download %s no longer in qBT, advancing queue", active)
                await _advance_download_queue(ctx, expected_hash=active)
        except Exception:
            pass  # qBT unreachable — leave active hash for next poll

    # Housekeeping: purge qBT entries stuck in missingFiles state.
    await _cleanup_missing_files_torrents(ctx)


async def _cleanup_missing_files_torrents(ctx: HandlerContext) -> None:
    """Remove torrents in 'missingFiles' state from qBittorrent.

    These are stale entries where the organizer already moved files to
    the Plex library structure but the original qBT entry was never
    cleaned up.  Also triggers a Plex empty-trash pass when any entries
    are removed so ghost metadata gets purged.
    """
    try:
        all_torrents = await asyncio.to_thread(ctx.qbt.list_torrents)
    except Exception:
        LOG.warning("missingFiles cleanup: failed to list torrents", exc_info=True)
        return
    missing = [t for t in all_torrents if str(t.get("state") or "") == "missingFiles"]
    if not missing:
        return
    removed = 0
    affected_sections: set[str] = set()
    for t in missing:
        h = str(t.get("hash") or "").strip()
        name = str(t.get("name") or "unknown")
        category = str(t.get("category") or "").strip().lower()
        if not h:
            continue
        try:
            await asyncio.to_thread(ctx.qbt.delete_torrent, h, delete_files=False)
            removed += 1
            LOG.info("Purged missingFiles torrent: %s (%s)", name, h)
        except Exception:
            LOG.debug("Failed to purge missingFiles torrent %s", h, exc_info=True)
            continue
        if category in ("tv", "shows", "tv shows"):
            affected_sections.add("show")
        elif category in ("movies", "movie", "films"):
            affected_sections.add("movie")
    if removed:
        LOG.info("Purged %d missingFiles torrent(s) from qBT", removed)
    # Ask Plex to scan + empty trash for affected section types.
    if affected_sections and ctx.plex.ready():
        try:
            refreshed = await asyncio.to_thread(ctx.plex.refresh_all_by_type, sorted(affected_sections))
            LOG.info("Plex trash cleanup after missingFiles purge: %s", refreshed)
        except Exception:
            LOG.debug("Plex trash cleanup after missingFiles purge failed", exc_info=True)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def is_direct_torrent_link(url: str) -> bool:
    """Return True if url is a magnet link or direct .torrent download."""
    u = (url or "").strip()
    if not u:
        return False
    low = u.lower()
    if low.startswith("magnet:?"):
        return True
    if not (low.startswith("http://") or low.startswith("https://")):
        return False

    parsed = urllib.parse.urlparse(u)
    path = (parsed.path or "").lower()
    if path.endswith(".torrent"):
        return True

    # Heuristic: known direct download endpoints
    if "download" in path and "torrent" in path:
        return True
    if path.endswith("/dl") or path.endswith("/download"):
        return True

    return False


def result_to_url(result_row: dict[str, Any]) -> str:
    """Convert a search result row into a torrent/magnet URL suitable for qBT."""
    h = (result_row.get("hash") or "").strip().lower()
    name = (result_row.get("name") or "torrent").strip()
    if re.fullmatch(r"[a-f0-9]{40}", h):
        return f"magnet:?xt=urn:btih:{h}&dn={urllib.parse.quote(name)}"

    for k in ("file_url", "url"):
        v = (result_row.get(k) or "").strip()
        if v and is_direct_torrent_link(v):
            return v

    # descr_link is usually a webpage, not a torrent payload. Only allow if it is direct.
    d = (result_row.get("descr_link") or "").strip()
    if d and is_direct_torrent_link(d):
        return d

    raise RuntimeError("Result source is a webpage, not a direct torrent/magnet link. Pick a different result/source.")


def extract_hash(row: dict[str, Any], url: str) -> str | None:
    """Extract the torrent info-hash from either the result row or the magnet URL."""
    h = str(row.get("hash") or "").strip().lower()
    if re.fullmatch(r"[a-f0-9]{40}", h):
        return h

    m = re.search(r"btih:([A-Fa-f0-9]{40})", url)
    if m:
        return m.group(1).lower()

    return None


def scan_download_candidate(
    result_row: dict[str, Any],
    *,
    media_type: str,
    files: list[str] | None = None,
) -> tuple[str, str | None, Any]:
    """Apply the shared download-time malware gate and return URL/hash metadata.

    This helper is side-effect free so background runners can reuse the same
    candidate validation path as manual downloads without sending Telegram
    messages or touching qBittorrent.
    """
    torrent_name = str(result_row.get("name") or "")
    torrent_size = int(result_row.get("size") or result_row.get("fileSize") or 0)
    uploader = str(result_row.get("uploader") or "").strip() or None
    malware_scan = scan_download(
        name=torrent_name,
        size_bytes=torrent_size,
        quality_tier=quality_tier(torrent_name),
        media_type=media_type,
        files=files or [],
        uploader=uploader,
    )
    url = result_to_url(result_row)
    torrent_hash = extract_hash(result_row, url)
    return url, torrent_hash, malware_scan


async def resolve_hash_by_name(ctx: HandlerContext, title: str, category: str, wait_s: int = 20) -> str | None:
    """Poll qBT until a torrent matching *title* appears, returning its hash."""
    deadline = time.time() + wait_s
    want = title.strip().lower()
    want_norm = normalize_title(title)
    while time.time() < deadline:
        try:
            rows = await asyncio.to_thread(
                ctx.qbt.list_torrents,
                category=category,
                sort="added_on",
                reverse=True,
                limit=150,
            )
            candidates: list[tuple[float, str]] = []
            now_epoch = time.time()
            RECENCY_WINDOW_S = 60
            for row in rows:
                name = str(row.get("name") or "").strip().lower()
                if not name:
                    continue
                h = str(row.get("hash") or "").strip().lower()
                if not re.fullmatch(r"[a-f0-9]{40}", h):
                    continue
                added_on = int(row.get("added_on", 0) or 0)
                is_recent = added_on == 0 or (now_epoch - added_on) <= RECENCY_WINDOW_S
                # Priority 1: exact match (no recency filter)
                if name == want:
                    return h
                # Priority 2: normalized title match (no recency filter)
                name_norm = normalize_title(name)
                if want_norm and name_norm == want_norm:
                    return h
                # Priority 3: want contained in name (recency required)
                if is_recent and want in name and len(want) >= len(name) * 0.4:
                    candidates.append((len(want) / len(name), h))
                # Priority 4: name contained in want (recency required)
                elif is_recent and name in want and len(name) >= len(want) * 0.6:
                    candidates.append((len(name) / len(want) * 0.8, h))
            if candidates:
                candidates.sort(key=lambda c: c[0], reverse=True)
                return candidates[0][1]
        except Exception:
            LOG.warning("Hash lookup by name failed", exc_info=True)
        await asyncio.sleep(0.6)
    return None


async def do_add(
    ctx: HandlerContext,
    user_id: int,
    search_id: str,
    idx: int,
    media_choice: str,
) -> DoAddResult:
    """Fast phase: pre-flight checks + qbt.add_url.  Returns in ~1-2s.

    The slow work (hash resolution, file inspection, malware scan, queue
    management) is deferred to :func:`do_add_background`.
    """
    payload = ctx.store.get_search(user_id, search_id)
    if not payload:
        raise RuntimeError("Search result not found")

    choice = normalize_media_choice(media_choice)
    if choice not in {"movies", "tv"}:
        raise RuntimeError("Media type must be Movies or TV")

    row = ctx.store.get_result(user_id, search_id, idx)
    if not row:
        raise RuntimeError("Search result not found")

    # Pre-flight checks with short-lived cache to avoid repeating for each
    # episode when adding multiple in a batch.
    now = time.time()

    cached_cat = _preflight_cache.get("categories")
    if cached_cat and (now - cached_cat[1]) < _PREFLIGHT_CACHE_TTL:
        cat_result = cached_cat[0]
    else:
        try:
            cat_result = await asyncio.wait_for(asyncio.to_thread(ensure_media_categories, ctx), timeout=10.0)
        except TimeoutError:
            raise RuntimeError("Storage/category check timed out (10s). Check qBittorrent connectivity.")
        _preflight_cache["categories"] = (cat_result, now)

    cached_transport = _preflight_cache.get("transport")
    if cached_transport and (now - cached_transport[1]) < _PREFLIGHT_CACHE_TTL:
        transport_result = cached_transport[0]
    else:
        try:
            transport_result = await asyncio.wait_for(asyncio.to_thread(qbt_transport_status, ctx), timeout=10.0)
        except TimeoutError:
            raise RuntimeError("qBittorrent transport check timed out (10s). Is qBittorrent running?")
        _preflight_cache["transport"] = (transport_result, now)

    cached_vpn = _preflight_cache.get("vpn")
    if cached_vpn and (now - cached_vpn[1]) < _PREFLIGHT_CACHE_TTL:
        vpn_result = cached_vpn[0]
    else:
        try:
            vpn_result = await asyncio.wait_for(asyncio.to_thread(vpn_ready_for_download, ctx), timeout=10.0)
        except TimeoutError:
            raise RuntimeError("VPN status check timed out (10s). Check VPN connection.")
        _preflight_cache["vpn"] = (vpn_result, now)

    ok, reason = cat_result
    transport_ok, transport_reason = transport_result
    vpn_ok, vpn_reason = vpn_result
    if not ok:
        try:
            ctx.store.log_health_event(
                user_id,
                None,
                "preflight_fail",
                "error",
                json.dumps({"check": "storage_categories", "reason": reason}),
                str(row.get("name", "unknown")),
            )
        except Exception:
            pass
        raise RuntimeError(f"Storage/category routing not ready: {reason}")
    if not transport_ok:
        try:
            ctx.store.log_health_event(
                user_id,
                None,
                "preflight_fail",
                "error",
                json.dumps({"check": "qbt_transport", "reason": transport_reason}),
                str(row.get("name", "unknown")),
            )
        except Exception:
            pass
        raise RuntimeError(f"qBittorrent transport is not ready: {transport_reason}")
    if not vpn_ok:
        try:
            ctx.store.log_health_event(
                user_id,
                None,
                "preflight_fail",
                "error",
                json.dumps({"check": "vpn", "reason": vpn_reason}),
                str(row.get("name", "unknown")),
            )
        except Exception:
            pass
        raise RuntimeError(f"VPN safety check failed: {vpn_reason}")

    target = targets(ctx)[choice]
    free_ok, free_reason = check_free_space(target["path"])
    if not free_ok:
        try:
            ctx.store.log_health_event(
                user_id,
                None,
                "preflight_fail",
                "error",
                json.dumps({"check": "disk_space", "reason": free_reason, "path": target["path"]}),
                str(row.get("name", "unknown")),
            )
        except Exception:
            pass
        raise RuntimeError(free_reason)
    # --- Malware / fake-content gate (pre-add, metadata only) ---
    _torrent_name = str(row.get("name") or "")
    _torrent_size = int(row.get("size") or 0)
    _torrent_hash_key = str(row.get("hash") or row.get("fileHash") or _torrent_name)
    _media_type = "episode" if choice == "tv" else "movie"
    _uploader = str(row.get("uploader") or "").strip() or None
    url, torrent_hash, malware_scan = scan_download_candidate(
        row,
        media_type=_media_type,
        files=[],
    )
    if malware_scan.is_blocked:
        try:
            ctx.store.log_malware_block(
                torrent_hash=_torrent_hash_key,
                torrent_name=_torrent_name,
                stage="search",
                reasons=malware_scan.reasons,
            )
        except Exception:
            pass  # logging failure must not block the user response
        reasons_text = "\n".join(f"• {r}" for r in malware_scan.reasons)
        raise RuntimeError(
            f"Download blocked — suspicious content detected (risk score {malware_scan.score}/100):\n{reasons_text}"
        )
    # --- end malware gate ---
    is_magnet = url.lower().startswith("magnet:?")
    try:
        resp = await asyncio.wait_for(
            asyncio.to_thread(
                ctx.qbt.add_url,
                url,
                category=target["category"],
                savepath=target["path"],
                paused=True,
            ),
            timeout=15.0,
        )
    except TimeoutError:
        raise RuntimeError("qBittorrent add_url timed out (15s). The torrent may still be added \u2014 check /active.")

    return DoAddResult(
        name=_torrent_name,
        size=_torrent_size,
        hash=torrent_hash,
        category=str(target["category"]),
        save_path=str(target["path"]),
        url=url,
        is_magnet=is_magnet,
        idx=idx,
        target_label=str(target["label"]),
        resp=str(resp),
        media_type=_media_type,
        uploader=_uploader,
    )


async def send_download_starting_message(
    ctx: HandlerContext,
    user_id: int,
    msg: Any,
    result: DoAddResult,
) -> Any:
    """Send the interim '⬇️ Download Starting' confirmation and return the sent message."""
    # ETA note based on torrent type
    if result.hash and not result.is_magnet:
        eta_note = "\u23f3 Download starting shortly\u2026"
    elif result.hash and result.is_magnet:
        eta_note = "\u23f3 Starting download\u2026 magnet metadata may take 10-60s to resolve."
    elif not result.hash and not result.is_magnet:
        eta_note = "\u23f3 Resolving torrent hash (~5s)\u2026"
    else:
        eta_note = "\u23f3 Resolving magnet link\u2026 metadata may take 10-60s."

    text = (
        f"\u2b07\ufe0f <b>Download Starting</b>\n"
        f"<code>{_h(result.name)}</code>\n"
        f"Library: {_h(result.target_label)} \u00b7 {_h(result.category)}\n\n"
        f"{eta_note}\n"
        "\U0001f6e1\ufe0f <i>Security scan runs alongside download \u00b7 "
        "Full ClamAV scan after completion</i>"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")]])
    edit_text = getattr(msg, "edit_text", None)
    if callable(edit_text) and asyncio.iscoroutinefunction(edit_text):
        await msg.edit_text(text, reply_markup=kb, parse_mode=_PM)
        sent = msg
    else:
        sent = await msg.reply_text(text, reply_markup=kb, parse_mode=_PM)
    track_ephemeral_message(ctx, user_id, sent)
    return sent


def _clear_pending_scan(ctx: HandlerContext, name: str, torrent_hash: str | None) -> None:
    """Remove a pending_scans entry by hash or name (best-effort)."""
    if torrent_hash:
        ctx.pending_scans.pop(torrent_hash.lower(), None)
    # Also try by name key (used when hash was unknown at registration time)
    ctx.pending_scans.pop(name.lower(), None)


async def do_add_background(
    ctx: HandlerContext,
    user_id: int,
    result: DoAddResult,
    interim_msg: Any,
    *,
    header: str | None = None,
    post_add_rows: list[list[Any]] | None = None,
    start_tracker: bool = True,
) -> None:
    """Background phase: hash resolution, queue+resume, tracker, concurrent file scan.

    Optimised pipeline — resumes the torrent immediately after hash resolution
    so downloads start in ~2-5s.  File-list heuristic scan runs concurrently
    while the download is active; ClamAV completion gate is the final safety net.

    Fire-and-forget — all exceptions are caught and logged.
    """
    completed_normally = False
    try:
        torrent_hash = result.hash

        # --- Hash resolution (up to 20s) ---
        if not torrent_hash:
            torrent_hash = await resolve_hash_by_name(ctx, result.name, result.category, wait_s=20)
        if not torrent_hash:
            try:
                ctx.store.log_health_event(
                    user_id,
                    None,
                    "hash_resolve_fail",
                    "warning",
                    json.dumps({"name": result.name, "category": result.category}),
                    result.name,
                )
            except Exception:
                pass
            # Clean up pending_scans entry
            _clear_pending_scan(ctx, result.name, None)
            try:
                await interim_msg.edit_text(
                    f"\u26a0\ufe0f Could not resolve torrent hash for:\n<code>{_h(result.name)}</code>\n\n"
                    "<i>The Command Center will track this download once its hash resolves.</i>",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")]]
                    ),
                    parse_mode=_PM,
                )
            except Exception:
                pass
            if start_tracker:
                start_pending_progress_tracker(
                    ctx,
                    user_id,
                    result.name,
                    result.category,
                    interim_msg,
                    header=header,
                    post_add_rows=post_add_rows,
                    headless=True,
                )
            completed_normally = True
            return

        # --- Sequential download queue + RESUME (moved before file inspection) ---
        queued = False
        async with ctx.download_queue_lock:
            if ctx.active_download_hash is None:
                ctx.active_download_hash = torrent_hash.lower()
                await asyncio.to_thread(ctx.qbt.resume_torrents, torrent_hash)
            else:
                await ctx.download_queue.put({"hash": torrent_hash.lower(), "name": result.name})
                queued = True

        # Torrent is now resumed / queued — clear pending_scans (CC picks it up from qBT)
        _clear_pending_scan(ctx, result.name, torrent_hash)

        queue_note = ""
        if queued:
            queue_note = (
                f"\n\U0001f4cb <b>Queued</b> \u2014 position {ctx.download_queue.qsize()} in queue. "
                "Will start automatically when the current download finishes."
            )

        summary = (
            f"\u2705 Added #{result.idx}: {_h(result.name)}\n"
            f"Library: {_h(result.target_label)}\n"
            f"Category: {_h(result.category)}\n"
            f"Path: {_h(result.save_path)}\n"
            f"qBittorrent: {_h(result.resp)}"
            f"{queue_note}"
        )

        # --- Attach progress tracker (HEADLESS — Command Center owns live display) ---
        if start_tracker:
            # Build the post-add action keyboard: existing post-add rows + a
            # Stop & Delete row + Home. This keyboard stays on the summary
            # message forever — it is NOT edited by the progress tracker.
            action_rows: list[list[Any]] = []
            if post_add_rows:
                action_rows.extend(post_add_rows)
            action_rows.append(
                [
                    InlineKeyboardButton(
                        "\U0001f6d1 Stop & Delete Download",
                        callback_data=f"stop:{torrent_hash}",
                    )
                ]
            )
            action_rows.append([InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")])
            action_kb = InlineKeyboardMarkup(action_rows)
            try:
                await interim_msg.edit_text(summary, reply_markup=action_kb, parse_mode=_PM)
            except Exception:
                LOG.warning("Failed to edit interim msg for post-add summary", exc_info=True)
            chat_id = int(getattr(interim_msg, "chat_id", 0) or 0)
            start_progress_tracker(
                ctx,
                user_id,
                torrent_hash,
                None,
                result.name,
                chat_id=chat_id,
            )
        else:
            # Schedule callers handle their own tracker — just edit the message.
            try:
                await interim_msg.edit_text(summary, parse_mode=_PM)
            except Exception:
                pass

        # --- Fire concurrent file-list scan (runs while download is active) ---
        scan_task = asyncio.create_task(
            _concurrent_file_scan(ctx, user_id, torrent_hash, result, interim_msg),
            name=f"concurrent_scan:{torrent_hash[:12]}",
        )
        ctx.background_tasks.add(scan_task)
        scan_task.add_done_callback(ctx.background_tasks.discard)

        completed_normally = True
    except Exception:
        LOG.error("do_add_background failed for %s", result.name, exc_info=True)
    finally:
        # Safety-net cleanup of pending_scans in case of early exception
        _clear_pending_scan(ctx, result.name, result.hash)
        if not completed_normally:
            try:
                await interim_msg.edit_text(
                    f"\u26a0\ufe0f Background checks failed for:\n<code>{_h(result.name)}</code>\n\n"
                    "<i>The torrent was added but safety checks did not complete. Check /active.</i>",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")]]
                    ),
                    parse_mode=_PM,
                )
            except Exception:
                pass


async def do_add_full(
    ctx: HandlerContext,
    user_id: int,
    search_id: str,
    idx: int,
    media_choice: str,
) -> dict[str, Any]:
    """Full synchronous add pipeline (fast + slow).  Backward compat for schedule callers.

    Identical to the old do_add() behaviour: blocks until hash resolution,
    file inspection, malware scan, and queue management are all done.
    """
    result = await do_add(ctx, user_id, search_id, idx, media_choice)

    torrent_hash = result.hash
    if not torrent_hash:
        torrent_hash = await resolve_hash_by_name(ctx, result.name, result.category, wait_s=20)

    inspection_note = ""
    if not torrent_hash:
        raise RuntimeError("Download blocked — qBittorrent did not assign a torrent hash for inspection.")

    inspection_timeout = (
        ctx.cfg.file_inspection_timeout_s * 3 if result.is_magnet else ctx.cfg.file_inspection_timeout_s
    )
    try:
        raw_files = await _wait_for_file_inspection(ctx, torrent_hash, timeout_s=inspection_timeout)
    except Exception as exc:
        inspection_note = (
            "\n\u26a0\ufe0f File inspection did not complete in time. "
            "Continuing with completion-time ClamAV scanning only."
        )
        LOG.warning(
            "Continuing after inspection failure for %s (magnet=%s): %s",
            torrent_hash,
            result.is_magnet,
            exc,
        )
    else:
        files = _torrent_file_names(raw_files)
        file_sizes = _torrent_file_sizes(raw_files)
        malware_scan_result = scan_download(
            name=result.name,
            size_bytes=result.size,
            quality_tier=quality_tier(result.name),
            media_type=result.media_type,
            files=files,
            uploader=result.uploader,
            file_sizes=file_sizes,
        )
        if malware_scan_result.is_blocked:
            try:
                await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
            except Exception:
                LOG.warning("Failed to delete blocked torrent %s", torrent_hash, exc_info=True)
            try:
                ctx.store.log_malware_block(
                    torrent_hash=torrent_hash,
                    torrent_name=result.name,
                    stage="download",
                    reasons=malware_scan_result.reasons,
                )
            except Exception:
                pass
            top_signals = sorted(malware_scan_result.signals, key=lambda s: s.points, reverse=True)[:5]
            signal_lines = "\n".join(f"• {s.signal_id} (+{s.points}) {s.detail}" for s in top_signals)
            raise RuntimeError(
                f"Blocked (Score: {malware_scan_result.score}/100)\n{result.name}\n\nSignals:\n{signal_lines}"
            )

    queued = False
    async with ctx.download_queue_lock:
        if ctx.active_download_hash is None:
            ctx.active_download_hash = torrent_hash.lower()
            await asyncio.to_thread(ctx.qbt.resume_torrents, torrent_hash)
        else:
            await ctx.download_queue.put({"hash": torrent_hash.lower(), "name": result.name})
            queued = True

    queue_note = ""
    if queued:
        queue_note = (
            f"\n\U0001f4cb <b>Queued</b> \u2014 position {ctx.download_queue.qsize()} in queue. "
            "Will start automatically when the current download finishes."
        )

    summary = (
        f"\u2705 Added #{idx}: {_h(result.name)}\n"
        f"Library: {_h(result.target_label)}\n"
        f"Category: {_h(result.category)}\n"
        f"Path: {_h(result.save_path)}\n"
        f"qBittorrent: {_h(result.resp)}"
        f"{inspection_note}"
        f"{queue_note}"
    )

    return {
        "summary": summary,
        "name": result.name,
        "category": result.category,
        "hash": torrent_hash,
        "path": result.save_path,
        "queued": queued,
    }


async def on_cb_mwblock(ctx: HandlerContext, *, data: str, q: Any, user_id: int) -> None:
    """Handle ``mwblock:keep:{hash}`` and ``mwblock:delete:{hash}`` callbacks."""
    parts = data.split(":", 2)
    if len(parts) < 3:
        await q.answer("Invalid action", show_alert=True)
        return
    action = parts[1]
    torrent_hash = parts[2]
    if not re.fullmatch(r"[a-f0-9]{40}", torrent_hash.lower()):
        await q.answer("Invalid hash", show_alert=True)
        return
    torrent_hash = torrent_hash.lower()

    if action == "keep":
        try:
            await asyncio.to_thread(ctx.qbt.resume_torrents, torrent_hash)
        except Exception:
            LOG.warning("mwblock:keep — torrent %s may no longer exist", torrent_hash, exc_info=True)
            await q.answer("Torrent no longer exists", show_alert=True)
            return
        try:
            ctx.store.log_health_event(
                user_id,
                torrent_hash,
                "malware_override_keep",
                "info",
                json.dumps({"action": "keep"}),
                torrent_hash,
            )
        except Exception:
            pass
        stop_kb = stop_download_keyboard(torrent_hash)
        try:
            await q.message.edit_text(
                "\u2705 <b>Resumed</b> \u2014 monitoring will continue.",
                reply_markup=stop_kb,
                parse_mode=_PM,
            )
        except Exception:
            pass
        start_progress_tracker(ctx, user_id, torrent_hash, q.message, "Download")
        await q.answer("Torrent resumed")

    elif action == "delete":
        try:
            await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
        except Exception:
            LOG.warning("mwblock:delete — torrent %s may no longer exist", torrent_hash, exc_info=True)
        # Clean up download queue entry if present
        async with ctx.download_queue_lock:
            if ctx.active_download_hash == torrent_hash:
                ctx.active_download_hash = None
        try:
            ctx.store.log_health_event(
                user_id,
                torrent_hash,
                "malware_override_delete",
                "info",
                json.dumps({"action": "delete"}),
                torrent_hash,
            )
        except Exception:
            pass
        try:
            await q.message.edit_text(
                "\U0001f5d1 <b>Torrent deleted.</b>",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("\U0001f3e0 Home", callback_data="nav:home")]]
                ),
                parse_mode=_PM,
            )
        except Exception:
            pass
        await q.answer("Torrent deleted")
    else:
        await q.answer("Unknown action", show_alert=True)


async def on_cb_stop(ctx: HandlerContext, *, data: str, q: Any, user_id: int) -> None:
    """Handle ``stop:*`` callback queries — cancel download and delete torrent."""
    if data.startswith("stop:all:"):
        hashes_str = data[len("stop:all:") :]
        hashes = [
            h.strip().lower()
            for h in hashes_str.split(",")
            if h.strip() and re.fullmatch(r"[a-f0-9]{40}", h.strip().lower())
        ]
        for torrent_hash in hashes:
            task = ctx.progress_tasks.pop((user_id, torrent_hash), None)
            if task and not task.done():
                task.cancel()
            media_path_all = ""
            try:
                torrent_info_all = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
                if torrent_info_all:
                    media_path_all = str(
                        torrent_info_all.get("content_path") or torrent_info_all.get("save_path") or ""
                    ).strip()
            except Exception:
                pass
            try:
                await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
                if ctx.plex.ready() and media_path_all:
                    try:
                        plex_msg = await asyncio.to_thread(ctx.plex.purge_deleted_path, media_path_all)
                        LOG.info("stop:all Plex purge: %s", plex_msg)
                    except Exception:
                        LOG.warning("stop:all Plex purge failed for %s", media_path_all, exc_info=True)
            except Exception:
                LOG.warning("stop:all failed to delete torrent %s", torrent_hash, exc_info=True)
        # Clear the download queue and reset active slot.
        async with ctx.download_queue_lock:
            while not ctx.download_queue.empty():
                try:
                    ctx.download_queue.get_nowait()
                except Exception:
                    break
            ctx.active_download_hash = None
        try:
            await stop_batch_monitor(ctx, user_id)
        except Exception:
            LOG.warning("stop:all failed to stop batch monitor for user %s", user_id, exc_info=True)
        await q.answer("All downloads stopped.")
        return

    if data.startswith("stop:"):
        torrent_hash = data[5:]
        if not re.fullmatch(r"[a-f0-9]{40}", torrent_hash):
            await q.answer("Invalid hash", show_alert=True)
            return
        key = (user_id, torrent_hash.lower())
        task = ctx.progress_tasks.get(key)
        if task and not task.done():
            task.cancel()
        torrent_name = "Download"
        media_path = ""
        try:
            torrent_info = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
            if torrent_info:
                torrent_name = torrent_info.get("name", "Download") or "Download"
                media_path = str(torrent_info.get("content_path") or torrent_info.get("save_path") or "").strip()
        except Exception:
            pass
        try:
            await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
            if ctx.plex.ready() and media_path:
                try:
                    plex_msg = await asyncio.to_thread(ctx.plex.purge_deleted_path, media_path)
                    LOG.info("Cancel-download Plex purge: %s", plex_msg)
                except Exception:
                    LOG.warning("Cancel-download Plex purge failed for %s", media_path, exc_info=True)
            # Remove from download queue if queued, or advance if it was active.
            await _remove_from_download_queue(ctx, torrent_hash.lower())
            try:
                await _advance_download_queue(ctx, expected_hash=torrent_hash.lower())
            except Exception:
                LOG.warning("Failed to advance queue after single stop", exc_info=True)
            # Navigate to Command Center (replicating nav:home logic)
            flow_mod.clear_flow(ctx, user_id)
            render_mod.cancel_pending_trackers_for_user(ctx, user_id)
            # Edit the tracker message in-place — no delete, no blank flash
            if ctx.navigate_to_command_center:
                await ctx.navigate_to_command_center(q.message, user_id, current_ui_message=q.message)
            # Send self-deleting confirmation notice (no buttons)
            notice = await q.message.chat.send_message(
                f"\u2705 <b>{_h(torrent_name)}</b> removed and canceled.",
                parse_mode=_PM,
            )

            async def _auto_delete(bot, cid: int, mid: int) -> None:
                await asyncio.sleep(10)
                try:
                    await bot.delete_message(chat_id=cid, message_id=mid)
                except Exception:
                    pass

            del_task = asyncio.create_task(
                _auto_delete(q.get_bot(), q.message.chat_id, notice.message_id),
                name=f"auto-delete:{q.message.chat_id}:{notice.message_id}",
            )
            ctx.background_tasks.add(del_task)
            del_task.add_done_callback(ctx.background_tasks.discard)
        except Exception as e:
            await q.message.edit_text(
                f"<b>\u26a0\ufe0f Stop Failed</b>\n<i>{_h(str(e))}</i>", reply_markup=None, parse_mode=_PM
            )
        return
