"""Prefix-based callback dispatcher replacing the if/elif chain in on_callback."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

LOG = logging.getLogger("qbtg")

Handler = Callable[..., Awaitable[None]]


class CallbackDispatcher:
    """Routes Telegram callback data strings to registered handler coroutines.

    Supports two registration modes:
    - ``register_exact(data, handler)`` for exact string matches like ``"nav:home"``
    - ``register_prefix(prefix, handler)`` for prefix matches like ``"rm:"``

    Exact matches are checked first (O(1) dict lookup).  Prefix matches are
    tried longest-first so ``"sch:confirm:all"`` beats ``"sch:"`` when both
    are registered.
    """

    def __init__(self) -> None:
        self._exact: dict[str, Handler] = {}
        self._prefix: list[tuple[str, Handler]] = []

    def register_exact(self, data: str, handler: Handler) -> None:
        self._exact[data] = handler

    def register_prefix(self, prefix: str, handler: Handler) -> None:
        self._prefix.append((prefix, handler))
        self._prefix.sort(key=lambda x: len(x[0]), reverse=True)

    async def dispatch(self, data: str, **kwargs: Any) -> bool:
        """Dispatch *data* to the matching handler.

        Returns True if a handler was found and called, False otherwise.
        The handler receives ``data=data`` plus any extra *kwargs*
        (typically ``q`` and ``user_id``).
        """
        handler = self._exact.get(data)
        if handler is not None:
            await handler(data=data, **kwargs)
            return True
        for prefix, handler in self._prefix:
            if data.startswith(prefix):
                await handler(data=data, **kwargs)
                return True
        LOG.warning("Unhandled callback data: %s", data)
        return False
