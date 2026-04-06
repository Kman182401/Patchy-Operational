---
name: env-check
description: Validate the Patchy Bot .env configuration for completeness and consistency. Use when the user says "check env", "validate config", "env check", "check environment", "config issue", or before first startup after config changes.
---

# Environment Configuration Validator

Check that the bot's `.env` file has all required variables set and that related groups of variables are consistently configured. Never display actual secret values.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate environment validation, config schema reading, and consistency checks to the `config-infra-agent`.

## Step 1 — Read the config schema

Read the Pydantic config model to understand all expected variables:

```
/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/config.py
```

This file defines every environment variable the bot uses, which are required, which have defaults, and what types they expect.

## Step 2 — Read .env.example for reference

```
/home/karson/Patchy_Bot/telegram-qbt/.env.example
```

This shows the expected variable names and example values.

## Step 3 — Check which variables are actually set

Do NOT read or display the .env file directly (it contains secrets). Instead, check which variables are present and non-empty by reading config.py to understand the Pydantic model fields and their defaults.

Then verify the runtime config loads correctly:

```bash
cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -c "
from patchy_bot.config import Config
try:
    cfg = Config()
    print('CONFIG_LOAD: OK')
    # Print which optional integrations are active (without values)
    print(f'PLEX_CONFIGURED: {bool(cfg.plex_base_url and cfg.plex_token)}')
    print(f'TMDB_CONFIGURED: {bool(cfg.tmdb_api_key)}')
    print(f'VPN_REQUIRED: {cfg.require_vpn_for_downloads}')
    print(f'PASSWORD_AUTH: {bool(cfg.bot_access_password)}')
    print(f'PATCHY_CHAT: {bool(cfg.patchy_llm_base_url)}')
    print(f'ALLOWED_USERS: {len(cfg.allowed_telegram_user_ids)} configured')
    print(f'QBT_URL: {\"set\" if cfg.qbt_base_url else \"MISSING\"}')
    print(f'MOVIES_CAT: {cfg.movies_category or \"not set\"}')
    print(f'TV_CAT: {cfg.tv_category or \"not set\"}')
except Exception as e:
    print(f'CONFIG_LOAD: FAILED - {e}')
" 2>&1
```

## Step 4 — Check for consistency issues

Based on the config load results, flag these common problems:

### Required variables
- `TELEGRAM_BOT_TOKEN` — must be set, bot cannot start without it
- `ALLOWED_TELEGRAM_USER_IDS` — must have at least one user ID
- `QBT_BASE_URL` — must be set for core functionality

### Integration consistency (both or neither)
- **Plex**: `PLEX_BASE_URL` + `PLEX_TOKEN` — both must be set if either is
- **VPN**: `REQUIRE_VPN_FOR_DOWNLOADS` + `VPN_SERVICE_NAME` + `VPN_INTERFACE_NAME` — if VPN is required, the service and interface must be configured
- **Password auth**: `BOT_ACCESS_PASSWORD` should have `AUTH_MODE` set appropriately
- **Patchy Chat**: `PATCHY_LLM_BASE_URL` + `PATCHY_LLM_API_KEY` — both needed for chat mode

### Category routing
- `MOVIES_CATEGORY` and `TV_CATEGORY` should be set for smart routing
- `MOVIES_PATH` and `TV_PATH` should point to valid directories if set

## Report format

### Configuration Status
- Config loads: YES / NO (with error)
- Required vars: all set / missing X

### Active Integrations
| Integration | Status | Notes |
|-------------|--------|-------|
| qBittorrent | Active | URL configured |
| Plex | Active / Inactive / Misconfigured | |
| TMDb | Active / Inactive | |
| VPN Gate | Active / Inactive / Misconfigured | |
| Password Auth | Active / Inactive | |
| Patchy Chat | Active / Inactive / Misconfigured | |

### Issues Found
List any problems with severity:
- **Critical** — bot won't start
- **Warning** — partial config, feature won't work
- **Info** — optional feature not configured (fine to ignore)

### Verdict
- **Ready** — all required config present, integrations consistent
- **N issues** — list what needs fixing
