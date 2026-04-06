"""Tests for patchy_bot.dispatch — CallbackDispatcher routing logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from patchy_bot.dispatch import CallbackDispatcher

# ---------------------------------------------------------------------------
# Exact-match tests
# ---------------------------------------------------------------------------


async def test_dispatch_exact_match_found_and_called() -> None:
    """Exact registration dispatches to the correct handler."""
    d = CallbackDispatcher()
    handler = AsyncMock()
    d.register_exact("nav:home", handler)

    result = await d.dispatch("nav:home")

    assert result is True
    handler.assert_awaited_once_with(data="nav:home")


async def test_dispatch_passes_kwargs_to_handler() -> None:
    """Extra kwargs passed to dispatch() are forwarded to the handler."""
    d = CallbackDispatcher()
    handler = AsyncMock()
    d.register_exact("nav:home", handler)

    q = object()  # stand-in for a CallbackQuery
    await d.dispatch("nav:home", q=q, user_id=123)

    handler.assert_awaited_once_with(data="nav:home", q=q, user_id=123)


# ---------------------------------------------------------------------------
# Prefix-match tests
# ---------------------------------------------------------------------------


async def test_dispatch_prefix_match_found_and_called() -> None:
    """Prefix registration matches data that starts with the prefix."""
    d = CallbackDispatcher()
    handler = AsyncMock()
    d.register_prefix("rm:", handler)

    result = await d.dispatch("rm:delete:123")

    assert result is True
    handler.assert_awaited_once_with(data="rm:delete:123")


async def test_dispatch_longest_prefix_wins() -> None:
    """When two prefixes match, the longer one takes priority."""
    d = CallbackDispatcher()
    short_handler = AsyncMock()
    long_handler = AsyncMock()

    d.register_prefix("sch:", short_handler)
    d.register_prefix("sch:confirm:", long_handler)

    result = await d.dispatch("sch:confirm:all")

    assert result is True
    long_handler.assert_awaited_once_with(data="sch:confirm:all")
    short_handler.assert_not_awaited()


async def test_dispatch_prefix_ordering_preserved_after_multiple_registers() -> None:
    """Registering a short prefix first, then a long one, still routes to the long one."""
    d = CallbackDispatcher()
    short_handler = AsyncMock()
    long_handler = AsyncMock()

    # Register short FIRST, long SECOND — ordering should still prefer long
    d.register_prefix("d:", short_handler)
    d.register_prefix("d:confirm:", long_handler)

    result = await d.dispatch("d:confirm:yes")

    assert result is True
    long_handler.assert_awaited_once_with(data="d:confirm:yes")
    short_handler.assert_not_awaited()


# ---------------------------------------------------------------------------
# Priority: exact > prefix
# ---------------------------------------------------------------------------


async def test_dispatch_exact_takes_priority_over_prefix() -> None:
    """An exact match is used even when a prefix also matches."""
    d = CallbackDispatcher()
    exact_handler = AsyncMock()
    prefix_handler = AsyncMock()

    d.register_exact("nav:home", exact_handler)
    d.register_prefix("nav:", prefix_handler)

    result = await d.dispatch("nav:home")

    assert result is True
    exact_handler.assert_awaited_once_with(data="nav:home")
    prefix_handler.assert_not_awaited()


# ---------------------------------------------------------------------------
# Unhandled data
# ---------------------------------------------------------------------------


async def test_dispatch_unhandled_returns_false() -> None:
    """Dispatch returns False when no handler matches."""
    d = CallbackDispatcher()

    result = await d.dispatch("unknown:data")

    assert result is False


async def test_dispatch_unhandled_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warning is logged when no handler matches the callback data."""
    d = CallbackDispatcher()
    mock_warning = Mock()
    monkeypatch.setattr("patchy_bot.dispatch.LOG.warning", mock_warning)

    await d.dispatch("unknown:data")

    mock_warning.assert_called_once_with("Unhandled callback data: %s", "unknown:data")
