"""LLM / Patchy-chat handler functions.

These are the four methods extracted from BotApp:

- ``chat_needs_qbt_snapshot`` — static check: does the user text reference qBT?
- ``build_qbt_snapshot`` — assembles a read-only qBT status string for LLM context
- ``patchy_system_prompt`` — returns the LLM system prompt
- ``reply_patchy_chat`` — async: sends text to the LLM and replies to the user

``build_qbt_snapshot`` inlines the three BotApp status-helper calls
(``_qbt_transport_status``, ``_storage_status``, ``_vpn_ready_for_download``)
using ``ctx.qbt`` and ``ctx.cfg`` directly to avoid a circular import back into
BotApp.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from typing import Any

from ..types import HandlerContext
from ..utils import _PM, _h, human_size

LOG = logging.getLogger("qbtg")


# ---------------------------------------------------------------------------
# Static helper — no ctx needed
# ---------------------------------------------------------------------------


def chat_needs_qbt_snapshot(text: str) -> bool:
    """Return True if *text* mentions qBT-related keywords.

    Args:
        text: Raw user message text.

    Returns:
        True if the message likely needs a qBT status snapshot as context.
    """
    low = text.lower()
    keywords = {
        "qbit",
        "qbittorrent",
        "torrent",
        "download",
        "seeding",
        "seed",
        "active",
        "speed",
        "eta",
        "storage",
        "category",
        "categories",
        "vpn",
    }
    return any(k in low for k in keywords)


# ---------------------------------------------------------------------------
# qBT snapshot helpers (inlined from BotApp private methods)
# ---------------------------------------------------------------------------


def _qbt_transport_status(ctx: HandlerContext) -> tuple[bool, str]:
    """Check qBT network transport health.

    Inlined from ``BotApp._qbt_transport_status``.

    Args:
        ctx: Shared handler context.

    Returns:
        ``(ok, reason)`` tuple.
    """
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


def _storage_status(ctx: HandlerContext) -> tuple[bool, str]:
    """Check media library storage health.

    Inlined from ``BotApp._storage_status``.

    Args:
        ctx: Shared handler context.

    Returns:
        ``(ok, reason)`` tuple.
    """
    cfg = ctx.cfg
    if cfg.require_nvme_mount and not os.path.ismount(cfg.nvme_mount_path):
        return False, f"NVMe mount missing at {cfg.nvme_mount_path}"

    for path in (cfg.movies_path, cfg.tv_path):
        os.makedirs(path, exist_ok=True)
        if not os.path.isdir(path):
            return False, f"Library path missing: {path}"

    return True, "ready"


def _vpn_ready_for_download(ctx: HandlerContext) -> tuple[bool, str]:
    """Check VPN interface readiness.

    Inlined from ``BotApp._vpn_ready_for_download``.

    Args:
        ctx: Shared handler context.

    Returns:
        ``(ok, reason)`` tuple.
    """
    cfg = ctx.cfg
    if not cfg.vpn_required_for_downloads:
        return True, "vpn check disabled"

    iface = cfg.vpn_interface_name

    if not os.path.exists(f"/sys/class/net/{iface}"):
        return False, f"VPN interface missing: {iface}"

    try:
        with open(f"/sys/class/net/{iface}/operstate", encoding="utf-8") as f:
            state = f.read().strip().lower()
    except Exception:
        state = "unknown"
    if state == "down":
        return False, f"VPN interface is down: {iface}"

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
        return False, f"VPN check error: {e}"

    return True, f"vpn interface {iface} ready"


# ---------------------------------------------------------------------------
# Exported functions
# ---------------------------------------------------------------------------


def build_qbt_snapshot(ctx: HandlerContext) -> str:
    """Build a read-only qBT status string for LLM context.

    Assembles active-torrent info plus transport, storage, and VPN status.

    Args:
        ctx: Shared handler context providing ``qbt`` and ``cfg``.

    Returns:
        Newline-joined status string, or empty string on total failure.
    """
    lines: list[str] = []
    try:
        active = ctx.qbt.list_active(limit=6)
    except Exception as e:
        active = []
        lines.append(f"active_error={e}")

    if not active:
        lines.append("active: none")
    else:
        lines.append("active:")
        for t in active[:6]:
            name = str(t.get("name") or "?")
            progress = float(t.get("progress", 0.0) or 0.0) * 100.0
            dls = int(t.get("dlspeed", 0) or 0)
            state = str(t.get("state") or "unknown")
            lines.append(f"- {name} | {progress:.1f}% | {state} | down={human_size(dls)}/s")

    try:
        transport_ok, transport_reason = _qbt_transport_status(ctx)
        lines.append(f"qbt transport: {'ready' if transport_ok else 'blocked'} ({transport_reason})")
    except Exception as e:
        lines.append(f"qbt transport: error ({e})")

    try:
        ok, reason = _storage_status(ctx)
        lines.append(f"storage: {'ready' if ok else 'not-ready'} ({reason})")
    except Exception as e:
        lines.append(f"storage: error ({e})")

    try:
        vpn_ok, vpn_reason = _vpn_ready_for_download(ctx)
        lines.append(f"vpn: {'ready' if vpn_ok else 'blocked'} ({vpn_reason})")
    except Exception as e:
        lines.append(f"vpn: error ({e})")

    return "\n".join(lines)


def patchy_system_prompt(ctx: HandlerContext) -> str:
    """Return the LLM system prompt for Patchy chat.

    Args:
        ctx: Shared handler context providing ``cfg.patchy_chat_name``.

    Returns:
        System prompt string.
    """
    return (
        f"You are {ctx.cfg.patchy_chat_name}, a friendly assistant for a home Plex/qBittorrent server. "
        "READ-ONLY MODE is mandatory: never claim to execute state-changing actions, "
        "never add/remove/pause/resume torrents, never edit files/services. "
        "You may analyze, explain, and recommend next steps only. "
        "If the user asks for a state change, clearly say it requires an explicit bot command/button. "
        "When a 'Read-only qBittorrent snapshot' message is provided, treat it as current source-of-truth data "
        "and answer from it directly (do not claim you lack access). "
        "Keep responses concise, practical, and human."
    )


def _strip_patchy_name(ctx: HandlerContext, text: str) -> str:
    """Strip the bot's name from the start of the user's message.

    Args:
        ctx: Shared handler context providing ``cfg.patchy_chat_name``.
        text: Raw user message.

    Returns:
        Text with leading name greeting removed and stripped.
    """
    name = re.escape(ctx.cfg.patchy_chat_name or "Patchy")
    cleaned = re.sub(rf"^\s*(?:hey|hi|hello|yo)\s+@?{name}\s*[:,!\-]?\s*", "", text, flags=re.I)
    cleaned = re.sub(rf"^\s*@?{name}\s*[:,!\-]?\s*", "", cleaned, flags=re.I)
    return cleaned.strip()


async def reply_patchy_chat(ctx: HandlerContext, msg: Any, user_id: int, text: str) -> None:
    """Send user text to the LLM and reply with the response.

    Maintains per-user chat history with LRU eviction.  Prepends a
    read-only qBT snapshot when the message references torrent/download
    keywords.

    Args:
        ctx: Shared handler context.
        msg: Telegram ``Message`` object with a ``reply_text`` coroutine.
        user_id: Telegram user ID, used as chat-history key.
        text: Raw user message text.
    """
    # TEMPORARY: chat disabled until API key is reconfigured
    await msg.reply_text("<i>Chat temporarily disabled.</i>", parse_mode=_PM)
    return

    if not ctx.cfg.patchy_chat_enabled:  # noqa: unreachable
        await msg.reply_text("Chat mode is currently disabled.", parse_mode=_PM)
        return

    if not ctx.patchy_llm.ready():
        await msg.reply_text(
            "Patchy chat is not configured yet. Set PATCHY_LLM_BASE_URL + PATCHY_LLM_API_KEY"
            " (or keep OpenClaw provider auto-discovery enabled).",
            parse_mode=_PM,
        )
        return

    user_text = (_strip_patchy_name(ctx, text) or text.strip())[:2000]

    snapshot_prefix = ""
    if chat_needs_qbt_snapshot(user_text):
        snapshot = await asyncio.to_thread(build_qbt_snapshot, ctx)
        if snapshot:
            snapshot_prefix = "Read-only qBittorrent snapshot:\n" + snapshot + "\n\n"

    messages: list[dict[str, str]] = [{"role": "system", "content": patchy_system_prompt(ctx)}]
    hist = ctx.chat_history.get(user_id, [])
    # Move to end on read to mark as recently used
    if user_id in ctx.chat_history:
        ctx.chat_history.move_to_end(user_id)
    if hist:
        messages.extend(hist[-(ctx.cfg.patchy_chat_history_turns * 2) :])

    user_content = snapshot_prefix + "User request:\n" + user_text
    messages.append({"role": "user", "content": user_content})

    try:
        reply, _used_model = await asyncio.to_thread(
            ctx.patchy_llm.chat,
            messages=messages,
            model=ctx.cfg.patchy_chat_model,
            fallback_model=ctx.cfg.patchy_chat_fallback_model,
            max_tokens=ctx.cfg.patchy_chat_max_tokens,
            temperature=ctx.cfg.patchy_chat_temperature,
        )
    except Exception as e:
        LOG.warning("Patchy chat failed", exc_info=True)
        await msg.reply_text(
            f"Patchy is online, but the model request failed right now: {_h(str(e))}",
            parse_mode=_PM,
        )
        return

    hist = ctx.chat_history.setdefault(user_id, [])
    hist.append({"role": "user", "content": user_text})
    hist.append({"role": "assistant", "content": reply})
    keep = ctx.cfg.patchy_chat_history_turns * 2
    if len(hist) > keep:
        del hist[:-keep]
    ctx.chat_history.move_to_end(user_id)
    # Evict oldest entry if over the user limit
    while len(ctx.chat_history) > ctx.chat_history_max_users:
        ctx.chat_history.popitem(last=False)

    await msg.reply_text(_h(reply), parse_mode=_PM)
