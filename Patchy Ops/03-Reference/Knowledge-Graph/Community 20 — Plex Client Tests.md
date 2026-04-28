# Community 20 — Plex Client Tests

**39 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `FakeResponse` | `telegram-qbt/tests/test_plex_client.py:L14` | 16 |
| `_make_client()` | `telegram-qbt/tests/test_plex_client.py:L22` | 15 |
| `.episode_inventory()` | `telegram-qbt/patchy_bot/clients/plex.py:L95` | 12 |
| `_path_matches_remove_target()` | `telegram-qbt/patchy_bot/clients/plex.py:L55` | 10 |
| `test_plex_client.py` | `telegram-qbt/tests/test_plex_client.py:L1` | 10 |
| `._tv_section()` | `telegram-qbt/patchy_bot/clients/plex.py:L75` | 7 |
| `TestPathMatchesRemoveTarget` | `telegram-qbt/tests/test_plex_client.py:L148` | 7 |
| `TestTvSection` | `telegram-qbt/tests/test_plex_client.py:L187` | 6 |
| `TestEpisodeInventory` | `telegram-qbt/tests/test_plex_client.py:L215` | 6 |
| `TestVerifyRemoveIdentityAbsent` | `telegram-qbt/tests/test_plex_client.py:L272` | 5 |
| `.test_verify_rating_keys_metadata_gone()` | `telegram-qbt/tests/test_plex_client.py:L273` | 5 |
| `.test_verify_rating_keys_metadata_exists()` | `telegram-qbt/tests/test_plex_client.py:L291` | 5 |
| `.test_verify_path_fallback_no_matching_parts()` | `telegram-qbt/tests/test_plex_client.py:L308` | 5 |
| `_norm_media_path()` | `telegram-qbt/patchy_bot/clients/plex.py:L51` | 4 |
| `TestNormMediaPath` | `telegram-qbt/tests/test_plex_client.py:L135` | 4 |

## Connected Communities

- [[Community 0 — Core Types & Clients]] (28 edges)
- [[Community 4 — Parsing & Utilities]] (2 edges)
- [[Community 1 — BotApp & Command Flow]] (2 edges)
- [[Community 6 — Movie Scheduling]] (1 edges)
- [[Community 15 — Health & LLM Client]] (1 edges)

## All Nodes (39)

- `FakeResponse` — `telegram-qbt/tests/test_plex_client.py` (16)
- `_make_client()` — `telegram-qbt/tests/test_plex_client.py` (15)
- `.episode_inventory()` — `telegram-qbt/patchy_bot/clients/plex.py` (12)
- `_path_matches_remove_target()` — `telegram-qbt/patchy_bot/clients/plex.py` (10)
- `test_plex_client.py` — `telegram-qbt/tests/test_plex_client.py` (10)
- `._tv_section()` — `telegram-qbt/patchy_bot/clients/plex.py` (7)
- `TestPathMatchesRemoveTarget` — `telegram-qbt/tests/test_plex_client.py` (7)
- `TestTvSection` — `telegram-qbt/tests/test_plex_client.py` (6)
- `TestEpisodeInventory` — `telegram-qbt/tests/test_plex_client.py` (6)
- `TestVerifyRemoveIdentityAbsent` — `telegram-qbt/tests/test_plex_client.py` (5)
- `.test_verify_rating_keys_metadata_gone()` — `telegram-qbt/tests/test_plex_client.py` (5)
- `.test_verify_rating_keys_metadata_exists()` — `telegram-qbt/tests/test_plex_client.py` (5)
- `.test_verify_path_fallback_no_matching_parts()` — `telegram-qbt/tests/test_plex_client.py` (5)
- `_norm_media_path()` — `telegram-qbt/patchy_bot/clients/plex.py` (4)
- `TestNormMediaPath` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_tv_section_matches_by_path()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_tv_section_falls_back_to_first_show()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_tv_section_returns_none_no_show_sections()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_tv_section_caches_result()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_episode_inventory_returns_codes()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_episode_inventory_show_not_found()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_episode_inventory_year_boosts_selection()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_episode_inventory_no_tv_section_raises()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `TestRequestErrors` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_get_xml_raises_on_bad_xml()` — `telegram-qbt/tests/test_plex_client.py` (4)
- `.test_norm_media_path_strips_and_normalizes()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.test_norm_media_path_empty()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.test_path_matches_episode_exact_match()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.test_path_matches_episode_no_prefix()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.test_path_matches_directory_prefix()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.test_path_matches_directory_exact()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.test_path_matches_empty_returns_false()` — `telegram-qbt/tests/test_plex_client.py` (2)
- `Tests for patchy_bot.clients.plex.PlexInventoryClient.` — `telegram-qbt/tests/test_plex_client.py` (2)
- `Minimal stand-in for requests.Response.` — `telegram-qbt/tests/test_plex_client.py` (2)
- `Return a PlexInventoryClient whose HTTP layer is fully faked.` — `telegram-qbt/tests/test_plex_client.py` (2)
- `When all rating_keys 404, the item is confirmed absent.` — `telegram-qbt/tests/test_plex_client.py` (2)
- `When metadata still returns 200, item is NOT absent.` — `telegram-qbt/tests/test_plex_client.py` (2)
- `path_fallback mode with no section_key scans all sections -- none match.` — `telegram-qbt/tests/test_plex_client.py` (2)
- `.__init__()` — `telegram-qbt/tests/test_plex_client.py` (1)
