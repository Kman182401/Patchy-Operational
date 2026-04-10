"""Tests for callback routing and state transitions.

Covers menu:*, flow:*, stop:*, rm:*, sch:* callbacks and the
CallbackDispatcher routing logic.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from patchy_bot.dispatch import CallbackDispatcher
from patchy_bot.handlers.commands import on_cb_flow, on_cb_menu
from patchy_bot.handlers.download import on_cb_stop
from patchy_bot.handlers.remove import on_cb_remove
from patchy_bot.handlers.schedule import on_cb_schedule
from patchy_bot.types import HandlerContext

# ---------------------------------------------------------------------------
# FakeBotApp — captures rendering/flow calls made by handler functions
# ---------------------------------------------------------------------------


class FakeBotApp:
    """Minimal stand-in for BotApp that records method calls.

    Handlers call ``bot_app._set_flow()``, ``bot_app._render_nav_ui()``, etc.
    This fake captures those calls so tests can assert on them.
    """

    def __init__(self, ctx: HandlerContext) -> None:
        self._ctx = ctx
        self.store = ctx.store
        self.cfg = ctx.cfg
        self.qbt = ctx.qbt
        self.plex = ctx.plex
        self.flow: dict[int, dict[str, Any]] = {}
        self.render_calls: list[tuple[str, tuple, dict]] = []
        self.progress_tasks: dict[tuple[int, str], Any] = ctx.progress_tasks
        # Wire render_command_center and navigate_to_command_center on ctx so handlers can use them
        ctx.render_command_center = self._render_command_center
        ctx.navigate_to_command_center = self._navigate_to_command_center

    # -- Flow management --

    def _set_flow(self, user_id: int, flow: dict[str, Any]) -> None:
        self.flow[user_id] = flow

    def _get_flow(self, user_id: int) -> dict[str, Any] | None:
        return self.flow.get(user_id)

    def _clear_flow(self, user_id: int) -> None:
        self.flow.pop(user_id, None)

    def _cancel_pending_trackers_for_user(self, user_id: int) -> None:
        pass  # no-op for tests

    async def _on_cb_nav_home(self, *, data: str, q: Any, user_id: int) -> None:
        self._clear_flow(user_id)
        self._cancel_pending_trackers_for_user(user_id)
        await self._navigate_to_command_center(q.message, user_id, current_ui_message=q.message)

    # -- Nav UI tracking (Command Center location) --

    user_nav_ui: dict[int, Any] = {}

    # -- Rendering stubs (record calls) --

    async def _render_nav_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("nav_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = 12345
        m.message_id = 1
        return m

    async def _render_remove_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("remove_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = 12345
        m.message_id = 1
        return m

    async def _render_schedule_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("schedule_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = 12345
        m.message_id = 1
        return m

    async def _render_tv_ui(self, *args: Any, **kwargs: Any) -> MagicMock:
        self.render_calls.append(("tv_ui", args, kwargs))
        m = MagicMock()
        m.chat_id = 12345
        m.message_id = 1
        return m

    async def _render_command_center(self, *args: Any, **kwargs: Any) -> None:
        self.render_calls.append(("command_center", args, kwargs))

    async def _navigate_to_command_center(self, msg: Any, user_id: int, **kwargs: Any) -> None:
        self.render_calls.append(("command_center", (msg,), {"user_id": user_id, **kwargs}))

    async def _open_remove_browse_root(self, *args: Any, **kwargs: Any) -> None:
        self.render_calls.append(("remove_browse_root", args, kwargs))

    async def _render_active_ui(self, *args: Any, **kwargs: Any) -> None:
        self.render_calls.append(("active_ui", args, kwargs))

    async def _render_categories_ui(self, *args: Any, **kwargs: Any) -> None:
        self.render_calls.append(("categories_ui", args, kwargs))

    async def _render_plugins_ui(self, *args: Any, **kwargs: Any) -> None:
        self.render_calls.append(("plugins_ui", args, kwargs))

    # -- UI builder stubs --

    def _nav_footer(self, **kwargs: Any) -> list[list[Any]]:
        return [[]]

    def _home_only_keyboard(self) -> MagicMock:
        return MagicMock()

    def _schedule_start_flow(self, user_id: int) -> None:
        self.flow[user_id] = {"mode": "schedule", "stage": "await_show"}

    def _help_text(self) -> str:
        return "<b>Help</b>\nSome help text."

    def _tv_filter_choice_text(self) -> str:
        return "Choose a filter option"

    def _tv_filter_choice_keyboard(self) -> MagicMock:
        return MagicMock()

    def _tv_filter_prompt_text(self) -> str:
        return "Enter filter text"

    def _tv_title_prompt_text(self) -> str:
        return "Enter show title"

    def _storage_status(self) -> tuple[bool, str]:
        return True, "ready"

    def _qbt_transport_status(self) -> tuple[bool, str]:
        return True, "connected"

    def _vpn_ready_for_download(self) -> tuple[bool, str]:
        return True, "ok"

    def _plex_storage_display(self) -> str:
        return "100 GiB free"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_app(mock_ctx: HandlerContext) -> FakeBotApp:
    """FakeBotApp wired to the shared mock_ctx fixture."""
    return FakeBotApp(mock_ctx)


@pytest.fixture
def query() -> MagicMock:
    """Mock Telegram CallbackQuery with async answer/edit/reply."""
    q = MagicMock()
    q.data = "nav:home"
    q.answer = AsyncMock()

    reply_msg = MagicMock()
    reply_msg.chat_id = 12345
    reply_msg.message_id = 999

    q.message = MagicMock()
    q.message.edit_text = AsyncMock()
    q.message.reply_text = AsyncMock(return_value=reply_msg)
    q.message.delete = AsyncMock()
    q.message.chat_id = 12345
    q.message.message_id = 100
    q.message.get_bot = MagicMock(return_value=MagicMock())
    return q


USER_ID = 12345


# ---------------------------------------------------------------------------
# Menu callbacks (handlers/commands.py: on_cb_menu)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_menu_movie_starts_flow(fake_app: FakeBotApp, query: MagicMock) -> None:
    """menu:movie sets flow to movie/await_title and renders nav_ui."""
    await on_cb_menu(fake_app, data="menu:movie", q=query, user_id=USER_ID)

    assert fake_app.flow[USER_ID]["mode"] == "movie"
    assert fake_app.flow[USER_ID]["stage"] == "await_title"
    assert any(name == "nav_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_menu_tv_starts_flow(fake_app: FakeBotApp, query: MagicMock) -> None:
    """menu:tv sets flow to tv/await_filter_choice and renders tv_ui."""
    await on_cb_menu(fake_app, data="menu:tv", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["mode"] == "tv"
    assert flow["stage"] == "await_filter_choice"
    assert any(name == "tv_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_menu_schedule_no_tracks(
    fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """menu:schedule with no tracks starts the schedule flow in schedule_ui."""
    monkeypatch.setattr("asyncio.to_thread", AsyncMock(return_value=[]))

    await on_cb_menu(fake_app, data="menu:schedule", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["mode"] == "schedule"
    assert flow["stage"] == "await_show"
    assert any(name == "schedule_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_menu_schedule_with_tracks(
    fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """menu:schedule with existing tracks shows the schedule menu with count."""
    tracks = [
        {"track_id": "t1", "enabled": True, "show_name": "Show A"},
        {"track_id": "t2", "enabled": False, "show_name": "Show B"},
    ]
    monkeypatch.setattr("asyncio.to_thread", AsyncMock(return_value=tracks))

    await on_cb_menu(fake_app, data="menu:schedule", q=query, user_id=USER_ID)

    # Should render nav_ui with schedule info, not start a new flow
    assert any(name == "nav_ui" for name, _, _ in fake_app.render_calls)
    # The rendered text should mention the track count
    for name, args, kwargs in fake_app.render_calls:
        if name == "nav_ui":
            text_arg = args[2] if len(args) > 2 else kwargs.get("text", "")
            if isinstance(text_arg, str):
                assert "1" in text_arg  # 1 active track


@pytest.mark.asyncio
async def test_cb_schedule_addnew_uses_schedule_ui(fake_app: FakeBotApp, query: MagicMock) -> None:
    """sch:addnew should remember the schedule flow message for later replacement."""
    await on_cb_schedule(fake_app, data="sch:addnew", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["mode"] == "schedule"
    assert flow["stage"] == "await_show"
    assert any(name == "schedule_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_menu_remove_opens_browse(fake_app: FakeBotApp, query: MagicMock) -> None:
    """menu:remove calls _open_remove_browse_root."""
    await on_cb_menu(fake_app, data="menu:remove", q=query, user_id=USER_ID)

    assert any(name == "remove_browse_root" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_menu_active_renders(fake_app: FakeBotApp, query: MagicMock) -> None:
    """menu:active calls _render_active_ui."""
    await on_cb_menu(fake_app, data="menu:active", q=query, user_id=USER_ID)

    assert any(name == "active_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_menu_help_renders(fake_app: FakeBotApp, query: MagicMock) -> None:
    """menu:help renders nav_ui with help text."""
    await on_cb_menu(fake_app, data="menu:help", q=query, user_id=USER_ID)

    rendered = [c for c in fake_app.render_calls if c[0] == "nav_ui"]
    assert len(rendered) >= 1
    # The help text should be passed as a positional arg
    text_arg = rendered[0][1][2] if len(rendered[0][1]) > 2 else ""
    assert "Help" in text_arg


@pytest.mark.asyncio
async def test_cb_menu_profile_renders(fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """menu:profile renders nav_ui with profile/status info."""
    # Store.get_defaults returns a dict
    fake_app.store.get_defaults = MagicMock(
        return_value={
            "default_min_seeds": 5,
            "default_sort": "quality",
            "default_order": "desc",
            "default_limit": 10,
        }
    )
    # asyncio.to_thread calls sync functions; mock it to just call them
    original_to_thread = asyncio.to_thread

    async def passthrough_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr("asyncio.to_thread", passthrough_to_thread)

    await on_cb_menu(fake_app, data="menu:profile", q=query, user_id=USER_ID)

    rendered = [c for c in fake_app.render_calls if c[0] == "nav_ui"]
    assert len(rendered) >= 1
    text_arg = rendered[0][1][2] if len(rendered[0][1]) > 2 else ""
    assert "min_seeds" in text_arg
    assert "storage status" in text_arg


# ---------------------------------------------------------------------------
# Flow callbacks (handlers/commands.py: on_cb_flow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_flow_tv_filter_set(fake_app: FakeBotApp, query: MagicMock) -> None:
    """flow:tv_filter_set transitions to await_filter stage."""
    await on_cb_flow(fake_app, data="flow:tv_filter_set", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["mode"] == "tv"
    assert flow["stage"] == "await_filter"
    assert any(name == "tv_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_flow_tv_filter_skip(fake_app: FakeBotApp, query: MagicMock) -> None:
    """flow:tv_filter_skip transitions to await_title stage."""
    await on_cb_flow(fake_app, data="flow:tv_filter_skip", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["mode"] == "tv"
    assert flow["stage"] == "await_title"
    assert any(name == "tv_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_flow_tv_full_series(fake_app: FakeBotApp, query: MagicMock) -> None:
    """flow:tv_full_series transitions to await_title with full_series=True."""
    await on_cb_flow(fake_app, data="flow:tv_full_series", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["mode"] == "tv"
    assert flow["stage"] == "await_title"
    assert flow.get("full_series") is True
    assert any(name == "tv_ui" for name, _, _ in fake_app.render_calls)


# ---------------------------------------------------------------------------
# Stop callback (handlers/download.py: on_cb_stop)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_stop_cancels_task(fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """stop:hash cancels the progress task, deletes the torrent, and navigates to CC."""
    torrent_hash = "a" * 40

    # Plant a fake progress task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_task.cancel = MagicMock()
    fake_app.progress_tasks[(USER_ID, torrent_hash)] = mock_task

    # asyncio.to_thread: first call = get_torrent (returns info), second = delete_torrent,
    # third = get_command_center (from CC nav logic)
    call_count = 0
    torrent_info = {"category": "Movies", "name": "Test Movie"}

    async def fake_to_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return torrent_info
        if call_count == 2:
            return None  # delete_torrent returns nothing
        return None  # get_command_center fallback

    monkeypatch.setattr("patchy_bot.handlers.download.asyncio.to_thread", fake_to_thread)

    # Stub send_message for confirmation notice
    notice_mock = MagicMock()
    notice_mock.message_id = 999
    query.message.chat.send_message = AsyncMock(return_value=notice_mock)

    await on_cb_stop(fake_app._ctx, data=f"stop:{torrent_hash}", q=query, user_id=USER_ID)

    mock_task.cancel.assert_called_once()
    # Should navigate to command center
    assert any(name == "command_center" for name, _, _ in fake_app.render_calls)
    # Should send a confirmation notice with no reply_markup
    query.message.chat.send_message.assert_called_once()
    sent_kwargs = query.message.chat.send_message.call_args
    assert "reply_markup" not in (sent_kwargs.kwargs or {})
    assert "Test Movie" in sent_kwargs[0][0]


@pytest.mark.asyncio
async def test_cb_stop_delete_fails(fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """stop:hash shows error when qbt.delete_torrent raises."""
    torrent_hash = "b" * 40

    call_count = 0

    async def fake_to_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"category": "Movies", "name": "Test Movie"}
        raise ConnectionError("qBT unreachable")

    monkeypatch.setattr("patchy_bot.handlers.download.asyncio.to_thread", fake_to_thread)

    await on_cb_stop(fake_app._ctx, data=f"stop:{torrent_hash}", q=query, user_id=USER_ID)

    query.message.edit_text.assert_called_once()
    assert "Failed" in query.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_cb_stop_tv_category_navigates_to_cc(
    fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stop:hash for a TV-category torrent navigates to CC with confirmation."""
    torrent_hash = "c" * 40

    call_count = 0

    async def fake_to_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"category": "TV", "name": "Test.Show.S01E01"}
        if call_count == 2:
            return None  # delete_torrent
        return None  # get_command_center

    monkeypatch.setattr("patchy_bot.handlers.download.asyncio.to_thread", fake_to_thread)

    notice_mock = MagicMock()
    notice_mock.message_id = 999
    query.message.chat.send_message = AsyncMock(return_value=notice_mock)

    await on_cb_stop(fake_app._ctx, data=f"stop:{torrent_hash}", q=query, user_id=USER_ID)

    # Should navigate to command center
    assert any(name == "command_center" for name, _, _ in fake_app.render_calls)
    # Confirmation notice should mention the torrent name
    query.message.chat.send_message.assert_called_once()
    assert "Test.Show.S01E01" in query.message.chat.send_message.call_args[0][0]


@pytest.mark.asyncio
async def test_nav_home_edits_message_in_place(fake_app: FakeBotApp, query: MagicMock) -> None:
    """nav:home must never call delete() — it edits the message in-place."""
    fake_app._set_flow(USER_ID, {"mode": "schedule", "stage": "main"})

    await fake_app._on_cb_nav_home(data="nav:home", q=query, user_id=USER_ID)

    # delete must never be called
    query.message.delete.assert_not_called()
    # Should navigate to command center with current_ui_message
    cc_calls = [(args, kwargs) for name, args, kwargs in fake_app.render_calls if name == "command_center"]
    assert len(cc_calls) >= 1
    _, kwargs = cc_calls[0]
    assert kwargs.get("current_ui_message") is query.message


@pytest.mark.asyncio
async def test_stop_callback_edits_tracker_in_place(
    fake_app: FakeBotApp, query: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """stop:hash must never call delete() — it edits the tracker message in-place."""
    torrent_hash = "d" * 40
    call_count = 0

    async def fake_to_thread(fn, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"category": "Movies", "name": "Test Movie"}
        if call_count == 2:
            return None  # delete_torrent
        return None

    monkeypatch.setattr("patchy_bot.handlers.download.asyncio.to_thread", fake_to_thread)

    notice_mock = MagicMock()
    notice_mock.message_id = 999
    query.message.chat.send_message = AsyncMock(return_value=notice_mock)

    await on_cb_stop(fake_app._ctx, data=f"stop:{torrent_hash}", q=query, user_id=USER_ID)

    # delete must never be called on the tracker message
    query.message.delete.assert_not_called()
    # Should navigate to command center with current_ui_message
    cc_calls = [(args, kwargs) for name, args, kwargs in fake_app.render_calls if name == "command_center"]
    assert len(cc_calls) >= 1
    _, kwargs = cc_calls[0]
    assert kwargs.get("current_ui_message") is query.message


# ---------------------------------------------------------------------------
# Remove cancel/browse (handlers/remove.py: on_cb_remove)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_remove_cancel_clears_flow(fake_app: FakeBotApp, query: MagicMock) -> None:
    """rm:cancel clears flow and renders command center."""
    fake_app._set_flow(USER_ID, {"mode": "remove", "stage": "choose_item"})

    await on_cb_remove(fake_app, data="rm:cancel", q=query, user_id=USER_ID)

    assert fake_app._get_flow(USER_ID) is None
    assert any(name == "command_center" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_remove_browse_opens_root(fake_app: FakeBotApp, query: MagicMock) -> None:
    """rm:browse calls _open_remove_browse_root."""
    await on_cb_remove(fake_app, data="rm:browse", q=query, user_id=USER_ID)

    assert any(name == "remove_browse_root" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_remove_browsecat_movies_renders_library(fake_app: FakeBotApp, query: MagicMock, tmp_path) -> None:
    movies_dir = tmp_path / "Movies"
    (movies_dir / "Movie.One.2024.mkv").write_text("x")
    fake_app.cfg.movies_path = str(movies_dir)

    await on_cb_remove(fake_app, data="rm:browsecat:movies", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["stage"] == "choose_item"
    assert flow["browse_category"] == "movies"
    assert any(name == "remove_ui" for name, _, _ in fake_app.render_calls)


@pytest.mark.asyncio
async def test_cb_remove_browsecat_tv_renders_library(fake_app: FakeBotApp, query: MagicMock, tmp_path) -> None:
    tv_dir = tmp_path / "TV"
    (tv_dir / "Show.Name.S01E02.1080p.mkv").write_text("x")
    fake_app.cfg.tv_path = str(tv_dir)

    await on_cb_remove(fake_app, data="rm:browsecat:tv", q=query, user_id=USER_ID)

    flow = fake_app.flow[USER_ID]
    assert flow["stage"] == "choose_item"
    assert flow["browse_category"] == "tv"
    assert any(name == "remove_ui" for name, _, _ in fake_app.render_calls)


# ---------------------------------------------------------------------------
# Schedule cancel (handlers/schedule.py: on_cb_schedule)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_schedule_cancel_clears_flow(fake_app: FakeBotApp, query: MagicMock) -> None:
    """sch:cancel clears flow and renders command center."""
    fake_app._set_flow(USER_ID, {"mode": "schedule", "stage": "await_show"})

    await on_cb_schedule(fake_app, data="sch:cancel", q=query, user_id=USER_ID)

    assert fake_app._get_flow(USER_ID) is None
    assert any(name == "command_center" for name, _, _ in fake_app.render_calls)


# ---------------------------------------------------------------------------
# CallbackDispatcher integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_routes_menu_to_handler() -> None:
    """CallbackDispatcher routes 'menu:movie' to the registered handler."""
    dispatcher = CallbackDispatcher()
    received: list[dict] = []

    async def handler(**kwargs: Any) -> None:
        received.append(kwargs)

    dispatcher.register_prefix("menu:", handler)

    found = await dispatcher.dispatch("menu:movie", q=MagicMock(), user_id=USER_ID)

    assert found is True
    assert len(received) == 1
    assert received[0]["data"] == "menu:movie"


@pytest.mark.asyncio
async def test_dispatch_routes_rm_to_handler() -> None:
    """CallbackDispatcher routes 'rm:cancel' to the registered handler."""
    dispatcher = CallbackDispatcher()
    received: list[dict] = []

    async def handler(**kwargs: Any) -> None:
        received.append(kwargs)

    dispatcher.register_prefix("rm:", handler)

    found = await dispatcher.dispatch("rm:cancel", q=MagicMock(), user_id=USER_ID)

    assert found is True
    assert len(received) == 1
    assert received[0]["data"] == "rm:cancel"


@pytest.mark.asyncio
async def test_dispatch_routes_stop_to_handler() -> None:
    """CallbackDispatcher routes 'stop:abc123' to the registered handler."""
    dispatcher = CallbackDispatcher()
    received: list[dict] = []

    async def handler(**kwargs: Any) -> None:
        received.append(kwargs)

    dispatcher.register_prefix("stop:", handler)

    found = await dispatcher.dispatch("stop:abc123", q=MagicMock(), user_id=USER_ID)

    assert found is True
    assert len(received) == 1
    assert received[0]["data"] == "stop:abc123"


@pytest.mark.asyncio
async def test_dispatch_exact_beats_prefix() -> None:
    """Exact match takes priority over prefix match."""
    dispatcher = CallbackDispatcher()
    exact_calls: list[str] = []
    prefix_calls: list[str] = []

    async def exact_handler(**kwargs: Any) -> None:
        exact_calls.append(kwargs["data"])

    async def prefix_handler(**kwargs: Any) -> None:
        prefix_calls.append(kwargs["data"])

    dispatcher.register_exact("nav:home", exact_handler)
    dispatcher.register_prefix("nav:", prefix_handler)

    found = await dispatcher.dispatch("nav:home")

    assert found is True
    assert exact_calls == ["nav:home"]
    assert prefix_calls == []


@pytest.mark.asyncio
async def test_dispatch_unhandled_returns_false() -> None:
    """Dispatch returns False for unrecognized callback data."""
    dispatcher = CallbackDispatcher()

    found = await dispatcher.dispatch("unknown:data")

    assert found is False
