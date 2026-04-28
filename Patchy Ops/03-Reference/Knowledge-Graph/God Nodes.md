# God Nodes

The most connected nodes in the Patchy Bot knowledge graph — these are the core abstractions everything flows through.

| Rank | Node | File | Edges | Community |
|------|------|------|-------|-----------|
| 1 | `BotApp` | `telegram-qbt/patchy_bot/bot.py:L75` | 367 | [[Community 1 — BotApp & Command Flow]] |
| 2 | `HandlerContext` | `telegram-qbt/patchy_bot/types.py:L21` | 330 | [[Community 0 — Core Types & Clients]] |
| 3 | `Store` | `telegram-qbt/patchy_bot/store.py:L23` | 243 | [[Community 0 — Core Types & Clients]] |
| 4 | `test_parsing.py` | `telegram-qbt/tests/test_parsing.py:L1` | 175 | [[Community 4 — Parsing & Utilities]] |
| 5 | `ScanResult` | `telegram-qbt/patchy_bot/malware.py:L117` | 172 | [[Community 3 — Malware Scanning]] |
| 6 | `TVMetadataClient` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L46` | 150 | [[Community 0 — Core Types & Clients]] |
| 7 | `MovieReleaseStatus` | `telegram-qbt/patchy_bot/clients/tv_metadata.py:L25` | 130 | [[Community 0 — Core Types & Clients]] |
| 8 | `CallbackDispatcher` | `telegram-qbt/patchy_bot/dispatch.py:L14` | 124 | [[Community 8 — Callback Dispatch]] |
| 9 | `DoAddResult` | `telegram-qbt/patchy_bot/handlers/download.py:L375` | 124 | [[Community 2 — Download Pipeline]] |
| 10 | `Config` | `telegram-qbt/patchy_bot/config.py:L13` | 106 | [[Community 0 — Core Types & Clients]] |
| 11 | `now_ts()` | `telegram-qbt/patchy_bot/utils.py:L32` | 103 | [[Community 6 — Movie Scheduling]] |
| 12 | `PlexInventoryClient` | `telegram-qbt/patchy_bot/clients/plex.py:L18` | 101 | [[Community 0 — Core Types & Clients]] |
| 13 | `test_handlers.py` | `telegram-qbt/tests/test_handlers.py:L1` | 89 | [[Community 5 — Search & Filters]] |
| 14 | `QBClient` | `telegram-qbt/patchy_bot/clients/qbittorrent.py:L18` | 87 | [[Community 0 — Core Types & Clients]] |
| 15 | `test_download_pipeline.py` | `telegram-qbt/tests/test_download_pipeline.py:L1` | 87 | [[Community 2 — Download Pipeline]] |
| 16 | `_h()` | `telegram-qbt/patchy_bot/utils.py:L27` | 85 | [[Community 1 — BotApp & Command Flow]] |
| 17 | `RateLimiter` | `telegram-qbt/patchy_bot/rate_limiter.py:L10` | 85 | [[Community 0 — Core Types & Clients]] |
| 18 | `scan_download()` | `telegram-qbt/patchy_bot/malware.py:L1150` | 85 | [[Community 3 — Malware Scanning]] |
| 19 | `_gb()` | `telegram-qbt/tests/test_malware.py:L28` | 81 | [[Community 3 — Malware Scanning]] |
| 20 | `scan_search_result()` | `telegram-qbt/patchy_bot/malware.py:L1112` | 76 | [[Community 3 — Malware Scanning]] |

## What Makes a God Node?

God nodes have the highest edge count — they're referenced, imported, or called by the most other nodes. They represent architectural chokepoints where changes ripple widely.

