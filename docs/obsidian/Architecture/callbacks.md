# Callback Routing

> Generated from `patchy_bot/bot.py` on 2026-04-11. Routed via `CallbackDispatcher` in `dispatch.py`.

## Dispatch Mechanism

The `CallbackDispatcher` class supports two registration modes:

1. **Exact match** — O(1) dict lookup for literal callback data strings
2. **Prefix match** — tried longest-first so `"sch:confirm:all"` beats `"sch:"`

Exact matches are always checked before prefix matches.

## Registrations

### Exact Matches (2)

| Callback Data | Handler Method | Purpose |
|---------------|---------------|---------|
| `nav:home` | `_on_cb_nav_home` | Navigate to command center home |
| `dl:manage` | `_on_cb_dl_manage` | Open download management view |

### Prefix Matches (12, longest-first)

| Prefix | Handler Method | Domain | Owner Agent |
|--------|---------------|--------|-------------|
| `moviepost:` | `_on_cb_moviepost` | Post-download movie actions | search-download-agent |
| `stop:all:` | `_on_cb_stop` | Stop all downloads | search-download-agent |
| `mwblock:` | `_on_cb_mwblock` | Malware block decision | search-download-agent |
| `tvpost:` | `_on_cb_tvpost` | Post-download TV actions | search-download-agent |
| `msch:` | `_on_cb_movie_schedule` | Movie schedule tracking | movie-tracking-agent |
| `menu:` | `_on_cb_menu` | Menu navigation | ui-agent |
| `flow:` | `_on_cb_flow` | Flow state transitions | ui-agent |
| `stop:` | `_on_cb_stop` | Stop individual download | search-download-agent |
| `sch:` | `_on_cb_schedule` | TV schedule tracking | schedule-agent |
| `rm:` | `_on_cb_remove` | Media removal | remove-agent |
| `a:` | `_on_cb_add` | Add torrent to download | search-download-agent |
| `d:` | `_on_cb_download` | Download flow actions | search-download-agent |
| `p:` | `_on_cb_page` | Pagination navigation | ui-agent |

## Callback Data Format

All callback data uses colon-delimited format: `prefix:param1:param2`

Examples:
- `sch:track:12345` — track a show with ID 12345
- `rm:confirm:job-uuid` — confirm a removal job
- `a:searchid:3` — add result #3 from a search
- `msch:search:42` — movie schedule search for TMDB ID 42
- `p:searchid:2` — navigate to page 2 of search results
