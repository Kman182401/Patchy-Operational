"""Shared keyboard builders used across multiple flows."""

from __future__ import annotations

import math
from collections.abc import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ---------------------------------------------------------------------------
# Navigation footer
# ---------------------------------------------------------------------------


def nav_footer(*, back_data: str = "", include_home: bool = True) -> list[list[InlineKeyboardButton]]:
    """Return a navigation footer row: optional Back + optional Home button."""
    nav: list[InlineKeyboardButton] = []
    if back_data:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=back_data))
    if include_home:
        nav.append(InlineKeyboardButton("🏠 Home", callback_data="nav:home"))
    return [nav] if nav else []


def home_only_keyboard() -> InlineKeyboardMarkup:
    """Single-row keyboard containing only the Home button."""
    return InlineKeyboardMarkup(nav_footer(include_home=True))


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def compact_action_rows(
    rows: list[list[InlineKeyboardButton]], *, max_buttons: int = 5, columns: int = 2
) -> list[list[InlineKeyboardButton]]:
    """Re-flow ``rows`` into a compact grid when there are few buttons.

    If the total button count exceeds ``max_buttons``, the original ``rows``
    are returned unchanged.  Otherwise buttons are re-arranged into a grid of
    ``columns`` per row.
    """
    buttons = [button for row in rows for button in row]
    if not buttons or len(buttons) > max_buttons:
        return rows
    return [buttons[idx : idx + max(1, columns)] for idx in range(0, len(buttons), max(1, columns))]


# ---------------------------------------------------------------------------
# Top-level keyboards
# ---------------------------------------------------------------------------


def command_center_keyboard(
    active_downloads: list[tuple[str, str]] | None = None,
) -> InlineKeyboardMarkup:
    """Main command-center keyboard shown on /start.

    Args:
        active_downloads: Optional list of ``(torrent_hash, display_name)``
            tuples.  When non-empty a cancel button is shown for each (up to 3).
    """
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("🎬 Movie Search", callback_data="menu:movie"),
            InlineKeyboardButton("📺 TV Search", callback_data="menu:tv"),
        ],
        [
            InlineKeyboardButton("🗓️ Schedule", callback_data="menu:schedule"),
            InlineKeyboardButton("🗑️ Remove", callback_data="menu:remove"),
        ],
    ]
    if active_downloads:
        count = len(active_downloads)
        rows.append([InlineKeyboardButton(f"🛑 Manage Downloads ({count})", callback_data="dl:manage")])
    rows.append([InlineKeyboardButton("ℹ️ Help", callback_data="menu:help")])
    return InlineKeyboardMarkup(rows)


def manage_downloads_keyboard(
    active_downloads: list[tuple[str, str]],
) -> InlineKeyboardMarkup:
    """Keyboard for the downloads management sub-page.

    Shows individual stop buttons for each active download with a Back button.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for torrent_hash, name in active_downloads:
        label = name[:33] + "…" if len(name) > 34 else name
        rows.append([InlineKeyboardButton(f"🛑 {label}", callback_data=f"stop:{torrent_hash}")])
    if not rows:
        rows.append([InlineKeyboardButton("📭 No active downloads", callback_data="nav:home")])
    rows.extend(nav_footer(back_data="nav:home", include_home=False))
    return InlineKeyboardMarkup(rows)


def tv_filter_choice_keyboard() -> InlineKeyboardMarkup:
    """Keyboard presented when the user starts a TV search."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("➕ Set Season+Episode", callback_data="flow:tv_filter_set"),
            InlineKeyboardButton("⏭ Skip Filters", callback_data="flow:tv_filter_skip"),
        ],
        [
            InlineKeyboardButton("📦 Full Season", callback_data="flow:tv_full_season"),
        ],
        [
            InlineKeyboardButton("📦 Full Series", callback_data="flow:tv_full_series"),
        ],
    ]
    rows.extend(nav_footer(back_data="nav:home", include_home=False))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Post-add action keyboards
# ---------------------------------------------------------------------------


def post_add_movie_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after adding a movie search result."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎬 Search Again", callback_data="moviepost:search_again")],
            [InlineKeyboardButton("🏠 Home", callback_data="nav:home")],
        ]
    )


def post_add_tv_standard_keyboard(
    sid: str,
    *,
    next_ep_data: str | None = None,
) -> InlineKeyboardMarkup:
    """Keyboard shown after adding a standard TV episode."""
    rows: list[list[InlineKeyboardButton]] = []
    if next_ep_data:
        rows.append([InlineKeyboardButton("⏭ Download Next Episode", callback_data=next_ep_data)])
    rows.append([InlineKeyboardButton("📺 Download Another Episode", callback_data=f"tvpost:another_ep:{sid}")])
    rows.append([InlineKeyboardButton("📺 Search Again", callback_data="tvpost:search_again")])
    rows.append([InlineKeyboardButton("🏠 Home", callback_data="nav:home")])
    return InlineKeyboardMarkup(rows)


def post_add_tv_full_season_keyboard(sid: str) -> InlineKeyboardMarkup:
    """Keyboard shown after adding a full season pack."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Download Another Season", callback_data=f"tvpost:another_season:{sid}")],
            [InlineKeyboardButton("📺 Search Again", callback_data="tvpost:search_again")],
            [InlineKeyboardButton("🏠 Home", callback_data="nav:home")],
        ]
    )


def post_add_tv_full_series_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after adding a full series."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📺 Search Again", callback_data="tvpost:search_again")],
            [InlineKeyboardButton("🏠 Home", callback_data="nav:home")],
        ]
    )


def tv_show_picker_keyboard(results: list[dict[str, object]], back_data: str) -> InlineKeyboardMarkup:
    """Keyboard for the TVMaze show picker (Phase A).

    Emits one button per result with callback ``tvpick:{index}``. Footer uses
    the shared nav_footer with Back + Home.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for idx, show in enumerate(results):
        name = str(show.get("name") or "Unknown")
        year = show.get("year")
        if year:
            label = f"📺 {name} ({year})"
        else:
            label = f"📺 {name}"
        if len(label) > 60:
            label = label[:59] + "…"
        rows.append([InlineKeyboardButton(label, callback_data=f"tvpick:{idx}")])
    rows.extend(nav_footer(back_data=back_data, include_home=True))
    return InlineKeyboardMarkup(rows)


def movie_picker_keyboard(results: list[dict[str, object]], back_data: str) -> InlineKeyboardMarkup:
    """Keyboard for the TMDB movie picker (Phase A).

    Emits one button per result with callback ``moviepick:{index}``. Footer
    uses the shared nav_footer with Back + Home.
    """
    rows: list[list[InlineKeyboardButton]] = []
    for idx, movie in enumerate(results):
        title = str(movie.get("title") or "Unknown")
        year = movie.get("year")
        if year:
            label = f"🎬 {title} ({year})"
        else:
            label = f"🎬 {title}"
        if len(label) > 60:
            label = label[:59] + "…"
        rows.append([InlineKeyboardButton(label, callback_data=f"moviepick:{idx}")])
    rows.extend(nav_footer(back_data=back_data, include_home=True))
    return InlineKeyboardMarkup(rows)


def tv_followup_same_season_keyboard(sid: str) -> InlineKeyboardMarkup:
    """Yes/No choice for staying in the same season."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes", callback_data=f"tvpost:same_yes:{sid}"),
                InlineKeyboardButton("No", callback_data=f"tvpost:same_no:{sid}"),
            ],
            [InlineKeyboardButton("🏠 Home", callback_data="nav:home")],
        ]
    )


def candidate_nav_keyboard(
    *,
    pick_label: str,
    pick_callback: str,
    candidate_idx: int,
    total_candidates: int,
    nav_prefix: str,
    nav_footer_fn: Callable[..., list[list[InlineKeyboardButton]]] | None = None,
) -> InlineKeyboardMarkup:
    """Build a keyboard for cycling through search result candidates.

    Layout (top to bottom):
      1. Pick button row (single button)
      2. Nav row (only if total_candidates > 1): ◀ Prev / Next ▶
      3. 🏠 Home button
      4. Optional nav footer (if provided)
    """
    rows: list[list[InlineKeyboardButton]] = []

    # Pick button
    rows.append([InlineKeyboardButton(pick_label, callback_data=pick_callback)])

    # Nav row (only when multiple candidates)
    if total_candidates > 1:
        prev_idx = (candidate_idx - 1) % total_candidates
        next_idx = (candidate_idx + 1) % total_candidates
        rows.append(
            [
                InlineKeyboardButton(
                    f"◀ Prev ({prev_idx + 1}/{total_candidates})",
                    callback_data=f"{nav_prefix}:{prev_idx}",
                ),
                InlineKeyboardButton(
                    f"Next ({next_idx + 1}/{total_candidates}) ▶",
                    callback_data=f"{nav_prefix}:{next_idx}",
                ),
            ]
        )

    # Home button
    rows.append([InlineKeyboardButton("🏠 Home", callback_data="nav:home")])

    # Optional nav footer
    if nav_footer_fn is not None:
        rows.extend(nav_footer_fn(include_home=False))

    return InlineKeyboardMarkup(rows)


def media_picker_keyboard(sid: str, idx: int, *, back_data: str = "") -> InlineKeyboardMarkup:
    """Keyboard that asks the user to pick Movies or TV for a search result."""
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("🎬 Movies", callback_data=f"d:{sid}:{idx}:movies"),
            InlineKeyboardButton("📺 TV", callback_data=f"d:{sid}:{idx}:tv"),
        ]
    ]
    rows.extend(nav_footer(back_data=back_data))
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Tracked-list shared keyboard (My Shows / My Movies)
# ---------------------------------------------------------------------------


def tracked_list_page_bounds(items: list, page: int, per_page: int = 8) -> tuple[int, int, int, int]:
    """Return (page, total_pages, start, end) for a tracked list slice."""
    total_pages = max(1, math.ceil(max(1, len(items)) / per_page))
    page = max(0, min(int(page), total_pages - 1))
    start = page * per_page
    end = min(start + per_page, len(items))
    return page, total_pages, start, end


def tracked_list_keyboard(
    items: list[dict],
    page: int,
    *,
    per_page: int = 8,
    item_callback_fn: Callable[[dict], str],
    item_label_fn: Callable[[dict], str],
    filter_current: str = "all",
    filter_prefix: str = "sch",
    nav_prefix: str = "sch",
    add_callback: str = "",
    add_label: str = "",
    switch_callback: str = "",
    switch_label: str = "",
    back_data: str = "menu:schedule",
) -> InlineKeyboardMarkup:
    """Build the full keyboard for a tracked-list screen.

    Rows (top to bottom):
      1. Filter tabs: All / Active / Paused
      2. One button per visible item (tappable title)
      3. Pagination: Prev / Next (only when multiple pages exist)
      4. Add New button (when add_callback provided)
      5. Nav footer: Back + Home
    """
    page, total_pages, start, end = tracked_list_page_bounds(items, page, per_page)
    visible = items[start:end]

    rows: list[list[InlineKeyboardButton]] = []

    # --- filter row ---
    def _filter_btn(label: str, key: str) -> InlineKeyboardButton:
        marker = "✅ " if filter_current == key else ""
        return InlineKeyboardButton(f"{marker}{label}", callback_data=f"{filter_prefix}:f:{key}")

    rows.append(
        [
            _filter_btn("All", "all"),
            _filter_btn("Active", "act"),
            _filter_btn("Paused", "pau"),
        ]
    )

    # --- item rows ---
    for item in visible:
        rows.append([InlineKeyboardButton(item_label_fn(item), callback_data=item_callback_fn(item))])

    # --- pagination row ---
    if total_pages > 1:
        prev_btn = InlineKeyboardButton(
            "⬅️ Prev",
            callback_data=f"{nav_prefix}:pg:{page - 1}" if page > 0 else f"{nav_prefix}:pg:0",
        )
        next_btn = InlineKeyboardButton(
            "Next ➡️",
            callback_data=f"{nav_prefix}:pg:{page + 1}"
            if page < total_pages - 1
            else f"{nav_prefix}:pg:{total_pages - 1}",
        )
        if page == 0:
            rows.append([next_btn])
        elif page == total_pages - 1:
            rows.append([prev_btn])
        else:
            rows.append([prev_btn, next_btn])

    # --- add new button ---
    if add_callback and add_label:
        rows.append([InlineKeyboardButton(add_label, callback_data=add_callback)])

    # --- switch button (toggle between Shows / Movies) ---
    if switch_callback and switch_label:
        rows.append([InlineKeyboardButton(switch_label, callback_data=switch_callback)])

    # --- nav footer ---
    rows.extend(nav_footer(back_data=back_data, include_home=True))

    return InlineKeyboardMarkup(rows)
