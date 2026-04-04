# Telegram qBittorrent Command Center

Telegram bot for managing qBittorrent from chat with a Plex-oriented flow.

## What changed

- Patchy chat mode: type normal messages (e.g. `Hey Patchy!`) for AI replies in read-only mode
- Plain-English search intent: ask explicitly with verbs like `find dune 2021 4k` / `search movie interstellar`
- `/start` now acts like a command center with quick-action buttons, including Remove
- Add flow now forces media choice (`Movies` or `TV`) per torrent
- Bot routes adds to dedicated NVMe library paths for Plex
- `/schedule` now researches shows online, auto-selects the best current season, compares released episodes against Plex/library inventory, caches TV metadata, and automatically retries/queues valid new episode releases after the release window

## Core behavior

1. You send a plain message (or `/search ...`).
2. Bot returns ranked results.
3. You tap **Add** on a result.
4. Bot asks: **Movies** or **TV**.
5. Bot adds torrent with the mapped qBittorrent category + path.

## Commands

- `/start` – command center + quick actions, including Remove
- `/remove` – search or browse Plex/library items, then delete from disk and trigger Plex cleanup after confirmation
- `/search <query> [options]`
  - `--min-seeds <n>`
  - `--min-size <e.g. 700MB>`
  - `--max-size <e.g. 8GB>`
  - `--sort seeds|size|name|leechers`
  - `--order asc|desc`
  - `--limit <1-50>`
  - `--search-cat all|movies|tv|music|games|anime|software|books`
  - `--plugin enabled|all|<plugin_name>`
- `/show <search_id> [page]`
- `/add <search_id> <index> <movies|tv>`
- `/active [n]`
- `/schedule`
  - Prompts for a show name instead of manual cron details
  - Uses TVMaze (and optional TMDb) metadata to confirm the right show
  - Prefers Plex inventory when configured, then falls back to the local TV library folders
  - Automatically retries qBittorrent searches after release+grace and auto-queues valid TV episode matches until the season is complete
- `/categories`
- `/profile`
- `/plugins`
- `/health`
- `/unlock <password>`
- `/logout`

## Security Controls

- `ALLOWED_TELEGRAM_USER_IDS` allowlist (required)
- Optional second factor: `BOT_ACCESS_PASSWORD` — required once on first use, then never again
- Group-chat access toggle: `ALLOW_GROUP_CHATS=false` by default
- VPN gate for downloads: `REQUIRE_VPN_FOR_DOWNLOADS=true` with `VPN_SERVICE_NAME` + `VPN_INTERFACE_NAME`

`/health` now checks the real dependency path instead of returning a placeholder: qBittorrent search/plugin access, category/path routing, VPN gate state, and the current access/control posture.

## Live Download Monitor

After add, the bot posts a live status message and updates it with an animated progress bar until completion (or timeout).
The monitor now treats qBittorrent's sentinel fields correctly, uses completed bytes for the done/total display, and can be configured for raw unsmoothed speed/progress output.

Tuning:
- `PROGRESS_REFRESH_SECONDS`
- `PROGRESS_EDIT_MIN_SECONDS`
- `PROGRESS_SMOOTHING_ALPHA`
- `PROGRESS_TRACK_TIMEOUT_SECONDS`

## Search Speed Tuning

If search feels slow, tune these:
- `SEARCH_TIMEOUT_SECONDS`
- `POLL_INTERVAL_SECONDS`
- `SEARCH_EARLY_EXIT_MIN_RESULTS`
- `SEARCH_EARLY_EXIT_IDLE_SECONDS`
- `SEARCH_EARLY_EXIT_MAX_WAIT_SECONDS`

The bot now returns partial results early when enough candidates are found, instead of always waiting for every plugin to finish.

## Patchy Chat Mode (Read-Only)

Patchy replies to normal conversation text by default.

- Search requests are intent-based (`find ...`, `search ...`, `movie ...`, `tv ...`)
- Guided input flows (season/episode/title prompts) always take priority
- Chat mode is strictly read-only (no state-changing actions)

Tuning:
- `PATCHY_CHAT_ENABLED`
- `PATCHY_CHAT_NAME`
- `PATCHY_CHAT_MODEL` (primary)
- `PATCHY_CHAT_FALLBACK_MODEL` (used if primary model is unavailable)
- `PATCHY_CHAT_TIMEOUT_SECONDS`
- `PATCHY_CHAT_MAX_TOKENS`
- `PATCHY_CHAT_TEMPERATURE`
- `PATCHY_CHAT_HISTORY_TURNS`
- `PATCHY_LLM_BASE_URL` / `PATCHY_LLM_API_KEY` (optional; auto-discovered from OpenClaw config when blank)

## Environment

Important routing settings in `.env`:

Search responsiveness tuning:
- `POLL_INTERVAL_SECONDS` (lower = checks results/status more often)
- `SEARCH_EARLY_EXIT_MIN_RESULTS` (allow fast return once this many raw results exist)
- `SEARCH_EARLY_EXIT_IDLE_SECONDS` (if no new results arrive for this long, return early)
- `SEARCH_TIMEOUT_SECONDS` (hard cap)

- `MOVIES_CATEGORY=Movies`
- `TV_CATEGORY=TV`
- `NVME_MOUNT_PATH=/mnt/nvme`
- `MOVIES_PATH=/mnt/nvme/Movies`
- `TV_PATH=/mnt/nvme/TV`
- `REQUIRE_NVME_MOUNT=true`
- `TMDB_API_KEY=` (optional; enriches schedule lookups with a stable TMDb id)
- `PLEX_BASE_URL=http://127.0.0.1:32400` (optional; enables direct Plex inventory checks)
- `PLEX_TOKEN=` (optional Plex token; when omitted or when Plex is temporarily degraded the schedule flow falls back to scanning `TV_PATH`)

With `REQUIRE_NVME_MOUNT=true`, add operations fail safely if NVMe is not mounted.

## Install / Run

```bash
cd /home/karson/Patchy_Bot/telegram-qbt
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
sudo cp telegram-qbt-bot.service /etc/systemd/system/telegram-qbt-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-qbt-bot.service
```

### Reproducible installs (recommended)

The repo ships `requirements.lock` and `requirements-dev.lock` — generated by
[pip-tools](https://pip-tools.readthedocs.io/) — that pin every transitive
dependency to an exact version and SHA-256 hash.  This prevents a changed
package from silently entering your environment (supply-chain hardening).

```bash
# Production environment
pip-sync requirements.lock

# Development environment (includes pytest etc.)
pip-sync requirements.lock requirements-dev.lock
```

To regenerate the lock files after editing `requirements.txt`:

```bash
pip-compile requirements.txt --generate-hashes -o requirements.lock
pip-compile requirements-dev.txt --generate-hashes -o requirements-dev.lock
```

---

For ad-hoc local runs outside systemd, export the environment first:

```bash
set -a
source .env
set +a
. .venv/bin/activate
python qbt_telegram_bot.py
```

Check status/logs:

```bash
systemctl status telegram-qbt-bot.service --no-pager
journalctl -u telegram-qbt-bot.service -n 100 --no-pager
```

Run the local verification suite:

```bash
. .venv/bin/activate
pytest -q
```
