"""Tests for candidate cycling UI: keyboards, captions, and callback data."""

from __future__ import annotations

import pytest

from patchy_bot.ui.keyboards import candidate_nav_keyboard
from patchy_bot.ui.text import movie_candidate_caption, tv_candidate_caption


# ---------------------------------------------------------------------------
# Keyboard builder tests
# ---------------------------------------------------------------------------


class TestCandidateNavKeyboard:
    def test_single_result_no_nav_row(self) -> None:
        kb = candidate_nav_keyboard(
            pick_label="Show (2025)",
            pick_callback="sch:pick:0",
            candidate_idx=0,
            total_candidates=1,
            nav_prefix="sch:cnav",
        )
        rows = kb.inline_keyboard
        # Pick row + Home row = 2 rows, no nav row
        assert len(rows) == 2
        assert rows[0][0].text == "Show (2025)"
        assert rows[1][0].text == "🏠 Home"

    def test_multiple_results_has_nav_row(self) -> None:
        kb = candidate_nav_keyboard(
            pick_label="Show (2025)",
            pick_callback="sch:pick:1",
            candidate_idx=1,
            total_candidates=3,
            nav_prefix="sch:cnav",
        )
        rows = kb.inline_keyboard
        # Pick row + Nav row + Home row = 3 rows
        assert len(rows) == 3
        # Nav row has 2 buttons
        assert len(rows[1]) == 2

    def test_nav_buttons_wrap_around_forward(self) -> None:
        kb = candidate_nav_keyboard(
            pick_label="Show (2025)",
            pick_callback="sch:pick:4",
            candidate_idx=4,
            total_candidates=5,
            nav_prefix="sch:cnav",
        )
        nav_row = kb.inline_keyboard[1]
        next_btn = nav_row[1]
        # At idx 4 of 5, Next wraps to idx 0
        assert next_btn.callback_data == "sch:cnav:0"

    def test_nav_buttons_wrap_around_backward(self) -> None:
        kb = candidate_nav_keyboard(
            pick_label="Show (2025)",
            pick_callback="sch:pick:0",
            candidate_idx=0,
            total_candidates=5,
            nav_prefix="sch:cnav",
        )
        nav_row = kb.inline_keyboard[1]
        prev_btn = nav_row[0]
        # At idx 0 of 5, Prev wraps to idx 4
        assert prev_btn.callback_data == "sch:cnav:4"

    def test_nav_button_labels(self) -> None:
        kb = candidate_nav_keyboard(
            pick_label="Show (2025)",
            pick_callback="sch:pick:1",
            candidate_idx=1,
            total_candidates=5,
            nav_prefix="sch:cnav",
        )
        nav_row = kb.inline_keyboard[1]
        prev_btn = nav_row[0]
        next_btn = nav_row[1]
        assert prev_btn.text == "◀ Prev (1/5)"
        assert next_btn.text == "Next (3/5) ▶"

    def test_pick_callback_data(self) -> None:
        kb = candidate_nav_keyboard(
            pick_label="Daredevil (2025)",
            pick_callback="sch:pick:2",
            candidate_idx=2,
            total_candidates=5,
            nav_prefix="sch:cnav",
        )
        pick_btn = kb.inline_keyboard[0][0]
        assert pick_btn.callback_data == "sch:pick:2"
        assert pick_btn.text == "Daredevil (2025)"

    def test_nav_footer_fn_appended(self) -> None:
        from telegram import InlineKeyboardButton

        def mock_footer(include_home: bool = True) -> list[list[InlineKeyboardButton]]:
            return [[InlineKeyboardButton("⬅️ Back", callback_data="nav:back")]]

        kb = candidate_nav_keyboard(
            pick_label="Show (2025)",
            pick_callback="sch:pick:0",
            candidate_idx=0,
            total_candidates=3,
            nav_prefix="sch:cnav",
            nav_footer_fn=mock_footer,
        )
        rows = kb.inline_keyboard
        # Pick + Nav + Home + Footer = 4 rows
        assert len(rows) == 4
        assert rows[3][0].text == "⬅️ Back"


# ---------------------------------------------------------------------------
# Caption builder tests
# ---------------------------------------------------------------------------


class TestTvCandidateCaption:
    def test_format(self) -> None:
        candidate = {
            "name": "Daredevil: Born Again",
            "year": 2025,
            "status": "Running",
            "network": "Disney+",
        }
        caption = tv_candidate_caption(candidate, 1, 5)
        assert "(2 of 5)" in caption
        assert "Daredevil: Born Again" in caption
        assert "2025" in caption
        assert "Running" in caption
        assert "Disney+" in caption
        assert "Pick the Correct Show" in caption

    def test_missing_fields(self) -> None:
        candidate = {"name": "Unknown Show"}
        caption = tv_candidate_caption(candidate, 0, 1)
        assert "(1 of 1)" in caption
        assert "?" in caption  # year fallback
        assert "Unknown" in caption  # status fallback
        assert "Unknown network" in caption  # network fallback


class TestMovieCandidateCaption:
    def test_format(self) -> None:
        candidate = {"title": "Dune: Part Two", "year": 2024}
        caption = movie_candidate_caption(candidate, 0, 3, "dune")
        assert "(1 of 3)" in caption
        assert "Dune: Part Two" in caption
        assert "(2024)" in caption
        assert "dune" in caption
        assert "Results for" in caption

    def test_no_year(self) -> None:
        candidate = {"title": "Some Movie"}
        caption = movie_candidate_caption(candidate, 0, 1, "some movie")
        assert "(1 of 1)" in caption
        assert "Some Movie" in caption
        # No year parenthetical
        assert "( )" not in caption


# ---------------------------------------------------------------------------
# Callback data parsing tests
# ---------------------------------------------------------------------------


class TestCallbackDataFormat:
    def test_sch_cnav_parse(self) -> None:
        data = "sch:cnav:3"
        idx = int(data.split(":")[-1])
        assert idx == 3

    def test_msch_cnav_parse(self) -> None:
        data = "msch:cnav:2"
        idx = int(data.split(":")[-1])
        assert idx == 2
