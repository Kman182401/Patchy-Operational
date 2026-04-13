from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from patchy_bot.handlers.download import (
    batch_stop_keyboard,
    progress_bar,
    render_batch_monitor_text,
    start_batch_monitor,
)


def test_render_batch_monitor_text_empty_state() -> None:
    assert render_batch_monitor_text([]) == "<b>⬇️ All downloads complete</b>"


def test_render_batch_monitor_text_single_entry() -> None:
    text = render_batch_monitor_text(
        [
            {
                "title": "Show & Co S01E01 1080p",
                "info": {
                    "progress": 0.453,
                    "eta": 201,
                    "size": 1_000_000_000,
                    "completed": 453_000_000,
                    "state": "downloading",
                },
                "progress_pct": 45.3,
            }
        ]
    )

    assert "<b>⬇️ Downloading</b> · <i>1 active</i>" in text
    assert "<code>Show &amp; Co S01E01 1080p</code>" in text
    assert f"<code>[{progress_bar(45.3)}] 45.3%</code> · ETA <code>00:03:21</code>" in text


def test_render_batch_monitor_text_three_entries() -> None:
    text = render_batch_monitor_text(
        [
            {
                "title": "Alpha S01E01 1080p",
                "info": {"progress": 0.1, "eta": 120, "state": "downloading"},
                "progress_pct": 10.0,
            },
            {
                "title": "Beta S01E02 1080p",
                "info": {"progress": 0.5, "eta": 3600, "state": "downloading"},
                "progress_pct": 50.0,
            },
            {
                "title": "Gamma S01E03 1080p",
                "info": {"progress": 0.9, "eta": 8640001, "state": "downloading"},
                "progress_pct": 90.0,
            },
        ]
    )

    assert "<i>3 active</i>" in text
    assert text.count("<code>") == 9
    assert text.count("\n\n") == 3
    assert "<code>Gamma S01E03 1080p</code>" in text


def test_batch_stop_keyboard_uses_namespaced_callback_data() -> None:
    keyboard = batch_stop_keyboard(
        [
            "hash-a",
            "hash-b",
            "hash-c",
        ]
    ).inline_keyboard

    assert [[button.text for button in row] for row in keyboard] == [["🏠 Home", "🛑 Stop All Downloads"]]
    callback_data = keyboard[0][1].callback_data
    assert callback_data is not None
    assert callback_data.startswith("stop:all:")  # pyright: ignore[reportAttributeAccessIssue]
    assert len(callback_data.encode("utf-8")) <= 64  # pyright: ignore[reportAttributeAccessIssue]
    assert callback_data == "stop:all:hash-a,hash-b,hash-c"


class _FakeBatchMessage:
    def __init__(self, chat_id: int, text: str, reply_markup) -> None:
        self.chat_id = chat_id
        self.text = text
        self.reply_markup = reply_markup
        self.edit_calls: list[dict[str, object]] = []
        self.deleted = False

    async def edit_text(self, text: str, *, reply_markup=None, parse_mode=None) -> None:
        self.text = text
        self.reply_markup = reply_markup
        self.edit_calls.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})

    async def delete(self) -> None:
        self.deleted = True


class _FakeBatchBot:
    def __init__(self) -> None:
        self.sent_messages: list[_FakeBatchMessage] = []

    async def send_message(self, *, chat_id: int, text: str, reply_markup=None, parse_mode=None):
        msg = _FakeBatchMessage(chat_id, text, reply_markup)
        self.sent_messages.append(msg)
        return msg


@pytest.mark.asyncio
async def test_batch_monitor_loop_edits_single_message_and_cleans_up() -> None:
    bot = _FakeBatchBot()
    qbt_state = {
        "progress": 0.10,
        "eta": 120,
        "state": "downloading",
    }

    class FakeQbt:
        def get_torrent(self, torrent_hash: str) -> dict[str, object]:
            assert torrent_hash == "hash-a"
            return dict(qbt_state)

    async def _progress_task() -> None:
        await asyncio.sleep(10)

    progress_task = asyncio.create_task(_progress_task())
    ctx = SimpleNamespace(
        cfg=SimpleNamespace(progress_refresh_s=0.01),
        qbt=FakeQbt(),
        app=SimpleNamespace(bot=bot),
        progress_tasks={(7, "hash-a"): progress_task},
        batch_monitor_tasks={},
        batch_monitor_messages={},
        batch_monitor_data={
            (7, "hash-a"): {
                "title": "Alpha S01E01 1080p",
                "info": dict(qbt_state),
                "progress_pct": 10.0,
                "dls_bps": 0,
            }
        },
    )

    start_batch_monitor(ctx, 7, 12345)  # pyright: ignore[reportArgumentType]
    await asyncio.sleep(0.03)

    assert len(bot.sent_messages) == 1
    msg = bot.sent_messages[0]
    assert "Alpha S01E01 1080p" in msg.text
    assert "stop:all:hash-a" == msg.reply_markup.inline_keyboard[0][1].callback_data  # pyright: ignore[reportOptionalMemberAccess]

    qbt_state["progress"] = 0.20
    qbt_state["eta"] = 90
    ctx.batch_monitor_data[(7, "hash-a")]["progress_pct"] = 20.0
    await asyncio.sleep(0.03)

    assert msg.edit_calls
    assert "20.0%" in str(msg.edit_calls[-1]["text"])

    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    await asyncio.wait_for(ctx.batch_monitor_tasks[7], timeout=0.2)

    assert msg.deleted is True
    assert ctx.batch_monitor_tasks == {}
    assert ctx.batch_monitor_messages == {}
