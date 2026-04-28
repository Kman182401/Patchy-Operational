# Community 19 — Health Checks & VPN

**44 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `test_health.py` | `telegram-qbt/tests/test_health.py:L1` | 14 |
| `_FakeCfg` | `telegram-qbt/tests/test_health.py:L21` | 12 |
| `speed_report()` | `telegram-qbt/patchy_bot/handlers/commands.py:L211` | 11 |
| `check_vpn()` | `telegram-qbt/patchy_bot/health.py:L49` | 9 |
| `check_qbt_connection()` | `telegram-qbt/patchy_bot/health.py:L118` | 8 |
| `check_disk_space()` | `telegram-qbt/patchy_bot/health.py:L146` | 7 |
| `run_preflight()` | `telegram-qbt/patchy_bot/health.py:L183` | 6 |
| `TestCheckVpn` | `telegram-qbt/tests/test_health.py:L40` | 6 |
| `qbt_transport_status()` | `telegram-qbt/patchy_bot/handlers/_shared.py:L81` | 5 |
| `.get_transfer_info()` | `telegram-qbt/patchy_bot/clients/qbittorrent.py:L215` | 5 |
| `TestCheckQbtConnection` | `telegram-qbt/tests/test_health.py:L124` | 5 |
| `.get_preferences()` | `telegram-qbt/patchy_bot/clients/qbittorrent.py:L219` | 4 |
| `_make_speed_ctx()` | `telegram-qbt/tests/test_handlers.py:L632` | 4 |
| `test_speed_report_returns_string()` | `telegram-qbt/tests/test_handlers.py:L661` | 4 |
| `test_speed_report_contains_speed_values()` | `telegram-qbt/tests/test_handlers.py:L671` | 4 |

## Connected Communities

- [[Community 0 — Core Types & Clients]] (18 edges)
- [[Community 1 — BotApp & Command Flow]] (4 edges)
- [[Community 5 — Search & Filters]] (3 edges)
- [[Community 8 — Callback Dispatch]] (1 edges)
- [[Community 4 — Parsing & Utilities]] (1 edges)
- [[Community 7 — Runners & Progress]] (1 edges)
- [[Community 15 — Health & LLM Client]] (1 edges)

## All Nodes (44)

- `test_health.py` — `telegram-qbt/tests/test_health.py` (14)
- `_FakeCfg` — `telegram-qbt/tests/test_health.py` (12)
- `speed_report()` — `telegram-qbt/patchy_bot/handlers/commands.py` (11)
- `check_vpn()` — `telegram-qbt/patchy_bot/health.py` (9)
- `check_qbt_connection()` — `telegram-qbt/patchy_bot/health.py` (8)
- `check_disk_space()` — `telegram-qbt/patchy_bot/health.py` (7)
- `run_preflight()` — `telegram-qbt/patchy_bot/health.py` (6)
- `TestCheckVpn` — `telegram-qbt/tests/test_health.py` (6)
- `qbt_transport_status()` — `telegram-qbt/patchy_bot/handlers/_shared.py` (5)
- `.get_transfer_info()` — `telegram-qbt/patchy_bot/clients/qbittorrent.py` (5)
- `TestCheckQbtConnection` — `telegram-qbt/tests/test_health.py` (5)
- `.get_preferences()` — `telegram-qbt/patchy_bot/clients/qbittorrent.py` (4)
- `_make_speed_ctx()` — `telegram-qbt/tests/test_handlers.py` (4)
- `test_speed_report_returns_string()` — `telegram-qbt/tests/test_handlers.py` (4)
- `test_speed_report_contains_speed_values()` — `telegram-qbt/tests/test_handlers.py` (4)
- `.test_disabled()` — `telegram-qbt/tests/test_health.py` (3)
- `test_interface_missing()` — `telegram-qbt/tests/test_health.py` (3)
- `.test_interface_down()` — `telegram-qbt/tests/test_health.py` (3)
- `.test_no_ip()` — `telegram-qbt/tests/test_health.py` (3)
- `.test_dns_failure()` — `telegram-qbt/tests/test_health.py` (3)
- `.test_all_ok()` — `telegram-qbt/tests/test_health.py` (3)
- `test_all_pass()` — `telegram-qbt/tests/test_health.py` (3)
- `test_one_blocker()` — `telegram-qbt/tests/test_health.py` (3)
- `test_warnings_only()` — `telegram-qbt/tests/test_health.py` (3)
- `._qbt_transport_status()` — `telegram-qbt/patchy_bot/bot.py` (2)
- `._speed_report()` — `telegram-qbt/patchy_bot/bot.py` (2)
- `Build the /speed dashboard text.      Args:         ctx: Handler context with qb` — `telegram-qbt/patchy_bot/handlers/commands.py` (2)
- `Check qBittorrent connection status and bound network interface.` — `telegram-qbt/patchy_bot/handlers/_shared.py` (2)
- `.test_connected()` — `telegram-qbt/tests/test_health.py` (2)
- `.test_firewalled()` — `telegram-qbt/tests/test_health.py` (2)
- `.test_disconnected()` — `telegram-qbt/tests/test_health.py` (2)
- `.test_unreachable()` — `telegram-qbt/tests/test_health.py` (2)
- `test_plenty_of_space()` — `telegram-qbt/tests/test_health.py` (2)
- `test_low_space_warning()` — `telegram-qbt/tests/test_health.py` (2)
- `test_critical_block()` — `telegram-qbt/tests/test_health.py` (2)
- `test_oserror_graceful()` — `telegram-qbt/tests/test_health.py` (2)
- `Build a minimal ctx for speed_report.` — `telegram-qbt/tests/test_handlers.py` (1)
- `speed_report returns a non-empty string.` — `telegram-qbt/tests/test_handlers.py` (1)
- `speed_report includes download and upload speed labels.` — `telegram-qbt/tests/test_handlers.py` (1)
- `.__init__()` — `telegram-qbt/tests/test_health.py` (1)
- `TestCheckDiskSpace` — `telegram-qbt/tests/test_health.py` (1)
- `TestRunPreflight` — `telegram-qbt/tests/test_health.py` (1)
- `Tests for patchy_bot.health — VPN, qBT, and disk space checks.` — `telegram-qbt/tests/test_health.py` (1)
- `Minimal Config stand-in.` — `telegram-qbt/tests/test_health.py` (1)
