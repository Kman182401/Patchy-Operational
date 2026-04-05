"""Base handler class that all domain handlers extend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..types import HandlerContext


class BaseHandler(ABC):
    """Abstract base for domain-specific handler modules.

    Each handler receives a HandlerContext at construction and uses it
    to access shared clients and state.  Subclasses must implement
    ``register_callbacks`` to wire their callback prefixes into the
    dispatcher.  ``register_commands`` is optional — override it to
    return (command_name, handler_coroutine) pairs.
    """

    def __init__(self, ctx: HandlerContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def register_callbacks(self, dispatcher: Any) -> None:
        """Register callback-query prefixes with the CallbackDispatcher."""

    def register_commands(self) -> list[tuple[str, Any]]:
        """Return (command_name, handler_coroutine) pairs to register.

        Override in subclasses that own slash commands.  The default
        returns an empty list.
        """
        return []
