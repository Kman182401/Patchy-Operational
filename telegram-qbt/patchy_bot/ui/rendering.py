"""Render helpers — nav-UI, flow-UI, and ephemeral-message lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardMarkup
from telegram.error import TelegramError

from ..types import HandlerContext
from ..utils import _PM
from .flow import set_flow

LOG = logging.getLogger("qbtg")


# ---------------------------------------------------------------------------
# Helpers that remember message locations
# ---------------------------------------------------------------------------


def remember_nav_ui_message(ctx: HandlerContext, user_id: int, message: Any) -> None:
    """Persist the command-center message location in memory and the DB."""
    chat_id = getattr(message, "chat_id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return
    ctx.user_nav_ui[user_id] = {
        "chat_id": int(chat_id),
        "message_id": int(message_id),
    }
    try:
        ctx.store.save_command_center(user_id, int(chat_id), int(message_id))
    except Exception:
        LOG.warning("Failed to persist CC location to DB", exc_info=True)


def remember_flow_ui_message(
    ctx: HandlerContext,
    user_id: int,
    flow: dict[str, Any] | None,
    message: Any,
    flow_key: str,
) -> None:
    """Store the flow-message location inside ``flow`` and re-save to ``ctx``."""
    if not isinstance(flow, dict):
        return
    chat_id = getattr(message, "chat_id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return
    flow[f"{flow_key}_ui_chat_id"] = int(chat_id)
    flow[f"{flow_key}_ui_message_id"] = int(message_id)
    if str(flow.get("mode") or "") == flow_key:
        set_flow(ctx, user_id, flow)


# ---------------------------------------------------------------------------
# Ephemeral-message tracking
# ---------------------------------------------------------------------------


def track_ephemeral_message(ctx: HandlerContext, user_id: int, message: Any) -> None:
    """Register a message for later bulk deletion."""
    chat_id = getattr(message, "chat_id", None)
    message_id = getattr(message, "message_id", None)
    if chat_id is None or message_id is None:
        return
    ctx.user_ephemeral_messages.setdefault(user_id, []).append({"chat_id": int(chat_id), "message_id": int(message_id)})


async def cleanup_ephemeral_messages(ctx: HandlerContext, user_id: int, bot: Any) -> None:
    """Delete all ephemeral messages tracked for ``user_id``."""
    msgs = ctx.user_ephemeral_messages.pop(user_id, [])
    for m in msgs:
        try:
            await bot.delete_message(chat_id=m["chat_id"], message_id=m["message_id"])
        except TelegramError:
            pass


# ---------------------------------------------------------------------------
# Nav-UI helpers
# ---------------------------------------------------------------------------


async def delete_old_nav_ui(ctx: HandlerContext, user_id: int, bot: Any) -> None:
    """Delete the previous command-center message so /start shows a clean chat."""
    info = ctx.user_nav_ui.pop(user_id, None)
    if not info:
        return
    try:
        await bot.delete_message(chat_id=info["chat_id"], message_id=info["message_id"])
    except TelegramError:
        pass


async def cleanup_private_user_message(message: Any) -> None:
    """Delete ``message`` if it was sent in a private chat."""
    chat = getattr(message, "chat", None)
    chat_type = str(getattr(chat, "type", "") or "").lower()
    if chat_type != "private":
        return
    try:
        await message.delete()
    except (TelegramError, Exception):
        return


# ---------------------------------------------------------------------------
# Task-cancellation helpers
# ---------------------------------------------------------------------------


def cancel_pending_trackers_for_user(ctx: HandlerContext, user_id: int) -> None:
    """Cancel pending-tracker asyncio tasks for ``user_id``.

    Prevents stale monitor messages from appearing after a home cleanup.
    """
    to_cancel = [key for key in list(ctx.pending_tracker_tasks) if key[0] == user_id]
    for key in to_cancel:
        task = ctx.pending_tracker_tasks.pop(key, None)
        if task and not task.done():
            task.cancel()


# ---------------------------------------------------------------------------
# Core render functions
# ---------------------------------------------------------------------------


async def render_nav_ui(
    ctx: HandlerContext,
    user_id: int,
    anchor_message: Any,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    current_ui_message: Any | None = None,
) -> Any:
    """Render (or update) the command-center message for ``user_id``.

    Edits the existing message when one is remembered; falls back to a new
    ``reply_text`` when no prior message exists or when the edit fails.
    """
    bot = anchor_message.get_bot()
    remembered = ctx.user_nav_ui.get(user_id) or {}
    target_chat_id = int(remembered.get("chat_id") or 0)
    target_message_id = int(remembered.get("message_id") or 0)
    if current_ui_message is not None:
        target_chat_id = int(getattr(current_ui_message, "chat_id", 0) or 0)
        target_message_id = int(getattr(current_ui_message, "message_id", 0) or 0)
    if target_chat_id and target_message_id:
        try:
            rendered = await bot.edit_message_text(
                chat_id=target_chat_id,
                message_id=target_message_id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
                parse_mode=_PM,
            )
            target_message = rendered if hasattr(rendered, "message_id") else current_ui_message
            if target_message is not None:
                remember_nav_ui_message(ctx, user_id, target_message)
                return target_message
        except TelegramError as e:
            if "message is not modified" in str(e).lower():
                target_message = current_ui_message
                if target_message is not None:
                    remember_nav_ui_message(ctx, user_id, target_message)
                    return target_message
    rendered = await anchor_message.reply_text(
        text,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
        parse_mode=_PM,
    )
    remember_nav_ui_message(ctx, user_id, rendered)
    return rendered


async def render_flow_ui(
    ctx: HandlerContext,
    user_id: int,
    anchor_message: Any,
    flow: dict[str, Any] | None,
    text: str,
    *,
    flow_key: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    current_ui_message: Any | None = None,
) -> Any:
    """Render (or update) a flow-mode UI message.

    Edits the existing flow message when one is stored in ``flow``; falls back
    to a new ``reply_text`` otherwise.
    """
    flow = flow if isinstance(flow, dict) else None
    bot = anchor_message.get_bot()
    target_chat_id = int(flow.get(f"{flow_key}_ui_chat_id") or 0) if flow else 0
    target_message_id = int(flow.get(f"{flow_key}_ui_message_id") or 0) if flow else 0
    if current_ui_message is not None:
        target_chat_id = int(getattr(current_ui_message, "chat_id", 0) or 0)
        target_message_id = int(getattr(current_ui_message, "message_id", 0) or 0)
    if target_chat_id and target_message_id:
        try:
            rendered = await bot.edit_message_text(
                chat_id=target_chat_id,
                message_id=target_message_id,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
                parse_mode=_PM,
            )
            target_message = rendered if hasattr(rendered, "message_id") else current_ui_message
            if target_message is not None:
                remember_flow_ui_message(ctx, user_id, flow, target_message, flow_key)
                return target_message
        except TelegramError as e:
            if "message is not modified" in str(e).lower():
                target_message = current_ui_message
                if target_message is not None:
                    remember_flow_ui_message(ctx, user_id, flow, target_message, flow_key)
                    return target_message
    rendered = await anchor_message.reply_text(
        text,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
        parse_mode=_PM,
    )
    remember_flow_ui_message(ctx, user_id, flow, rendered, flow_key)
    return rendered


async def render_remove_ui(
    ctx: HandlerContext,
    user_id: int,
    anchor_message: Any,
    flow: dict[str, Any] | None,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    current_ui_message: Any | None = None,
) -> Any:
    """Convenience wrapper around ``render_flow_ui`` for the remove flow."""
    return await render_flow_ui(
        ctx,
        user_id,
        anchor_message,
        flow,
        text,
        flow_key="remove",
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
        current_ui_message=current_ui_message,
    )


async def render_schedule_ui(
    ctx: HandlerContext,
    user_id: int,
    anchor_message: Any,
    flow: dict[str, Any] | None,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    current_ui_message: Any | None = None,
) -> Any:
    """Convenience wrapper around ``render_flow_ui`` for the schedule flow."""
    return await render_flow_ui(
        ctx,
        user_id,
        anchor_message,
        flow,
        text,
        flow_key="schedule",
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
        current_ui_message=current_ui_message,
    )


async def render_tv_ui(
    ctx: HandlerContext,
    user_id: int,
    anchor_message: Any,
    flow: dict[str, Any] | None,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool = True,
    current_ui_message: Any | None = None,
) -> Any:
    """Convenience wrapper around ``render_flow_ui`` for the TV-search flow."""
    return await render_flow_ui(
        ctx,
        user_id,
        anchor_message,
        flow,
        text,
        flow_key="tv",
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
        current_ui_message=current_ui_message,
    )
