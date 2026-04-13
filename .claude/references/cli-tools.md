# CLI Tools Reference

Prefer CLI tools over MCP servers — CLIs consume zero tokens when idle.

## Available CLIs

| CLI | Purpose | Common commands |
|-----|---------|----------------|
| `ctx7` | Library docs lookup | `ctx7 resolve <library>`, `ctx7 search <query>` |
| `task-master` | Task management | `task-master list`, `task-master next`, `task-master set-status` |
| `gh` | GitHub operations | `gh issue list`, `gh pr create`, `gh pr list` |
| `ruff` | Python linting | `ruff check --fix .`, `ruff format .` |
| `mypy` | Type checking | `mypy patchy_bot/` |
| `pytest` | Testing | `pytest tests/ -v`, `pytest --cov=patchy_bot` |
| `journalctl` | Service logs | `journalctl -u telegram-qbt-bot.service -f --no-pager -n 50` |
| `systemctl` | Service management | `systemctl status telegram-qbt-bot.service` |

## Rule
Always use CLI tools instead of searching for MCP alternatives.
Git operations → `gh` CLI. Library docs → `ctx7`. Testing → `pytest` directly.
