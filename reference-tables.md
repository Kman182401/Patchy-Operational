# Patchy Bot Quick Reference

Last updated: April 2026. For complete details, read the actual source files. This is a summary for quick lookup.

## Configuration (45 env vars via Config.from_env())

### Core
| Env Var | Type | Default | Notes |
|---------|------|---------|-------|
| TELEGRAM_BOT_TOKEN | str | required | Bot API token |
| ALLOWED_TELEGRAM_USER_IDS | set[int] | {} | Comma-separated |
| ALLOW_GROUP_CHATS | bool | False | |
| BOT_ACCESS_PASSWORD | str | "" | Empty = no password gate |
| ACCESS_SESSION_TTL_SECONDS | int | 0 | 0 = indefinite |

### VPN
| Env Var | Type | Default |
|---------|------|---------|
| REQUIRE_VPN_FOR_DOWNLOADS | bool | True |
| VPN_SERVICE_NAME | str | surfshark-vpn.service |
| VPN_INTERFACE_NAME | str | tun0 |

### qBittorrent
| Env Var | Type | Default |
|---------|------|---------|
| QBT_BASE_URL | str | http://127.0.0.1:8080 |
| QBT_USERNAME / QBT_PASSWORD | str? | None |

### Plex
| Env Var | Type | Default |
|---------|------|---------|
| PLEX_BASE_URL | str? | None |
| PLEX_TOKEN | str? | None |

### Database & Storage
| Env Var | Type | Default |
|---------|------|---------|
| DB_PATH | str | ./state.sqlite3 |
| BACKUP_DIR | str? | None |

### Search Tuning
| Env Var | Default | Notes |
|---------|---------|-------|
| SEARCH_TIMEOUT_SECONDS | 45 | min 10 |
| POLL_INTERVAL_SECONDS | 0.6 | min 0.4 |
| SEARCH_EARLY_EXIT_MIN_RESULTS | 20 | min 0 |
| SEARCH_EARLY_EXIT_IDLE_SECONDS | 2.5 | min 1.0 |
| SEARCH_EARLY_EXIT_MAX_WAIT_SECONDS | 12.0 | min 2.0 |

### Result Defaults
| Env Var | Default | Notes |
|---------|---------|-------|
| RESULT_PAGE_SIZE | 5 | min 3 |
| DEFAULT_RESULT_LIMIT | 10 | 1-50 |
| DEFAULT_SORT | quality | lowercased |
| DEFAULT_ORDER | desc | |
| DEFAULT_MIN_QUALITY | 1080 | 0/480/720/1080/2160 |
| DEFAULT_MIN_SEEDS | 5 | min 0 |

### Categories & Paths
| Env Var | Default |
|---------|---------|
| MOVIES_CATEGORY / TV_CATEGORY / SPAM_CATEGORY | Movies / TV / Spam |
| MOVIES_PATH | /mnt/nvme/Movies |
| TV_PATH | /mnt/nvme/TV |
| SPAM_PATH | ~/Downloads/Spam |
| NVME_MOUNT_PATH | /mnt/nvme |
| REQUIRE_NVME_MOUNT | True |

### LLM Chat
| Env Var | Default |
|---------|---------|
| PATCHY_CHAT_ENABLED | True |
| PATCHY_CHAT_MODEL | gpt-5-chat-latest |
| PATCHY_CHAT_FALLBACK_MODEL | gpt-4.1-mini |
| PATCHY_CHAT_TIMEOUT_SECONDS | 35 |
| PATCHY_CHAT_MAX_TOKENS | 500 |
| PATCHY_CHAT_TEMPERATURE | 0.2 |

### Download Progress
| Env Var | Default |
|---------|---------|
| PROGRESS_REFRESH_SECONDS | 1.0 |
| PROGRESS_TRACK_TIMEOUT_SECONDS | 1800 |

### Path Safety
Dangerous roots (media paths cannot resolve to these): /, /bin, /boot, /dev, /etc, /home, /lib, /lib64, /opt, /proc, /root, /run, /sbin, /srv, /sys, /tmp, /usr, /var

## Key Database Tables (SQLite, WAL mode, busy_timeout=5000)

For full schemas with all columns, read store.py directly. Below are the tables and their purpose.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| searches | Torrent search metadata | search_id (PK), user_id, query, options_json |
| results | Individual torrent results | (search_id, idx) PK, name, size, seeds, quality_score |
| user_defaults | Per-user search prefs | user_id PK, default_min_seeds, default_sort |
| user_auth | Session unlock tracking | user_id PK, unlocked_until |
| auth_attempts | Brute-force protection | user_id PK, fail_count, locked_until |
| schedule_tracks | TV episode tracking (core) | track_id PK, show_name, tvmaze_id, pending_json, auto_state_json |
| schedule_runner_status | Runner health (singleton) | status_id=1, last_error_text, metadata_source_health_json |
| schedule_show_cache | TVMaze/TMDB cache (8h TTL) | tvmaze_id PK, bundle_json, expires_at |
| remove_jobs | Deletion pipeline | job_id PK, target_path, status, retry_count |
| notified_completions | Download dedup | torrent_hash PK |
| command_center_ui | Persistent UI message | user_id PK, chat_id, message_id |

## Key Utility Functions (utils.py)

All pure functions with no side effects (except build_requests_session).

| Category | Key Functions |
|----------|--------------|
| Text | `_h(text)` — HTML-escape, `human_size(bytes)`, `normalize_title(value)` |
| Time | `now_ts()`, `_relative_time(ts)`, `format_local_ts(ts)`, `parse_release_ts(airstamp, airdate)` |
| Parsing | `parse_bool(value)`, `parse_size_to_bytes(value)`, `quality_tier(name)` |
| Episodes | `episode_code(s, e)`, `extract_episode_codes(text)`, `extract_season_number(text)` |
| Remove | `format_remove_season_label(name)`, `is_remove_media_file(name)` |
| HTTP | `build_requests_session(user_agent, retries=3)` — retry on 429/5xx |

## Key Constants
- `_PM = "HTML"` — Telegram parse mode
- `_ACTIVE_DL_STATES` — qBT downloading states: {downloading, forcedDL, stalledDL, metaDL, forcedMetaDL, queuedDL, checkingDL, moving, checkingResumeData}
- `REMOVE_MEDIA_FILE_EXTENSIONS` — 26 video formats
