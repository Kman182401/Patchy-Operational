# Task ID: 4

**Title:** Extract the search handler

**Status:** pending

**Dependencies:** 2, 3

**Priority:** high

**Description:** Move search-related methods into patchy_bot/handlers/search.py: _build_search_parser, _apply_filters, _sort_rows, _parse_tv_filter, _build_tv_query, _strip_patchy_name, _extract_search_intent, _render_page, _run_search. The handler registers itself with the dispatcher for a:, d:, and p: callback prefixes. Update bot.py on_text movie/tv flow branches to delegate to the search handler.

**Details:**

The search handler manages the full lifecycle: query parsing with argparse, torrent search via QBClient, result filtering (quality tier, size, seeds), pagination, and the add-to-library flow. It handles 3 callback prefixes: a: (show library picker), d: (download with choice), p: (page navigation). The on_text branches for mode='movie'/stage='await_title' and mode='tv'/stage='await_title' delegate to this handler's run_search method. Lines moved: approximately 2791-3257 from bot.py (~465 lines).

**Test Strategy:**

Add at least 5 new unit tests for _apply_filters and _sort_rows with known input/output pairs. Existing episode-code tests must pass. Deploy and test: movie search flow, TV search flow, page navigation, add-to-library flow.
