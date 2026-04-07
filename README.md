# Patchy Bot Claude Plugin

This repository is a local Claude Code plugin project.

`claude plugin install` is the wrong command for this repo unless you also pass a marketplace plugin name. The CLI help on this machine shows:

```text
claude plugin install|i [options] <plugin>
```

Use these commands instead:

```bash
# Validate the local plugin manifest
claude plugin validate .

# Start Claude Code with this plugin loaded for the current session
claude --plugin-dir .
```

If you want the shorter form, use the helper script:

```bash
./scripts/claude-with-plugin
```

Notes:

- The plugin root is this repository root, not the `.claude-plugin/` directory.
- `claude plugin validate .claude-plugin` fails because the validator expects a plugin root directory or a direct path to `plugin.json`.
- Marketplace installs are separate from local development. Official local plugin docs in the installed `plugin-dev` toolkit recommend `cc --plugin-dir /path/to/plugin`.

## Project Skill Policy

Claude Code should treat the project-local skill set as the primary guidance for this repo.

- Default guard skills: `scope-guard`, `reuse-check`, `assumptions-audit`, `diff-review`
- Conditional Patchy skills: `telegram-ux-architect`, `telegram-chat-polisher`, `env-check`, `test-bot`, `restart`, `check-logs`, `db-inspect`, `debug-schedule`, `sync-parity`
- Manual only: `gh-issues-auto-fixer`

Do not preload or “always use” the giant `skills/global/` library. Use it only as backup reference when the project-local skills do not cover the task.
