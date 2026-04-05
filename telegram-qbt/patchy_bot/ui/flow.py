"""Flow state management — get/set/clear per-user modal state."""

from __future__ import annotations

from typing import Any

from ..types import HandlerContext


def set_flow(ctx: HandlerContext, user_id: int, payload: dict[str, Any]) -> None:
    """Store ``payload`` as the current flow state for ``user_id``."""
    ctx.user_flow[user_id] = payload


def get_flow(ctx: HandlerContext, user_id: int) -> dict[str, Any] | None:
    """Return the current flow state for ``user_id``, or ``None`` if absent."""
    return ctx.user_flow.get(user_id)


def clear_flow(ctx: HandlerContext, user_id: int) -> None:
    """Remove the flow state for ``user_id`` (no-op if not present)."""
    ctx.user_flow.pop(user_id, None)
