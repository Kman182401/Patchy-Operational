# Community 13 — Completion Security

**70 nodes** in this cluster.

## Hub Nodes

| Node | File | Connections |
|------|------|-------------|
| `_apply_completion_security_gate()` | `telegram-qbt/patchy_bot/handlers/download.py:L464` | 27 |
| `test_completion_security_gate.py` | `telegram-qbt/tests/test_completion_security_gate.py:L1` | 26 |
| `_run_clamav_scan()` | `telegram-qbt/patchy_bot/handlers/download.py:L418` | 16 |
| `_validate_safe_path()` | `telegram-qbt/patchy_bot/handlers/download.py:L210` | 11 |
| `TestRunClamavScan` | `telegram-qbt/tests/test_completion_security_gate.py:L29` | 11 |
| `TestValidateSafePath` | `telegram-qbt/tests/test_delete_safety.py:L482` | 9 |
| `._fake_run()` | `telegram-qbt/tests/test_completion_security_gate.py:L154` | 9 |
| `_clamd_available()` | `telegram-qbt/patchy_bot/handlers/download.py:L394` | 8 |
| `TestClamdAvailable` | `telegram-qbt/tests/test_completion_security_gate.py:L108` | 7 |
| `CompletionSecurityResult` | `telegram-qbt/patchy_bot/handlers/download.py:L129` | 4 |
| `TestClamdVsClamscanFallback` | `telegram-qbt/tests/test_completion_security_gate.py:L153` | 4 |
| `Return True iff *target* resolves inside one of *allowed_roots*.      Used as a` | `telegram-qbt/patchy_bot/handlers/download.py:L211` | 3 |
| `.test_nonexistent_path_but_parent_inside_root()` | `telegram-qbt/tests/test_delete_safety.py:L524` | 3 |
| `.test_clean_returns_clean()` | `telegram-qbt/tests/test_completion_security_gate.py:L37` | 3 |
| `.test_infected_returns_infected()` | `telegram-qbt/tests/test_completion_security_gate.py:L44` | 3 |

## Connected Communities

- [[Community 2 — Download Pipeline]] (12 edges)
- [[Community 3 — Malware Scanning]] (2 edges)
- [[Community 0 — Core Types & Clients]] (2 edges)
- [[Community 7 — Runners & Progress]] (1 edges)
- [[Community 1 — BotApp & Command Flow]] (1 edges)
- [[Community 9 — Store Internals]] (1 edges)
- [[Community 18 — Delete Safety]] (1 edges)

## All Nodes (70)

- `_apply_completion_security_gate()` — `telegram-qbt/patchy_bot/handlers/download.py` (27)
- `test_completion_security_gate.py` — `telegram-qbt/tests/test_completion_security_gate.py` (26)
- `_run_clamav_scan()` — `telegram-qbt/patchy_bot/handlers/download.py` (16)
- `_validate_safe_path()` — `telegram-qbt/patchy_bot/handlers/download.py` (11)
- `TestRunClamavScan` — `telegram-qbt/tests/test_completion_security_gate.py` (11)
- `TestValidateSafePath` — `telegram-qbt/tests/test_delete_safety.py` (9)
- `._fake_run()` — `telegram-qbt/tests/test_completion_security_gate.py` (9)
- `_clamd_available()` — `telegram-qbt/patchy_bot/handlers/download.py` (8)
- `TestClamdAvailable` — `telegram-qbt/tests/test_completion_security_gate.py` (7)
- `CompletionSecurityResult` — `telegram-qbt/patchy_bot/handlers/download.py` (4)
- `TestClamdVsClamscanFallback` — `telegram-qbt/tests/test_completion_security_gate.py` (4)
- `Return True iff *target* resolves inside one of *allowed_roots*.      Used as a` — `telegram-qbt/patchy_bot/handlers/download.py` (3)
- `.test_nonexistent_path_but_parent_inside_root()` — `telegram-qbt/tests/test_delete_safety.py` (3)
- `.test_clean_returns_clean()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_infected_returns_infected()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_infected_no_stdout_fallback()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_error_returns_error()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_no_db_returns_unavailable()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_cant_open_returns_unavailable()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_cache_ttl()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_daemon_available_uses_clamdscan()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_daemon_unavailable_uses_clamscan()` — `telegram-qbt/tests/test_completion_security_gate.py` (3)
- `.test_path_within_allowed_root()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_path_outside_allowed_root()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_traversal_attempt()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_symlink_escape()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_multiple_allowed_roots()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_empty_root_skipped()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_all_empty_roots_reject()` — `telegram-qbt/tests/test_delete_safety.py` (2)
- `.test_timeout_returns_error()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `.test_exception_returns_error()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `.test_empty_path_returns_error()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `.test_clamdscan_not_installed()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `.test_daemon_responsive()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `.test_daemon_down()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `.test_ping_timeout()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `gate_ctx()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_clean_allows()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_unavailable_allows()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_error_pauses_and_blocks()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_error_logs_health_event()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_infected_deletes_torrent()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_infected_rmtree_fallback()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_infected_validates_path()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_infected_logs_malware_block()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_infected_logs_health_event()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_infected_notifies_users()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_empty_path_blocks()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_deletion_error_doesnt_crash()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_log_failure_doesnt_crash()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_clean_scan_zero_byte_file()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_clean_scan_text_file()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_eicar_detected()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `TestLogCleanScansFlag` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_clean_scan_logged_when_flag_on()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_clean_scan_not_logged_when_flag_off()` — `telegram-qbt/tests/test_completion_security_gate.py` (2)
- `test_breaker_trips_after_threshold()` — `telegram-qbt/tests/test_download_pipeline.py` (2)
- `test_breaker_resets_on_clean()` — `telegram-qbt/tests/test_download_pipeline.py` (2)
- `test_breaker_resets_on_infected()` — `telegram-qbt/tests/test_download_pipeline.py` (2)
- `test_breaker_resets_on_unavailable()` — `telegram-qbt/tests/test_download_pipeline.py` (2)
- `test_breaker_does_not_trip_on_two_errors()` — `telegram-qbt/tests/test_download_pipeline.py` (2)
- `pathlib.Path.resolve() does not require existence — nonexistent paths         ca` — `telegram-qbt/tests/test_delete_safety.py` (1)
- `._fake_run()` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `.setup_method()` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `TestCompletionSecurityGate` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `TestRealClamav` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `Tests for the completion-security gate: ClamAV scanning and the ``_apply_complet` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `A second call within the TTL window returns cached result.` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `HandlerContext with the bits _apply_completion_security_gate touches.      Adds:` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
- `The log_clean_scans config flag gates health-event logging on clean scans.` — `telegram-qbt/tests/test_completion_security_gate.py` (1)
