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
import os
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


async def _wait_for_file_inspection(
    ctx: HandlerContext,
    torrent_hash: str,
    *,
    timeout_s: int,
) -> list[str]:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            files = await asyncio.to_thread(ctx.qbt.get_torrent_files, torrent_hash)
            names = _torrent_file_names(files)
            if names:
                return names
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(0.8)
    if last_error is not None:
        raise RuntimeError(f"file inspection did not complete: {last_error}")
    raise RuntimeError("file inspection did not complete before timeout")


def _sanitize_quarantine_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" ._")
    return cleaned or "quarantine-item"


def _quarantine_payload(path: str, quarantine_root: str, torrent_hash: str) -> str:
    os.makedirs(quarantine_root, exist_ok=True)
    src = str(path or "").strip()
    if not src or not os.path.exists(src):
        raise RuntimeError(f"download path missing: {src or 'unknown'}")
    base_name = _sanitize_quarantine_name(os.path.basename(src.rstrip("/")) or torrent_hash[:12])
    dest = os.path.join(quarantine_root, base_name)
    counter = 2
    while os.path.exists(dest):
        dest = os.path.join(quarantine_root, f"{base_name}-{counter}")
        counter += 1
    shutil.move(src, dest)
    return dest


def _clamd_available() -> bool:
    if not shutil.which("clamdscan"):
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
        return False
    return result.returncode == 0


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

    try:
        await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=False)
    except Exception:
        LOG.warning("Failed to remove torrent after malware hold: %s", torrent_hash, exc_info=True)

    quarantine_root = os.path.join(ctx.cfg.spam_path, "quarantine")
    quarantine_path = media_path
    quarantine_error: str | None = None
    try:
        quarantine_path = await asyncio.to_thread(_quarantine_payload, media_path, quarantine_root, torrent_hash)
    except Exception as exc:
        quarantine_error = str(exc)
        LOG.warning("Failed to quarantine payload for %s", torrent_hash, exc_info=True)

    if quarantine_error:
        reasons = [*reasons, f"quarantine failed: {quarantine_error}"]

    try:
        await asyncio.to_thread(ctx.store.log_malware_block, torrent_hash, name, "download", reasons)
    except Exception:
        LOG.debug("Failed to log malware block", exc_info=True)

    severity = "critical" if status == "infected" else "warn"
    event_type = "malware_quarantine" if status == "infected" else "malware_scan_error"
    try:
        await asyncio.to_thread(
            ctx.store.log_health_event,
            user_id,
            torrent_hash,
            event_type,
            severity,
            json.dumps({"reasons": reasons, "quarantine_path": quarantine_path}),
            name,
        )
    except Exception:
        LOG.debug("Failed to log malware health event", exc_info=True)

    title = "Malware Detected" if status == "infected" else "Security Hold"
    intro = (
        "ClamAV detected malicious content."
        if status == "infected"
        else "ClamAV could not produce a safe verdict."
    )
    where = (
        f"\nQuarantined to: <code>{_h(quarantine_path)}</code>"
        if quarantine_path and quarantine_path != media_path
        else "\nPayload remains in place pending manual review."
    )
    reason_lines = "\n".join(f"• {_h(reason)}" for reason in reasons[:8])
    notice = (
        f"⚠️ <b>{title}</b>\n"
        f"<code>{_h(name)}</code>\n\n"
        f"{_h(intro)}{where}\n\n"
        f"{reason_lines}"
    )
    return CompletionSecurityResult(False, quarantine_path, notice)


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
    """Send a message directly to the chat when tracker_msg was deleted."""
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
    """Edit a tracker message, handling transient Telegram errors gracefully."""
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
    post_add_rows: list[list[Any]] | None = None,
) -> None:
    """Launch a progress-tracking asyncio task for a torrent, keyed by (uid, hash)."""
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


def start_pending_progress_tracker(
    ctx: HandlerContext,
    user_id: int,
    title: str,
    category: str,
    base_msg: Any,
    *,
    header: str | None = None,
    post_add_rows: list[list[Any]] | None = None,
) -> None:
    """Launch a pending-monitor task that waits for qBT to assign a hash, then attaches a live monitor."""
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
    post_add_rows: list[list[Any]] | None = None,
) -> None:
    """Poll qBT until the torrent hash is available, then start a live progress tracker."""
    key = (user_id, category.lower(), title.strip().lower())
    try:
        torrent_hash = await resolve_hash_by_name(ctx, title, category, wait_s=35)
        if not torrent_hash:
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
            try:
                ctx.store.log_health_event(
                    user_id,
                    None,
                    "pending_tracker_timeout",
                    "warn",
                    json.dumps({"title": title, "category": category, "wait_s": 35}),
                    title,
                )
            except Exception:
                LOG.debug("Failed to log pending_tracker_timeout health event", exc_info=True)
            return

        # When we have a header, edit the existing message to show combined content.
        # Without a header, reply with a new message (old behavior — avoids clobbering
        # shared messages like the schedule batch summary).
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
    """The main progress-tracking loop: polls qBT every few seconds, edits the Telegram message."""
    key = (user_id, torrent_hash.lower())
    start = time.time()
    tick = 0
    edit_count = 0
    last_text = ""
    last_edit_at = 0.0
    qbt_error_streak = 0
    edit_error_streak = 0
    edit_backoff_until = 0.0
    stop_kb = stop_download_keyboard(torrent_hash, post_add_rows=post_add_rows)

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

                timeout_text = (
                    (last_text + "\n") if last_text else ""
                ) + f"<b>\u23f1 Monitor Timed Out</b>\nUse <code>/active</code> for current status.{state_line}"
                if timeout_text != last_text:
                    edit_result = await safe_tracker_edit(tracker_msg, timeout_text, reply_markup=None)
                    if edit_result.ok:
                        last_text = timeout_text
                    else:
                        if edit_result.retry_after_s > 0:
                            edit_backoff_until = max(edit_backoff_until, time.time() + edit_result.retry_after_s)
                        else:
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
                edit_result = await safe_tracker_edit(tracker_msg, notice, reply_markup=None)
                if not edit_result.ok and edit_result.retry_after_s <= 0:
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

            text = render_progress_text(
                title,
                info,
                edit_count,
                progress_pct=smooth_progress_pct,
                dls_bps=int(smooth_dls),
                uls_bps=int(smooth_uls),
                header=header,
            )

            now = time.time()
            if now < edit_backoff_until:
                await asyncio.sleep(min(ctx.cfg.progress_refresh_s, max(0.2, edit_backoff_until - now)))
                tick += 1
                continue
            if text != last_text and (now - last_edit_at) >= ctx.cfg.progress_edit_min_s:
                edit_result = await safe_tracker_edit(tracker_msg, text, reply_markup=stop_kb)
                if edit_result.ok:
                    last_text = text
                    last_edit_at = now
                    edit_count += 1
                    edit_error_streak = 0
                else:
                    edit_error_streak += 1
                    if edit_result.retry_after_s > 0:
                        edit_backoff_until = max(edit_backoff_until, time.time() + edit_result.retry_after_s)

            if is_complete_torrent(info):
                done_text = (
                    render_progress_text(
                        title,
                        info,
                        edit_count,
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
        ctx.progress_tasks.pop(key, None)


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

    # Housekeeping: clean up old records once per run.
    try:
        await asyncio.to_thread(ctx.store.cleanup_old_completion_records)
    except Exception:
        pass


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
) -> dict[str, Any]:
    """Add a torrent to qBittorrent with pre-flight safety checks."""
    payload = ctx.store.get_search(user_id, search_id)
    if not payload:
        raise RuntimeError("Search result not found")

    choice = normalize_media_choice(media_choice)
    if choice not in {"movies", "tv"}:
        raise RuntimeError("Media type must be Movies or TV")

    row = ctx.store.get_result(user_id, search_id, idx)
    if not row:
        raise RuntimeError("Search result not found")

    try:
        cat_result = await asyncio.wait_for(asyncio.to_thread(ensure_media_categories, ctx), timeout=10.0)
    except TimeoutError:
        raise RuntimeError("Storage/category check timed out (10s). Check qBittorrent connectivity.")

    try:
        transport_result = await asyncio.wait_for(asyncio.to_thread(qbt_transport_status, ctx), timeout=10.0)
    except TimeoutError:
        raise RuntimeError("qBittorrent transport check timed out (10s). Is qBittorrent running?")

    try:
        vpn_result = await asyncio.wait_for(asyncio.to_thread(vpn_ready_for_download, ctx), timeout=10.0)
    except TimeoutError:
        raise RuntimeError("VPN status check timed out (10s). Check VPN connection.")

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
    # --- Malware / fake-content gate ---
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
                stage="download",
                reasons=malware_scan.reasons,
            )
        except Exception:
            pass  # logging failure must not block the user response
        reasons_text = "\n".join(f"• {r}" for r in malware_scan.reasons)
        raise RuntimeError(f"Download blocked — suspicious content detected:\n{reasons_text}")
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

    if not torrent_hash:
        torrent_hash = await resolve_hash_by_name(ctx, _torrent_name, target["category"], wait_s=20)

    inspection_note = ""
    if not torrent_hash:
        raise RuntimeError("Download blocked — qBittorrent did not assign a torrent hash for inspection.")

    try:
        files = await _wait_for_file_inspection(
            ctx,
            torrent_hash,
            timeout_s=ctx.cfg.file_inspection_timeout_s,
        )
    except Exception as exc:
        if is_magnet:
            inspection_note = (
                "\n\u26a0\ufe0f File inspection did not complete in time. "
                "Continuing with completion-time ClamAV scanning only."
            )
            LOG.warning("Continuing after magnet inspection failure for %s: %s", torrent_hash, exc)
        else:
            try:
                await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
            except Exception:
                LOG.warning("Failed to delete torrent after inspection failure %s", torrent_hash, exc_info=True)
            raise RuntimeError(f"Download blocked — file inspection failed: {exc}") from exc
    else:
        malware_scan = scan_download(
            name=_torrent_name,
            size_bytes=_torrent_size,
            quality_tier=quality_tier(_torrent_name),
            media_type=_media_type,
            files=files,
            uploader=_uploader,
        )
        if malware_scan.is_blocked:
            try:
                await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
            except Exception:
                LOG.warning("Failed to delete blocked torrent %s", torrent_hash, exc_info=True)
            try:
                ctx.store.log_malware_block(
                    torrent_hash=torrent_hash,
                    torrent_name=_torrent_name,
                    stage="download",
                    reasons=malware_scan.reasons,
                )
            except Exception:
                pass
            reasons_text = "\n".join(f"• {r}" for r in malware_scan.reasons)
            raise RuntimeError(f"Download blocked — suspicious content detected:\n{reasons_text}")

    await asyncio.to_thread(ctx.qbt.resume_torrents, torrent_hash)

    summary = (
        f"\u2705 Added #{idx}: {_h(str(row['name']))}\n"
        f"Library: {_h(str(target['label']))}\n"
        f"Category: {_h(str(target['category']))}\n"
        f"Path: {_h(str(target['path']))}\n"
        f"qBittorrent: {_h(str(resp))}"
        f"{inspection_note}"
    )

    return {
        "summary": summary,
        "name": str(row["name"]),
        "category": str(target["category"]),
        "hash": torrent_hash,
        "path": str(target["path"]),
    }


async def on_cb_stop(ctx: HandlerContext, *, data: str, q: Any, user_id: int) -> None:
    """Handle ``stop:*`` callback queries — cancel download and delete torrent."""
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
        try:
            torrent_info = await asyncio.to_thread(ctx.qbt.get_torrent, torrent_hash)
            if torrent_info:
                torrent_name = torrent_info.get("name", "Download") or "Download"
        except Exception:
            pass
        try:
            await asyncio.to_thread(ctx.qbt.delete_torrent, torrent_hash, delete_files=True)
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
