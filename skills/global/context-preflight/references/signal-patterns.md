# Signal Extraction Reference

Patterns for identifying projects and files from plan/prompt text.

---

## Project Identity Signals

### High-confidence signals (exact match → known project)
| Signal pattern | Likely project |
|----------------|---------------|
| "torrent", "qBittorrent", "Plex", "Patchy", "RTN", "codec", "release group" | Patchy_Bot |
| "IBKR", "options", "expiry", "theta", "File-Window", "trading" | File-Window |
| "Kraken", "spot", "openclaw", "order book" | openclaw-kraken |
| "CTF", "binary", "crack", "hash", "wordlist", "cracking_station" | cracking_station |
| "fuzz", "LLM", "jailbreak", "FuzzyAI", "adversarial" | FuzzyAI |
| "agent", "hook", "skill", "CLAUDE.md", "subagent", ".claude" | Claude Code ecosystem |

### Medium-confidence signals (require corroboration)
- Framework names alone (pytest, FastAPI, aiogram) — check tech stack against known projects
- Generic verbs ("fix the filter", "update the config") — need domain noun to disambiguate
- Language alone (Python, TypeScript) — insufficient without domain context

---

## Common File Patterns by Project Type

### Python bot / automation
```
<root>/
├── CLAUDE.md
├── README.md
├── pyproject.toml          ← always include
├── <package>/
│   ├── __init__.py         ← tier 3
│   ├── bot.py / main.py    ← tier 3 (entry point)
│   ├── config.py           ← tier 2 if config is relevant
│   ├── <affected_module>.py ← tier 2
│   └── models.py / types.py ← tier 3
└── tests/
    └── test_<module>.py    ← tier 2
```

### Claude Code ecosystem (agents/skills/hooks)
```
~/.claude/
├── CLAUDE.md               ← tier 1
├── settings.json           ← tier 1 if agent config relevant
├── agents/
│   └── <agent-name>.md     ← tier 2 if agent is subject of plan
└── skills/
    └── <skill-name>/
        └── SKILL.md        ← tier 2 if skill is subject

~/CLAUDE.md                 ← tier 1 (global rules)
<project>/CLAUDE.md         ← tier 1 (project rules)
```

### Trading / quant system
```
<root>/
├── CLAUDE.md
├── README.md
├── requirements.txt / pyproject.toml
├── <src>/
│   ├── strategy.py         ← tier 2 if strategy is referenced
│   ├── broker.py           ← tier 2 if broker/API calls involved
│   └── config.py           ← tier 2 (API keys config, never .env)
└── tests/
```

---

## File Exclusion Rules

Always exclude:
- `.env`, `*.secret`, `credentials.*`, `secrets.*`, `*.pem`, `*.key`
- `__pycache__/`, `.git/`, `node_modules/`, `dist/`, `build/`
- Binary files, images, compiled artifacts
- Log files (`.log`, `*.log`)
- Large data files unless explicitly task-relevant

Substitute for:
- `.env` → `.env.example` or `config.example.*`
- Production secrets → sanitized config schema

---

## Ambiguity Resolution Checklist

When unsure which project:
1. Check `~/CLAUDE.md` for project directory listings
2. `find ~ -maxdepth 2 -name "CLAUDE.md"` to enumerate all project roots
3. Cross-reference tech stack signals against all found CLAUDE.md files
4. If still ambiguous → list top 2 candidates and ask user

When unsure which file within a project:
1. `grep -r "<key_term>" <root> --include="*.py" -l` to find by content
2. Check imports: what does the main entry point import?
3. Follow the call chain from entry point to affected component
