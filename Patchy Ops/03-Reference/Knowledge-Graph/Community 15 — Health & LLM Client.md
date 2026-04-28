# Community 15 — Health & LLM Client

**55 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `.ready()` | `telegram-qbt/patchy_bot/clients/llm.py:L21` | 20 |
| `health_report()` | `telegram-qbt/patchy_bot/handlers/commands.py:L85` | 18 |
| `_shared.py` | `telegram-qbt/patchy_bot/handlers/_shared.py:L1` | 16 |
| `test_llm_client.py` | `telegram-qbt/tests/test_llm_client.py:L1` | 15 |
| `_make_client()` | `telegram-qbt/tests/test_llm_client.py:L17` | 10 |
| `.chat()` | `telegram-qbt/patchy_bot/clients/llm.py:L45` | 9 |
| `targets()` | `telegram-qbt/patchy_bot/handlers/_shared.py:L30` | 6 |
| `ensure_media_categories()` | `telegram-qbt/patchy_bot/handlers/_shared.py:L68` | 6 |
| `_extract_content()` | `telegram-qbt/patchy_bot/clients/llm.py:L25` | 6 |
| `_fake_response()` | `telegram-qbt/tests/test_llm_client.py:L21` | 6 |
| `storage_status()` | `telegram-qbt/patchy_bot/handlers/_shared.py:L56` | 5 |
| `test_chat_unsupported_model_not_retried()` | `telegram-qbt/tests/test_llm_client.py:L114` | 5 |
| `_make_health_ctx()` | `telegram-qbt/tests/test_handlers.py:L534` | 5 |
| `TestReady` | `telegram-qbt/tests/test_plex_client.py:L116` | 5 |
| `._ensure_media_categories()` | `telegram-qbt/patchy_bot/bot.py:L413` | 4 |

## Connected Communities

- [[Community 0 — Core Types & Clients]] (26 edges)
- [[Community 1 — BotApp & Command Flow]] (17 edges)
- [[Community 2 — Download Pipeline]] (7 edges)
- [[Community 5 — Search & Filters]] (5 edges)
- [[Community 6 — Movie Scheduling]] (4 edges)
- [[Community 4 — Parsing & Utilities]] (4 edges)
- [[Community 19 — Health Checks & VPN]] (1 edges)
- [[Community 23 — Media Choice Normalize]] (1 edges)
- [[Community 20 — Plex Client Tests]] (1 edges)

## All Nodes (55)

- `.ready()` — `telegram-qbt/patchy_bot/clients/llm.py` (20)
- `health_report()` — `telegram-qbt/patchy_bot/handlers/commands.py` (18)
- `_shared.py` — `telegram-qbt/patchy_bot/handlers/_shared.py` (16)
- `test_llm_client.py` — `telegram-qbt/tests/test_llm_client.py` (15)
- `_make_client()` — `telegram-qbt/tests/test_llm_client.py` (10)
- `.chat()` — `telegram-qbt/patchy_bot/clients/llm.py` (9)
- `targets()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (6)
- `ensure_media_categories()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (6)
- `_extract_content()` — `telegram-qbt/patchy_bot/clients/llm.py` (6)
- `_fake_response()` — `telegram-qbt/tests/test_llm_client.py` (6)
- `storage_status()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (5)
- `test_chat_unsupported_model_not_retried()` — `telegram-qbt/tests/test_llm_client.py` (5)
- `_make_health_ctx()` — `telegram-qbt/tests/test_handlers.py` (5)
- `TestReady` — `telegram-qbt/tests/test_plex_client.py` (5)
- `._ensure_media_categories()` — `telegram-qbt/patchy_bot/bot.py` (4)
- `norm_path()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (4)
- `vpn_ready_for_download()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (4)
- `test_chat_returns_content_and_model_on_success()` — `telegram-qbt/tests/test_llm_client.py` (4)
- `test_chat_falls_back_on_404()` — `telegram-qbt/tests/test_llm_client.py` (4)
- `test_chat_empty_response_triggers_fallback()` — `telegram-qbt/tests/test_llm_client.py` (4)
- `test_chat_raises_when_all_models_fail()` — `telegram-qbt/tests/test_llm_client.py` (4)
- `test_health_report_returns_html_string()` — `telegram-qbt/tests/test_handlers.py` (4)
- `test_health_report_checks_storage()` — `telegram-qbt/tests/test_handlers.py` (4)
- `test_health_report_overall_ok_when_healthy()` — `telegram-qbt/tests/test_handlers.py` (4)
- `._targets()` — `telegram-qbt/patchy_bot/bot.py` (3)
- `.list_search_plugins()` — `telegram-qbt/patchy_bot/clients/qbittorrent.py` (3)
- `test_llm_ready_returns_true_when_configured()` — `telegram-qbt/tests/test_llm_client.py` (3)
- `test_llm_ready_returns_false_when_missing_base_url()` — `telegram-qbt/tests/test_llm_client.py` (3)
- `test_llm_ready_returns_false_when_missing_api_key()` — `telegram-qbt/tests/test_llm_client.py` (3)
- `.test_plex_ready_true()` — `telegram-qbt/tests/test_plex_client.py` (3)
- `.test_plex_ready_false_no_url()` — `telegram-qbt/tests/test_plex_client.py` (3)
- `.test_plex_ready_false_no_token()` — `telegram-qbt/tests/test_plex_client.py` (3)
- `.count_due_schedule_tracks()` — `telegram-qbt/patchy_bot/store.py` (2)
- `.db_diagnostics()` — `telegram-qbt/patchy_bot/store.py` (2)
- `_norm_path()` — `telegram-qbt/patchy_bot/bot.py` (2)
- `._health_report()` — `telegram-qbt/patchy_bot/bot.py` (2)
- `Build the /health status report.      Args:         ctx: Handler context with al` — `telegram-qbt/patchy_bot/handlers/commands.py` (2)
- `auto_delete_after()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Shared utility functions used by multiple handler modules.  Canonical implementa` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Delete a message after *delay* seconds (best-effort).` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Return the movies/tv target dict from config.` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Normalize a filesystem path for comparison.` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Check NVMe mount + library paths.` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Ensure qBittorrent categories exist for movies + tv paths.` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `Check that the VPN interface is up and has an IP before allowing downloads.` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `test_extract_content_string()` — `telegram-qbt/tests/test_llm_client.py` (2)
- `test_extract_content_array()` — `telegram-qbt/tests/test_llm_client.py` (2)
- `test_extract_content_empty_choices()` — `telegram-qbt/tests/test_llm_client.py` (2)
- `test_extract_content_no_choices_key()` — `telegram-qbt/tests/test_llm_client.py` (2)
- `Unit tests for PatchyLLMClient (patchy_bot/clients/llm.py).` — `telegram-qbt/tests/test_llm_client.py` (2)
- `test_targets_only_include_movies_and_tv()` — `telegram-qbt/tests/test_parsing.py` (2)
- `Build a minimal ctx that health_report can consume.` — `telegram-qbt/tests/test_handlers.py` (1)
- `health_report output contains HTML bold tags.` — `telegram-qbt/tests/test_handlers.py` (1)
- `health_report mentions storage/routing status.` — `telegram-qbt/tests/test_handlers.py` (1)
- `health_report returns ok=True when no hard failures exist.` — `telegram-qbt/tests/test_handlers.py` (1)
