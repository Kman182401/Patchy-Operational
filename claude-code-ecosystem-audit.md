# Claude Code Ecosystem Audit Report
## Generated: 2026-04-13
## Project: Patchy Bot (~/Patchy_Bot)

This is a read-only audit of every Claude Code-facing configuration in the Patchy Bot project. File contents are verbatim where short; long files are summarized with key excerpts.

---

## 1. CLAUDE.md Configuration

### 1.1 Project CLAUDE.md — `/home/karson/Patchy_Bot/CLAUDE.md`

- Size: 7.1 KB, 81 lines, modified 2026-04-12 23:07
- Word count ~1,000 → **~1,300 tokens**
- Sections: Guardrails, Core Invariants, Restart Rule, Push Rule, CLAUDE.md/Memory Refresh Rule, File Ownership, High-Value Conventions, Memory Systems (two), Obsidian Project Vault

**Full contents (verbatim):**

```markdown
# Patchy Bot — Project Instructions

## Guardrails
- Do not run raw git write commands (`git commit`, `git push`, branch/reset) in `/home/karson/Patchy_Bot`. The `push` shell alias is the only sanctioned commit+push path (see Push Rule).
- Prefer code over docs when they disagree.
- Keep changes targeted. Do not rewrite unrelated flows or move files without a clear reason.
- Do not break `telegram-qbt/qbt_telegram_bot.py`; it is a back-compat shim unless the user explicitly wants it changed.
- Use the `patchy-bot` skill for the architecture map, module ownership, callback namespaces, DB ownership, and restart/test commands.

## Core Invariants
- Most runtime code lives in `telegram-qbt/patchy_bot/`.
- State that must survive restarts belongs in SQLite via `telegram-qbt/patchy_bot/store.py`. Transient chat/UI flow state can stay in memory.
- Search, add-flow, and Telegram UI behavior should stay aligned across movie and TV paths unless the user explicitly wants divergence.
- Dynamic values inserted into Telegram HTML messages must be escaped with `_h()`.
- If a download/progress change touches both the immediate path and the deferred-hash pending path, update both paths.

## Restart Rule
- After changes under `telegram-qbt/patchy_bot/` or related runtime config/service files, restart `telegram-qbt/telegram-qbt-bot.service` so the running bot picks up the change.

## Push Rule
- After completing any task that modifies files under `/home/karson/Patchy_Bot/`, run the `push` shell alias in Bash. It auto-commits and pushes to `origin/main`.
- The `push` alias is the ONLY sanctioned git path — never run raw `git commit`/`git push`/branch commands manually.
- End-of-task order: post-changes-audit → code-simplifier agent on touched code → restart the service (if runtime code changed) → run `push` → `/revise-claude-md`. All five must happen before reporting "done".

## CLAUDE.md / Memory Refresh Rule
- At the end of any productive session, invoke `/revise-claude-md` (claude-md-management plugin).
- If it proposes no changes, report "no new learnings captured" and move on.
- Runs AFTER `push` so any CLAUDE.md updates land in the NEXT commit.

## File Ownership
- Runtime code: `telegram-qbt/patchy_bot/`
- Repo-local Claude behavior: `.claude/`, `skills/`, `.claude-plugin/`

## High-Value Conventions
- Run `pytest -q` in `telegram-qbt/` for touched Python areas when tests exist.
- Prefer the curated project-local skills; **do not restore a mirrored global skill library to this repo**.
- Keep instructions that are workflow-specific, command-specific, or operationally detailed out of this file.
- Preserve path safety and media-type validation when moving or deleting files.

## Memory Systems (two, distinct roles)
1. **Auto-memory (canonical, live)** — `~/.claude/projects/-home-karson-Patchy-Bot/memory/`
2. **Project-local legacy log** — `~/Patchy_Bot/.claude/memory/` (read-mostly archive)

## Obsidian Project Vault
Vault at `Patchy Ops/` with numbered-folder layout (00-Home, 01-System, 02-Work, 03-Reference, 04-Ideas, 05-Changelog, _templates). Rules require vault sync after task completion. Use `vault-manager` subagent for complex ops.
```

**Flags for this file:**
| Check | Result |
|---|---|
| Compaction instructions | NO |
| Model/effort routing instructions | NO (only global CLAUDE.md and child files reference this) |
| Web research instructions | NO |
| Skill/subagent routing instructions | Partial — references `patchy-bot` skill, `vault-manager` agent, `code-simplifier` agent, `post-changes-audit`, `/revise-claude-md` |

### 1.2 Global CLAUDE.md — `/home/karson/CLAUDE.md`

- Size: 6.5 KB, 189 lines, modified 2026-04-06 13:11
- Word count ~850 → **~1,100 tokens**
- Headline: "Claude Code Configuration - RuFlo V3"

This is a **claude-flow / RuFlo V3 swarm manifesto**. It contains detailed rules about swarm orchestration, 3-tier model routing (Agent Booster WASM / Haiku / Sonnet-Opus), `npx @claude-flow/cli` commands, and 60+ claude-flow agent types.

**Key sections:** Behavioral Rules, File Organization, Project Architecture, Build & Test (npm-oriented), Security Rules, Concurrency rules, Swarm Orchestration, 3-Tier Model Routing table, Swarm Configuration, Swarm Execution Rules, V3 CLI Commands, Available Agents (60+), Memory Commands Reference, Quick Setup.

**Flags:**
| Check | Result |
|---|---|
| Compaction instructions | NO |
| Model/effort routing | YES — 3-tier routing table (Agent Booster / Haiku / Sonnet-Opus) |
| Web research instructions | NO |
| Skill/subagent routing | YES — lists 60+ claude-flow agent types |

**Contradictions with project CLAUDE.md:**
- Global says "Use `/src`, `/tests`, `/docs`, `/config`, `/scripts`, `/examples`"; project is a Python repo that does NOT use this layout (runtime lives in `telegram-qbt/patchy_bot/`).
- Global says "Build: `npm run build`, Test: `npm test`, Lint: `npm run lint`"; project is Python — uses `pytest`, `ruff`, `mypy`.
- Global promotes claude-flow swarms, CLI tools, HNSW, neural, raft consensus, hive-mind — none of which appear in the actual Patchy Bot workflow.
- Global says "NEVER save working files, text/mds, or tests to the root folder"; yet project instructs saving this audit to `~/Patchy_Bot/claude-code-ecosystem-audit.md` (root).
- Global loads at every session as `Contents of /home/karson/CLAUDE.md` — consumes ~1,100 tokens that are mostly irrelevant to this project.

**There is a second global file at `/home/karson/.claude/CLAUDE.md`** (shown in system reminder only, ~90 words, ~120 tokens). Its rules are concise and aligned with project practice: be concise, verify facts, prefer minimal changes, ask before destructive ops, keep project-specific content in project `.claude/`.

### 1.3 Child CLAUDE.md Files

Two child files found:

**`/home/karson/Patchy_Bot/telegram-qbt/CLAUDE.md`** — 190 lines, modified 2026-04 (recent). ~2,100 words → **~2,700 tokens**. This is the *substantive* project playbook:
- Project overview (Python 3.12+, PTB polling, SQLite WAL, asyncio; `bot.py` ~4,752 → actually **5,543** lines now)
- Architecture: handlers, UI, clients, CallbackDispatcher (2 exact + 12 prefix), HandlerContext, store.py (14 tables, 56+ CRUDs), 18 slash commands, 760 tests across 23 test files (actual file count: 31 test files)
- Coding conventions: HTML parse mode, `_h()` escape, colon-delimited callback data, ✅ prefix, Back/Home nav, inline buttons
- Code patterns table
- Parity Rule (movie/TV), Download Paths (immediate + deferred-hash), EMA variables
- Safety Rules: path safety (`PurePosixPath.is_relative_to`), SQLite (`0o600`, WAL, `busy_timeout=5000`), thread safety (`QBClient` lock), VPN/network (`current_network_interface` must not be VPN), secrets
- Service operations (systemctl restart, journalctl, DB file, backup, dependencies, hardening)
- **Subagent routing table for 25 agents** (actual count is 26)
- Post-Changes Audit modes (quick/standard/deep)
- Subagent-Driven Development rule (ALL work must delegate)
- Task Master, Settings (thinking enabled, Sonnet default, Opus for audit), Verification

**Flags:** Contains explicit subagent routing, model routing (Sonnet default, Opus for audit agents), service ops. Does NOT contain web-research instructions or compaction rules.

**`/home/karson/Patchy_Bot/.taskmaster/CLAUDE.md`** — 436 lines, modified 2026-04-04 19:28. ~3,500 words → **~4,500 tokens**. This is the **stock Task Master integration guide** unmodified from upstream. Contains generic task-master CLI docs, MCP tool tiers, workflow examples, git worktree patterns, troubleshooting. **None of it is Patchy Bot-specific.** Large token cost for negligible project value because the project uses Task Master infrequently (0 tasks currently defined).

### 1.4 CLAUDE.md Gap Analysis

**Total token load across all CLAUDE.md files touching this project:**
| File | Tokens (approx) |
|---|---|
| `~/.claude/CLAUDE.md` | ~120 |
| `~/CLAUDE.md` | ~1,100 |
| `Patchy_Bot/CLAUDE.md` | ~1,300 |
| `Patchy_Bot/telegram-qbt/CLAUDE.md` | ~2,700 |
| `Patchy_Bot/.taskmaster/CLAUDE.md` | ~4,500 |
| **Total** | **~9,720 tokens** on every session load |

**Duplication & contradictions:**
- "NEVER commit secrets / .env" — repeated in `~/CLAUDE.md`, project, child, telegram-qbt child
- Global `~/CLAUDE.md` contradicts project stack (Python vs npm, swarm vs PTB)
- `.taskmaster/CLAUDE.md` is stock boilerplate — 4,500 tokens for an integration barely used
- Telegram-qbt child claims "25 agents in `.claude/agents/`" but actual count is **26** (movie-tracking-agent added)
- Telegram-qbt child claims `bot.py ~4,752 lines` — actual is **5,543**
- Telegram-qbt child claims "760 tests across 23 test files" — actual file count is **31**

**Missing instructions:**
- No compaction / context-hygiene instructions anywhere
- No web research guidance (when to use WebFetch/WebSearch, domain whitelist is in `settings.local.json` but not explained)
- No explicit per-agent model/effort routing in project CLAUDE.md (only in telegram-qbt child, and vaguely)

---

## 2. Settings Configuration

### 2.1 settings.json Contents

**`/home/karson/Patchy_Bot/.claude/settings.json`** (109 lines, modified 2026-04-11 20:37)

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": [
      "Bash(git diff:*)", "Bash(git status:*)", "Bash(git log:*)",
      "Bash(git show:*)", "Bash(git remote:*)",
      "Bash(.venv/bin/python -m pytest:*)",
      "Bash(.venv/bin/python -m ruff:*)",
      "Bash(.venv/bin/python -m mypy:*)",
      "Bash(systemctl status:*)", "Bash(systemctl is-active:*)",
      "Bash(systemctl cat:*)", "Bash(journalctl:*)"
    ],
    "deny": [
      "Read(./.env)", "Read(./.env.*)", "Read(./secrets/**)"
    ]
  },
  "respectGitignore": true,
  "alwaysThinkingEnabled": true,
  "model": "claude-opus-4-6",
  "enabledPlugins": {
    "pyright-lsp@claude-plugins-official": true,
    "semgrep@claude-plugins-official": false,
    "context7@claude-plugins-official": true,
    "playwright@claude-plugins-official": false,
    "chrome-devtools-mcp@claude-plugins-official": false
  },
  "hooks": {
    "SessionStart":   [{ matcher:"",            hooks:[{type:"command", command:"bash .../session-start-context.sh"}] }],
    "PreToolUse":     [{ matcher:"Bash",        hooks:[{type:"command", command:"bash .../pre-bash-guard.sh"}] }],
    "PostToolUse":    [{ matcher:"Write|Edit",  hooks:[{type:"command", command:"bash .../post-edit-format.sh"}] },
                       { matcher:"Write|Edit|Bash", hooks:[{type:"command", command:"bash .../memory-recorder.sh"}] }],
    "Stop":           [{ matcher:"",            hooks:[{type:"command", command:"bash .../session-finalizer.sh"}] },
                       { matcher:"",            hooks:[{type:"command", command:"bash .../stop-audit-trigger.sh"}] }],
    "PermissionRequest":[{ hooks:[{type:"command", command:"bash .../auto-approve.sh", statusMessage:"Auto-approving..."}]}]
  }
}
```

**`/home/karson/Patchy_Bot/.claude/settings.local.json`** (42 lines) — domain allowlist for WebFetch: telegram.org, docs.pydantic.dev, github.com, deepwiki.com, trash-guides.info, gramio.dev, plus ~25 other domains. Also `systemctl cat/status/list-*`, `crontab -l`, `sudo crontab:*`.

**`/home/karson/.claude/settings.json`** (36 lines) — global:
```json
{
  "permissions": {
    "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "Agent",
              "mcp__context7__*", "mcp__playwright__*", "mcp__claude-flow__*", "mcp__exa__*",
              "mcp__filesystem__*", "mcp__obsidian__*", "mcp__plugin_playwright_playwright__*",
              "mcp__task-master__*", "mcp__tavily__*"],
    "deny": [],
    "defaultMode": "bypassPermissions"
  },
  "statusLine": { "type":"command", "command":"bash /home/karson/.claude/statusline-command.sh" },
  "enabledPlugins": { "context7@claude-plugins-official": true, "playwright@claude-plugins-official": true },
  "model": "claude-opus-4-6",
  "skipDangerousModePermissionPrompt": true
}
```

### 2.2 Settings Assessment

- **Default mode = `bypassPermissions`** AND a `PermissionRequest` hook that auto-approves everything → the project effectively has **no permission gate**. Destructive ops are only blocked via `pre-bash-guard.sh`.
- **Model = `claude-opus-4-6`** at both global and project level — expensive default. Telegram-qbt child CLAUDE.md says "Sonnet default; Opus for audit agents" which contradicts.
- **`alwaysThinkingEnabled: true`** adds extended-thinking tokens to every turn.
- **Allowlist duplicates settings.local.json** — `systemctl cat/status` is present in both.
- **Deny list is correct** for `.env` and `secrets/`, but the `Read(./.env)` pattern only covers relative paths; an absolute-path read could bypass it.
- **Global allow list is over-broad** (`Bash`, `Write`, `Edit`, `Agent` unrestricted). Combined with `skipDangerousModePermissionPrompt: true`, this is intentional "trust everything" posture.
- **Plugins enabled at project level:** pyright-lsp, context7. Disabled: semgrep, playwright, chrome-devtools-mcp. Global also enables playwright.
- **semgrep disabled** despite being useful for a security-conscious bot — worth reconsidering.

---

## 3. MCP Servers

### 3.1 Project MCP Config

**No `.mcp.json` in project root.** Only `~/.mcp.json` exists.

### 3.2 Global MCP Config — `/home/karson/.mcp.json`

```json
{
  "mcpServers": {
    "claude-flow": {
      "command": "npx",
      "args": ["-y", "@claude-flow/cli@3.5.75", "mcp", "start"],
      "env": {
        "npm_config_update_notifier": "false",
        "CLAUDE_FLOW_MODE": "v3",
        "CLAUDE_FLOW_HOOKS_ENABLED": "true",
        "CLAUDE_FLOW_TOPOLOGY": "hierarchical-mesh",
        "CLAUDE_FLOW_MAX_AGENTS": "15",
        "CLAUDE_FLOW_MEMORY_BACKEND": "hybrid"
      }
    }
  }
}
```

**Additionally visible via tool listing** (registered elsewhere, not in `~/.mcp.json`):
- `mcp__context7__*` (plugin)
- `mcp__playwright__*` / `mcp__plugin_playwright_playwright__*` (plugin)
- `mcp__exa__*` (web search)
- `mcp__filesystem__*`
- `mcp__obsidian__*` (for vault)
- `mcp__task-master__*`
- `mcp__tavily__*` (web search)

### 3.3 MCP Assessment

| Server | Source | Env vars (names only) | Assessment |
|---|---|---|---|
| claude-flow | `~/.mcp.json` | `CLAUDE_FLOW_MODE`, `CLAUDE_FLOW_HOOKS_ENABLED`, `CLAUDE_FLOW_TOPOLOGY`, `CLAUDE_FLOW_MAX_AGENTS`, `CLAUDE_FLOW_MEMORY_BACKEND`, `npm_config_update_notifier` (no secrets) | **300+ tools exposed.** Massive tool-schema overhead on startup. The project's CLAUDE.md describes no claude-flow workflow, and project code uses none of it. **Strong candidate for removal.** |
| context7 | plugin | unknown | Documentation lookup — likely useful |
| playwright | plugin | unknown | Disabled at project level; enabled globally |
| exa | plugin | unknown | Web search — redundant with tavily |
| filesystem | plugin | unknown | Redundant with built-in Read/Write/Glob/Grep tools |
| obsidian | plugin | unknown | Needed for `vault-manager` agent and `Patchy Ops/` vault |
| task-master | plugin | unknown | Used by 46 `/tm:*` commands but **0 tasks defined** |
| tavily | plugin | unknown | Web search |

**Concerns:**
1. **claude-flow is a token/tool sink** — its ~300-tool schema dominates the deferred tool list and offers ~0 value for this project.
2. **Three web-search providers** (WebFetch/WebSearch built-in, exa, tavily) — redundant.
3. **No project-level `.mcp.json`** means the project can't override global registration selectively.
4. **task-master** is registered but unused (0 tasks) — still paying the tool-schema cost.

---

## 4. Subagents

Directory: `/home/karson/Patchy_Bot/.claude/agents/` — **26 files** total (the telegram-qbt CLAUDE.md says "25 agents" — out of date).

### 4.1 Per-Agent Audit

Only 6 agents have a *complete* modern frontmatter (`name`, `description`, `tools`, `model`, `memory`, `color`): **dependency-audit, secret-scanner, lint-type, supply-chain-scan, coverage-analysis, static-analysis**. All are security/quality scanners with `model: opus`, `tools: Bash, Read`, `memory: project`. No issues.

The remaining 20 agents have varying degrees of missing metadata. Full per-agent breakdown:

| # | Agent | model | effort | tools | words | References | Critical gaps |
|---|---|---|---|---|---|---|---|
| 1 | dependency-audit-agent | opus | ✓ | Bash,Read | 840 | — | none |
| 2 | secret-scanner-agent | opus | ✓ | Bash,Read | 820 | — | none |
| 3 | test-agent | ❌ | ❌ | ❌ | 1100 | security-agent | missing model/effort/tools |
| 4 | database-agent | ❌ | ❌ | ❌ | 1200 | — | missing model/effort/tools |
| 5 | config-infra-agent | ❌ | ❌ | ❌ | 1100 | — | missing model/effort/tools |
| 6 | lint-type-agent | opus | ✓ | Bash,Read | 920 | — | none |
| 7 | ui-agent | ❌ | ❌ | ❌ | 1300 | frontend-design, architecture skills | missing model/effort/tools |
| 8 | release-manager-agent | haiku | ❌ | Read,Bash,Grep,Glob | 580 | test, config-infra, monitoring | missing effort |
| 9 | performance-optimization-agent | ❌ | ❌ | ❌ | 750 | monitoring, security | missing everything |
| 10 | supply-chain-scan-agent | opus | ✓ | Bash,Read | 720 | — | none |
| 11 | audit-correctness-agent | opus | ❌ | (`skills: diff-review`) | 620 | diff-review skill | **no `name`**, non-standard `permissionMode`+`maxTurns` |
| 12 | security-agent | opus | ❌ | Read,Grep,Glob,Bash | 1150 | orchestrator | missing effort, no memory, read-only enforced in prompt only |
| 13 | movie-tracking-agent | ❌ | ❌ | ❌ | 920 | search-download, plex | missing everything, ambiguity with schedule-agent |
| 14 | coverage-analysis-agent | opus | ✓ | Bash,Read | 820 | — | none |
| 15 | taskmaster-sync-agent | haiku | ❌ | Read,Bash,Grep,Glob | 520 | — | missing effort |
| 16 | monitoring-metrics-agent | ❌ | ❌ | ❌ | 900 | config-infra, performance | missing everything, design phase |
| 17 | search-download-agent | ❌ | ❌ | ❌ | 1400 | plex, security, torrent-abstraction | **LARGEST coord surface** (7 callback prefixes, 5 files), missing everything |
| 18 | vault-manager | ❌ | ❌ | ❌ | 320 | — | no Obsidian tools listed despite owning vault ops |
| 19 | audit-performance-agent | opus | ❌ | (`skills: diff-review`) | 550 | — | **no `name`**, non-standard frontmatter, near-duplicate of audit-correctness |
| 20 | torrent-client-abstraction-agent | ❌ | ❌ | ❌ | 720 | search-download | design phase, ADR required |
| 21 | remove-agent | opus | ❌ | ❌ | 1350 | security (MANDATORY), plex, database | missing effort/tools on a high-risk (irreversible delete) agent |
| 22 | static-analysis-agent | opus | ✓ | Bash,Read | 820 | — | none |
| 23 | schedule-agent | ❌ | ❌ | ❌ | 1550 | search-download, plex, security | **LARGEST domain**, owns movie schedule callbacks (overlaps movie-tracking-agent) |
| 24 | security-scan-orchestrator | opus | ❌ | Bash,Read | 1000 | 6 specialist agents | missing effort; orchestrates 6 agents without formal `blockedBy` |
| 25 | plex-agent | ❌ | ❌ | ❌ | 900 | search-download, schedule, remove | missing everything, integration point |
| 26 | media-library-abstraction-agent | ❌ | ❌ | ❌ | 600 | — | design phase, ADR required |

### 4.2 Subagent Summary Table (machine-readable)

```
agent                             | model  | effort | tools | words | refs
----------------------------------|--------|--------|-------|-------|-----
dependency-audit-agent            | opus   | yes    | yes   |  840  | no
secret-scanner-agent              | opus   | yes    | yes   |  820  | no
test-agent                        | -      | -      | -     | 1100  | yes
database-agent                    | -      | -      | -     | 1200  | no
config-infra-agent                | -      | -      | -     | 1100  | no
lint-type-agent                   | opus   | yes    | yes   |  920  | no
ui-agent                          | -      | -      | -     | 1300  | yes
release-manager-agent             | haiku  | -      | yes   |  580  | yes
performance-optimization-agent    | -      | -      | -     |  750  | yes
supply-chain-scan-agent           | opus   | yes    | yes   |  720  | no
audit-correctness-agent           | opus   | -      | skill |  620  | yes
security-agent                    | opus   | -      | yes   | 1150  | yes
movie-tracking-agent              | -      | -      | -     |  920  | yes
coverage-analysis-agent           | opus   | yes    | yes   |  820  | no
taskmaster-sync-agent             | haiku  | -      | yes   |  520  | no
monitoring-metrics-agent          | -      | -      | -     |  900  | yes
search-download-agent             | -      | -      | -     | 1400  | yes
vault-manager                     | -      | -      | -     |  320  | no
audit-performance-agent           | opus   | -      | skill |  550  | no
torrent-client-abstraction-agent  | -      | -      | -     |  720  | yes
remove-agent                      | opus   | -      | -     | 1350  | yes
static-analysis-agent             | opus   | yes    | yes   |  820  | no
schedule-agent                    | -      | -      | -     | 1550  | yes
security-scan-orchestrator        | opus   | -      | yes   | 1000  | yes
plex-agent                        | -      | -      | -     |  900  | yes
media-library-abstraction-agent   | -      | -      | -     |  600  | no
```

### 4.3 Subagent Gap Analysis

**Missing `model:`** — 13 agents: test, database, config-infra, ui, performance-opt, movie-tracking, monitoring-metrics, search-download, vault-manager, torrent-client-abstraction, remove, plex, media-library-abstraction.
(`remove-agent` does have `model: opus` in the frontmatter per the audit detail.)

**Missing `effort:`** — 22 agents (all except the 6 security-scan agents + 2 audit agents implicit).

**Missing `tools:`** — 13 agents (same set as missing model).

**Missing `memory:` (should have `memory: project`)** — 9 agents: database, ui, security, search-download, monitoring-metrics, remove, plex, schedule, vault-manager.

**Non-standard frontmatter** — `audit-correctness-agent.md` and `audit-performance-agent.md` use `permissionMode: plan` + `maxTurns` and lack a `name:` field. They appear to be skill-driven reviewers masquerading as agents.

**Domain ownership overlaps:**
1. **Movie scheduling** — `schedule-agent` already owns `on_cb_movie_schedule()` / `on_text_movie_schedule()` and `msch:` callback prefix, but `movie-tracking-agent` also claims them. One must yield.
2. **Callback prefixes** — 7 prefixes (`a:`, `d:`, `p:`, `stop:`, `dl:manage`, `tvpost:`, `moviepost:`) are claimed by both `search-download-agent` and `ui-agent`. Ownership is ambiguous.
3. **Plex integration** — `plex-agent`, `search-download-agent`, `remove-agent`, `schedule-agent`, `media-library-abstraction-agent` all touch Plex in different contexts.

**Agents in design phase only (not yet implemented):**
- `movie-tracking-agent` (partial)
- `monitoring-metrics-agent`
- `torrent-client-abstraction-agent`
- `media-library-abstraction-agent`

**Informal dependencies (no metadata):**
- `remove-agent` → `security-agent` "MANDATORY" (prose only)
- `search-download-agent` → `plex-agent`, `security-agent`
- `performance-optimization-agent` → `database-agent` sign-off (prose only)
- `security-scan-orchestrator` → 6 specialist agents (sequential, no `blockedBy`)

---

## 5. Skills

### 5.1 Project Skills

**Top-level project skills** — `/home/karson/Patchy_Bot/skills/` (excluding `global/` subdir):

| Skill | SKILL.md | Lines | Supporting files | Status |
|---|---|---|---|---|
| assumptions-audit | ✓ | 166 | — | active, identical to global copy |
| diff-review | ✓ | 203 | — | active, identical to global copy |
| reuse-check | ✓ | 166 | — | active, identical to global copy |
| scope-guard | ✓ | 151 | — | active, identical to global copy |
| **patchy-bot** | ✗ MISSING | — | — | **EMPTY DIR — SKILL.md absent**, yet CLAUDE.md instructs "Use the `patchy-bot` skill for the architecture map…" |

**Plugin skills** — `/home/karson/Patchy_Bot/.claude-plugin/skills/` (10 skills, all domain-specific to Patchy Bot):

| Skill | Lines | Purpose |
|---|---|---|
| check-logs | 91 | Pull recent systemd service logs, surface what matters |
| db-inspect | 159 | Query live SQLite DB state / schema / table contents |
| debug-schedule | 121 | Diagnose TV schedule runner / auto-tracking state |
| env-check | 107 | Validate `.env` without exposing secrets |
| gh-issues-auto-fixer | 302 | Fetch GitHub issues, route to domain agents, open PRs (user-invocable) |
| restart | 68 | Restart `telegram-qbt-bot.service` and verify |
| sync-parity | 66 | Audit movie/TV feature parity after shared flow changes |
| telegram-chat-polisher | 186 | Polish chat copy / button labels / keyboard layouts |
| telegram-ux-architect | 107 | Decide where an interaction belongs / flow structure before coding |
| test-bot | 70 | Run project verification stack from venv |

All 10 have SKILL.md with proper frontmatter; none have scripts/, references/, or resources/.

**Mirrored global skills** — `/home/karson/Patchy_Bot/skills/global/` — **43 directories, byte-for-byte mirror of `~/.claude/skills/`.**

### 5.2 Global Skills — `/home/karson/.claude/skills/`

43 skills available (full list in Section 5.3). The mirror in `skills/global/` contains the same 43.

### 5.3 Skills Summary Table

**Project top-level (5)**: assumptions-audit, diff-review, reuse-check, scope-guard, patchy-bot (empty)

**Plugin (10)**: check-logs, db-inspect, debug-schedule, env-check, gh-issues-auto-fixer, restart, sync-parity, telegram-chat-polisher, telegram-ux-architect, test-bot

**Mirrored global (43)**: analyze, assumptions-audit, audit, audit-trail, build, change-forensics, code-changes, commit, context-preflight, create-branch, create-pr, debug-and-fix, debugging-wizard, deploy-checklist, diff-review, expert-analysis, git-pushing, impact-radar, linter, pair-programming (1202 lines), plan-builder (1085 lines, has references/), plan-forge, plan-implementation, post-changes-audit, post-fix-memory, push, read-only-plans, regression-guard, researcher, reuse-check, scope-guard, security-review, security-scan, send-to-phone, skill-builder, standup, test-driven-development, testing-strategy, test-master, test-runner, the-fool, verification-loop, verification-quality

**Total in project tree:** 5 + 10 + 43 = **58 skill directories**; 57 usable (patchy-bot empty).

### Duplicate / Mirror Analysis

- **`skills/global/` is a byte-for-byte mirror of `~/.claude/skills/`** (verified on spot-checks incl. `plan-builder/references/` subdir).
- **This directly violates the CLAUDE.md rule:** *"Prefer the curated project-local skills; do not restore a mirrored global skill library to this repo."*
- The 4 top-level project skills (assumptions-audit, diff-review, reuse-check, scope-guard) are **identical copies** of the global versions — no project-specific customization. They exist twice in the repo (top-level + global mirror).
- **`patchy-bot` skill is empty** despite being referenced by name in CLAUDE.md.

---

## 6. Hooks

### 6.1 Current Hook Configuration

Seven command-type hooks wired via `settings.json`:

| Event | Matcher | Script | Lines | Purpose |
|---|---|---|---|---|
| SessionStart | `""` | `session-start-context.sh` | 9 | Runs `task-master list` at session start |
| PreToolUse | `Bash` | `pre-bash-guard.sh` | 20 | **Blocks** destructive `rm -rf` on repo paths and bash reads of `.env`/secrets (exit 2) |
| PostToolUse | `Write\|Edit` | `post-edit-format.sh` | 18 | Runs `ruff format` on edited Python files (non-blocking) |
| PostToolUse | `Write\|Edit\|Bash` | `memory-recorder.sh` | 38 | Appends event JSONL to `.event-buffer.jsonl` |
| Stop | `""` | `session-finalizer.sh` | 67 | Drains buffer to `sessions.md`, rotates archives (keeps last 5) |
| Stop | `""` | `stop-audit-trigger.sh` | 30 | Triggers post-changes-audit skill based on change size |
| PermissionRequest | — | `auto-approve.sh` | 6 | **Auto-approves all permission requests** |

All are `type: "command"` (no prompt-type anti-patterns).

### 6.2 Hook Assessment

| Hook | Issue |
|---|---|
| `auto-approve.sh` | **Security risk.** Combined with `defaultMode: bypassPermissions` and `skipDangerousModePermissionPrompt: true`, removes all permission gates. The only remaining guard is `pre-bash-guard.sh`. |
| `stop-audit-trigger.sh` | **Hardcoded path** `cd ~/Patchy_Bot/telegram-qbt`. Breaks if Claude Code is run from `~/Patchy_Bot/` directly. Not portable. |
| `session-finalizer.sh` | Fails silently if `sessions.md` doesn't exist but buffer has events (it currently doesn't — see § 8). Uses `mktemp` safely. |
| `pre-bash-guard.sh` | Correct. Guards `rm -rf`, `.env` reads. |
| `memory-recorder.sh` | Clean JSONL append with jq fallbacks. No issues. |
| `session-start-context.sh` | Clean. Fallback if task-master missing. |
| `post-edit-format.sh` | Non-blocking, safe. |

---

## 7. File Indexing (.claudeignore)

### 7.1 Current .claudeignore

**NO `.claudeignore` FILE EXISTS** in `/home/karson/Patchy_Bot/`. (`respectGitignore: true` is set, so gitignore is honored, but there is no Claude-specific exclusion file.)

### 7.2 Recommended Exclusions

Based on directory scan (no >1MB source files found outside `.venv/`, but the following consume space and/or would pollute indexing):

```
# Virtual environment
telegram-qbt/.venv/

# Git internals
.git/

# Cache and bytecode
__pycache__/        # 153 dirs found in tree
*.pyc
.ruff_cache/        # 16K
.mypy_cache/
.pytest_cache/
*.egg-info/

# Database files (runtime state)
*.db                # patchy_bot.db
*.sqlite*           # state.sqlite3, state.sqlite3-wal, state.sqlite3-shm

# Logs
*.log               # .playwright-mcp/console-*.log

# IDE
.vscode/
.idea/

# Playwright artifacts
.playwright-mcp/

# Obsidian plugins (huge)
Patchy Ops/.obsidian/plugins/

# Transient event buffers
.claude/memory/.event-buffer-*.jsonl

# Temp
.DS_Store
*.tmp
```

Key findings:
- `.git/` = **42 MB**, `telegram-qbt/` = **225 MB** (almost entirely `.venv/`)
- 4 SQLite files in `telegram-qbt/` (incl. WAL/SHM sidecars)
- 153 `__pycache__` directories
- No `.claudeignore` means all of this is candidates for scanning

---

## 8. Memory Files

Directory: `/home/karson/Patchy_Bot/.claude/memory/`

### 8.1 Per-File Contents

| File | Lines | ~Tokens | Status | Notes |
|---|---|---|---|---|
| MEMORY.md | 63 | ~555 | Current (2026-04-07) | Index file; points to the four category files. No contradictions. |
| patterns.md | 136 | ~1,717 | Current (2026-04-07) | 17 patterns/anti-patterns: HTML escaping, TOCTOU races, fuzzy matching, transient errors, text UX, path safety, EMA init, MoE scoring, subagent delegation, parity rule, no-git rule, no ⬜, restart on change, model hardcoding, no plan files, qBT binding, network topology. All dated 2026-04-05 to 2026-04-07. Aligned with CLAUDE.md. |
| bugs.md | 114 | ~1,255 | Current (2026-04-07) | 17 bug fixes, all from a single 2026-04-07 debugging session. Concrete verification steps. No outdated entries. |
| decisions.md | 65 | ~761 | Current (2026-04-06..07) | 6 architectural decisions: CAM/TS/SCR scoring, malware gate, season nav, no-git rule, qBT interface binding, Plex autoEmptyTrash. Aligned with invariants. |
| **sessions.md** | — | — | **DELETED** (git shows ` D .claude/memory/sessions.md`) | Referenced by MEMORY.md index and `session-finalizer.sh`. By CLAUDE.md rule this is OK (sessions are append-only and optional). |

**Event buffer archives** (transient, 5 files kept per rotation): `.event-buffer-20260407-221604.jsonl` (3.7 KB), `-222508.jsonl` (4.9 KB), `-223333.jsonl` (836 B), `-224030.jsonl` (1.1 KB), `-20260408-231750.jsonl` (5.4 KB).

### 8.2 Memory Assessment

- **No contradictions** with CLAUDE.md rules.
- **No duplication** with the auto-memory store at `~/.claude/projects/-home-karson-Patchy-Bot/memory/` (they're intentionally separate — legacy narrative log vs. canonical auto-memory).
- **`sessions.md` is staged-deleted** — confirm this is intentional. The finalizer hook will be a silent no-op without it.
- **Timestamps are all from 2026-04-05 → 2026-04-08** — the legacy log is essentially frozen. The auto-memory store is the live one.
- All entries are concrete and action-oriented.

---

## 9. Project Structure

### 9.1 Directory Overview

```
225M   telegram-qbt/          (mostly .venv/)
42M    .git/
2.5M   Patchy Ops/            (Obsidian vault)
996K   skills/                (5 top-level + 43 mirrored global)
508K   .claude/               (agents, hooks, memory, commands)
236K   .taskmaster/
148K   docs/
120K   .claude-plugin/        (10 plugin skills + plugin.json)
36K    Patchy/
16K    .vscode/  .ruff_cache/  .remember/
12K    .playwright-mcp/
8.0K   scripts/
```

### 9.2 File Metrics

| Metric | Value |
|---|---|
| `bot.py` line count | **5,543** (CLAUDE.md child says "~4,752" — stale) |
| Total Python files (excl .git/.venv/.ruff_cache) | **71** |
| Total test files (`test_*.py`) | **31** (CLAUDE.md child says "760 tests across 23 files" — stale count) |
| Handlers dir size | 2.3 MB total under `telegram-qbt/patchy_bot/` |

**Top 5 largest Python files:**
1. `bot.py` — 5,543 lines
2. `tests/test_parsing.py` — 4,593 lines
3. `handlers/schedule.py` — 3,546 lines
4. `handlers/remove.py` — 2,683 lines
5. `handlers/download.py` — 2,620 lines

**Handlers** (`telegram-qbt/patchy_bot/handlers/`): `_shared.py` (7.6 K), `base.py` (1.1 K), `chat.py` (8.3 K), `commands.py` (44 K), `download.py` (105 K), `full_series.py` (25 K), `remove.py` (109 K), `schedule.py` (145 K), `search.py` (24 K).

**UI** (`telegram-qbt/patchy_bot/ui/`): `flow.py` (720 B), `keyboards.py` (16 K), `rendering.py` (12 K), `text.py` (28 K).

**Clients** (`telegram-qbt/patchy_bot/clients/`): `llm.py` (3.9 K), `plex.py` (20 K), `qbittorrent.py` (11 K), `tv_metadata.py` (14 K).

### 9.3 Large Files / Token Sinks

- **`bot.py` (5,543 lines) is the #1 project token sink** — every exploration that pulls it in costs ~70–90K tokens raw. Splitting this monolith would be the highest-leverage codebase optimization.
- **`handlers/schedule.py` (3,546 lines)**, **`handlers/remove.py` (2,683)**, **`handlers/download.py` (2,620)** are the other three token-heavy modules.
- **`tests/test_parsing.py` (4,593 lines)** — largest test file; should rarely be loaded whole.
- No >1 MB source files found outside `.venv/`.

---

## 10. Custom Commands

### 10.1 Command Inventory

`/home/karson/Patchy_Bot/.claude/commands/tm/` — **46 stock Task Master command files**, unmodified from upstream. Full list:

```
add-dependency, add-subtask, add-task, analyze-complexity, analyze-project,
auto-implement-tasks, command-pipeline, complexity-report, convert-task-to-subtask,
expand-all-tasks, expand-task, fix-dependencies, help, init-project, init-project-quick,
install-taskmaster, learn, list-tasks-by-status, list-tasks, list-tasks-with-subtasks,
next-task, parse-prd, parse-prd-with-research, project-status, quick-install-taskmaster,
remove-all-subtasks, remove-dependency, remove-subtask, remove-subtasks, remove-task,
setup-models, show-task, smart-workflow, sync-readme, tm-main, to-cancelled, to-deferred,
to-done, to-in-progress, to-pending, to-review, update-single-task, update-task,
update-tasks-from-id, validate-dependencies, view-models
```

No project-specific custom commands found. No customization of the stock commands. **Currently 0 tasks defined in tasks.json**, so these 46 commands are unused.

---

## 11. Environment

### 11.1 Tool Versions

| Tool | Version |
|---|---|
| `claude --version` | 2.1.104 (Claude Code) |
| `python3 --version` | Python 3.12.3 |
| `node --version` | v22.22.1 |
| `ccusage` | **NOT INSTALLED** |
| `ecc-agentshield` | 1.5.0 ✓ |
| `localsend` | **NOT INSTALLED** |

### 11.2 Relevant Configuration

- **No root `pyproject.toml`** — only `telegram-qbt/pyproject.toml` exists. It has `[tool.ruff]` and `[tool.mypy]` sections.
- **`.env.example`** config keys (names only):
  `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `XAI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `AZURE_OPENAI_API_KEY`, `OLLAMA_API_KEY`, `GITHUB_API_KEY`
  (11 LLM provider keys — `.env.example` looks like the stock task-master template, not Patchy Bot's actual runtime env. Patchy's runtime uses `TELEGRAM_BOT_TOKEN`, `QB_*`, `PLEX_*`, etc. Discrepancy.)

---

## 12. Task Master

### 12.1 Configuration

**`.taskmaster/config.json`:**
```json
{
  "models": {
    "main":     { "provider":"claude-code", "modelId":"sonnet", "maxTokens":64000, "temperature":0.2 },
    "research": { "provider":"claude-code", "modelId":"sonnet", "maxTokens":64000, "temperature":0.1 },
    "fallback": { "provider":"claude-code", "modelId":"sonnet", "maxTokens":64000, "temperature":0.2 }
  },
  "global": { "projectName":"Patchy Bot", "defaultNumTasks":10, "defaultSubtasks":5, ... },
  "grokCli": { "timeout":120000, "defaultModel":"grok-4-latest" }
}
```

**`.taskmaster/state.json`:**
```json
{
  "currentTag": "master",
  "lastSwitched": "2026-04-04T23:26:41.178Z",
  "branchTagMapping": {},
  "migrationNoticeShown": true
}
```

All three TM roles (main/research/fallback) use `sonnet` — but the project's `settings.json` default is `claude-opus-4-6`. Diverges.

### 12.2 Task Status

**0 tasks** currently defined in `.taskmaster/tasks/tasks.json`. There are individual `task_001.md` through `task_013.md` files in the `tasks/` dir (likely orphaned from earlier TM runs), but the live `tasks.json` has no tasks. Task Master is effectively dormant in this project.

---

## Executive Summary

**Inventory totals**

- **Subagents**: 26 in `.claude/agents/`
- **Skills**: 58 directories total (5 top-level project, 10 plugin, 43 mirrored global); 57 usable (patchy-bot empty)
- **MCP servers**: 1 in `~/.mcp.json` (claude-flow, ~300 tools) + ~7 plugin-registered (context7, playwright, exa, filesystem, obsidian, task-master, tavily)
- **Hooks**: 7 command-type hooks (SessionStart, PreToolUse-Bash, PostToolUse×2, Stop×2, PermissionRequest)
- **Custom commands**: 46 stock Task Master commands, zero customization
- **CLAUDE.md files loaded per session**: 5 (~9,720 tokens combined)

**Biggest token sinks on startup/load**

1. `~/CLAUDE.md` RuFlo V3 global file — ~1,100 tokens, almost entirely irrelevant to this Python project
2. `.taskmaster/CLAUDE.md` stock guide — ~4,500 tokens, task-master integration that's dormant (0 tasks)
3. `telegram-qbt/CLAUDE.md` — ~2,700 tokens (the *useful* project playbook, but with stale counts)
4. `claude-flow` MCP server — schemas for ~300 tools with ~0 project fit
5. **`bot.py` (5,543 lines)** — the source-code token sink; any exploration that touches it is expensive
6. **`skills/global/` mirror** — 43 duplicate skill files in the repo
7. 3 redundant web-search providers (WebFetch/WebSearch + exa + tavily)

**Missing configurations**

- **No `.claudeignore`** — `.venv/`, `.git/`, `__pycache__/` (153 dirs), `*.db`/`*.sqlite*`, `.playwright-mcp/`, `Patchy Ops/.obsidian/plugins/` are all candidates
- **No `patchy-bot` skill** — directory exists but is empty, yet CLAUDE.md requires its use
- **No compaction / context-hygiene instructions** in any CLAUDE.md
- **No project-level `.mcp.json`** to override global registrations
- **No web-research policy** despite 35+ whitelisted domains in `settings.local.json`

**Outdated / contradictory rules**

- Global `~/CLAUDE.md` is a RuFlo V3 swarm manifesto that contradicts project practice (npm vs Python, swarm vs PTB bot, `/src` layout vs `telegram-qbt/patchy_bot/`)
- Project default model is `claude-opus-4-6`, but telegram-qbt child says "Sonnet default", and Task Master config says "sonnet" everywhere
- telegram-qbt child says "25 agents" (actual **26**), `bot.py ~4,752` (actual **5,543**), "760 tests across 23 files" (actual **31** files)
- `skills/global/` mirror directly violates the project CLAUDE.md rule *"do not restore a mirrored global skill library to this repo"*
- `sessions.md` is staged-deleted but still referenced by `session-finalizer.sh` and `MEMORY.md`

**Subagents missing model/effort frontmatter**

- 13 agents missing `model:` entirely (test, database, config-infra, ui, performance-opt, movie-tracking, monitoring-metrics, search-download, vault, torrent-abstraction, plex, media-library-abstraction, and remove has model but no tools)
- 22 agents missing `effort:`
- 13 agents missing `tools:` restriction
- 9 agents missing `memory:` where they should have `memory: project`
- 2 agents (audit-correctness, audit-performance) use non-standard frontmatter (no `name:`, use `permissionMode`/`maxTurns`)
- Ownership overlap: schedule-agent vs. movie-tracking-agent on `msch:` callbacks; search-download-agent vs. ui-agent on 7 callback prefixes

**MCP servers possibly unused / misconfigured**

- **claude-flow** (the only entry in `~/.mcp.json`) exposes ~300 tools; project uses none of them. Highest-impact removal candidate.
- **task-master** MCP is registered but project has 0 tasks.
- **exa + tavily + WebFetch/WebSearch** = 3 redundant web-search providers.
- **filesystem** MCP duplicates built-in Read/Write/Glob/Grep.

**Security concerns**

- `defaultMode: bypassPermissions` + `skipDangerousModePermissionPrompt: true` + `auto-approve.sh` PermissionRequest hook = **zero permission gates**. Only guard is `pre-bash-guard.sh` (blocks `rm -rf` on repo paths and `.env` reads via bash).
- `Read(./.env)` deny pattern uses relative paths; absolute-path reads could bypass.
- Global `settings.json` allows `Bash`, `Write`, `Edit`, `Agent` with no restrictions and an empty deny list.
- `semgrep` plugin is disabled despite being valuable for a security-critical bot.
- `stop-audit-trigger.sh` hardcodes `cd ~/Patchy_Bot/telegram-qbt` — fragile.

**Top 5 highest-impact optimization opportunities**

1. **Trim the CLAUDE.md stack.** Drop the RuFlo V3 content from `~/CLAUDE.md` (not applicable to this project) and delete the stock `.taskmaster/CLAUDE.md` (dormant feature). Potential savings: ~5,600 tokens on every session.
2. **Remove `skills/global/` mirror.** 43 duplicate skill files in the repo directly violating an explicit CLAUDE.md rule. Also delete the 4 top-level duplicates (assumptions-audit, diff-review, reuse-check, scope-guard) that are identical to global — or customize them for Patchy Bot. Populate the empty `skills/patchy-bot/` with the architecture map CLAUDE.md references.
3. **Create a `.claudeignore`.** Exclude `.venv/`, `__pycache__/`, `*.db`/`*.sqlite*`, `.ruff_cache/`, `.playwright-mcp/`, `Patchy Ops/.obsidian/plugins/`, event-buffer JSONL files.
4. **Fix subagent frontmatter.** Add `model`, `effort`, `tools`, `memory: project` to the 13 incomplete agents. Consolidate the two non-standard audit agents. Resolve the schedule-agent vs. movie-tracking-agent and search-download-agent vs. ui-agent ownership overlaps.
5. **Purge unused MCP servers.** Remove `claude-flow` from `~/.mcp.json` (saves the largest tool-schema load). Evaluate disabling `task-master`, one of `exa`/`tavily`, and `filesystem` — this alone recovers substantial tool-schema budget per session and keeps Claude's tool search sharper.

---

*End of audit report. All findings are read-only; no files were modified.*
