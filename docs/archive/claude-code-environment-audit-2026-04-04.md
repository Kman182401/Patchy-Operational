# Claude Code Environment Audit

**Generated:** 2026-04-04 19:16 EDT
**Purpose:** Provide comprehensive environment data to update the "prompt-engineer" skill in claude.ai with accurate Claude Code configuration details.
**Claude Code Version:** 2.1.92
**System:** Ubuntu 24.04.4 LTS (Noble Numbat), Linux 6.17.0-19-generic, x86_64

---

## 1. Claude Code Version & Runtime

### Claude Code
```
2.1.92 (Claude Code)
```

### Install Path
Claude is wrapped in a zsh function at `~/.zshrc`:
```bash
claude () {
    local claude_bin="/home/karson/.local/bin/claude"
    local patchy_root="/home/karson/Patchy_Bot"
    if [[ "$PWD" == "$patchy_root" || "$PWD" == "$patchy_root/"* ]]; then
        command "$claude_bin" --dangerously-skip-permissions --channels plugin:telegram@claude-plugins-official "$@"
    else
        command "$claude_bin" "$@"
    fi
}
```
Binary: `/home/karson/.local/bin/claude`
Exec path: `/home/karson/.local/share/claude/versions/2.1.92`

### Node.js & npm
```
Node: v22.22.1
npm: 11.12.1
```

### OS & Shell
```
$ uname -a
Linux home-pc 6.17.0-19-generic #19~24.04.2-Ubuntu SMP PREEMPT_DYNAMIC Fri Mar  6 23:08:46 UTC 2 x86_64 x86_64 x86_64 GNU/Linux

$ echo $SHELL
/usr/bin/zsh

PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
VERSION_CODENAME=noble
```

### Git
```
git version 2.43.0
```

### Environment Variables
```
CLAUDE_CODE_ENTRYPOINT=cli
CLAUDECODE=1
CLAUDE_CODE_EXECPATH=/home/karson/.local/share/claude/versions/2.1.92
```
No ANTHROPIC_API_KEY, PERPLEXITY_API_KEY, or MODEL variables found in env (keys managed via Claude Code auth, not env vars).

### Shell RC Claude-Related Entries (~/.zshrc)
```bash
# claude-update function for updating Claude Code
function claude-update { "$HOME/bin/claude-update" "$@"; }

# Run Claude with the Telegram channel by default inside Patchy_Bot.
claude() {
  local claude_bin="/home/karson/.local/bin/claude"
    command "$claude_bin" --dangerously-skip-permissions --channels plugin:telegram@claude-plugins-official "$@"
    command "$claude_bin" "$@"
}

alias ssh-claude='ssh claude@192.168.50.9'

# Claude Code deferred MCP loading (added by Taskmaster)
```

### Claude Code Help Output
```
Usage: claude [options] [command] [prompt]

Arguments:
  prompt                                            Your prompt

Options:
  --add-dir <directories...>                        Additional directories to allow tool access to
  --agent <agent>                                   Agent for the current session
  --agents <json>                                   JSON object defining custom agents
  --allow-dangerously-skip-permissions              Enable bypassing all permission checks as an option
  --allowedTools, --allowed-tools <tools...>        Comma or space-separated list of tool names to allow
  --append-system-prompt <prompt>                   Append a system prompt to the default system prompt
  --bare                                            Minimal mode: skip hooks, LSP, plugin sync, etc.
  --betas <betas...>                                Beta headers to include in API requests
  --brief                                           Enable SendUserMessage tool for agent-to-user communication
  --chrome                                          Enable Claude in Chrome integration
  -c, --continue                                    Continue the most recent conversation
  --dangerously-skip-permissions                    Bypass all permission checks
  -d, --debug [filter]                              Enable debug mode with optional category filtering
  --debug-file <path>                               Write debug logs to a specific file path
  --disable-slash-commands                          Disable all skills
  --disallowedTools, --disallowed-tools <tools...>  Comma or space-separated list of tool names to deny
  --effort <level>                                  Effort level (low, medium, high, max)
  --fallback-model <model>                          Enable automatic fallback to specified model
  --file <specs...>                                 File resources to download at startup
  --fork-session                                    Create a new session ID instead of reusing original
  --from-pr [value]                                 Resume a session linked to a PR
  -h, --help                                        Display help for command
  --ide                                             Automatically connect to IDE on startup
  --include-hook-events                             Include all hook lifecycle events in output stream
  --include-partial-messages                        Include partial message chunks as they arrive
  --input-format <format>                           Input format: "text" or "stream-json"
  --json-schema <schema>                            JSON Schema for structured output validation
  --max-budget-usd <amount>                         Maximum dollar amount for API calls
  --mcp-config <configs...>                         Load MCP servers from JSON files or strings
  --mcp-debug                                       [DEPRECATED] Enable MCP debug mode
  --model <model>                                   Model for the current session
  -n, --name <name>                                 Set a display name for this session
  --no-chrome                                       Disable Claude in Chrome integration
  --no-session-persistence                          Disable session persistence
  --output-format <format>                          Output format: "text", "json", or "stream-json"
  --permission-mode <mode>                          Permission mode (acceptEdits, auto, bypassPermissions, default, dontAsk, plan)
  --plugin-dir <path>                               Load plugins from a directory for this session only
  -p, --print                                       Print response and exit (useful for pipes)
  --remote-control-session-name-prefix <prefix>     Prefix for auto-generated Remote Control session names
  --replay-user-messages                            Re-emit user messages from stdin back on stdout
  -r, --resume [value]                              Resume a conversation by session ID
  --session-id <uuid>                               Use a specific session ID
  --setting-sources <sources>                       Comma-separated list of setting sources to load
  --settings <file-or-json>                         Path to a settings JSON file or a JSON string
  --strict-mcp-config                               Only use MCP servers from --mcp-config
  --system-prompt <prompt>                          System prompt to use for the session
  --tmux                                            Create a tmux session for the worktree
  --tools <tools...>                                Specify the list of available tools from the built-in set
  --verbose                                         Override verbose mode setting from config
  -v, --version                                     Output the version number
  -w, --worktree [name]                             Create a new git worktree for this session

Commands:
  agents [options]                                  List configured agents
  auth                                              Manage authentication
  auto-mode                                         Inspect auto mode classifier configuration
  doctor                                            Check the health of your Claude Code auto-updater
  install [options] [target]                        Install Claude Code native build
  mcp                                               Configure and manage MCP servers
  plugin|plugins                                    Manage Claude Code plugins
  setup-token                                       Set up a long-lived authentication token
  update|upgrade                                    Check for updates and install if available
```

---

## 2. CLAUDE.md Files

### File: /home/karson/.claude/CLAUDE.md (User-Level)
**Size:** 594 bytes | **Modified:** 2026-04-02 10:05

```markdown
<!-- expert-analysis:start -->
## Personal analysis preferences

- When I use analysis-oriented workflows, investigate before proposing implementation.
- Separate verified facts, inferences, unknowns, and recommendations.
- For recent, version-sensitive, or security-sensitive claims, verify with web tools whenever available.
- Prefer current official documentation and other primary sources.
- Explain clearly in simple language.
- Use concrete examples where helpful.
- Use prioritized step-by-step plans.
- Make before/after differences explicit when relevant.
<!-- expert-analysis:end -->
```

### File: /home/karson/CLAUDE.md (Home Directory / Global Project)
**Size:** ~8.5KB | **Modified:** Current session

```markdown
## Core Rules

1. **Do exactly what is asked.** Nothing more, nothing less. Ask if unclear.
2. **Challenge the direction.** If there's a faster/simpler way, propose it.
3. **Look before you create.** Read existing files before making new ones.
4. **Test before you respond.** Run relevant tests after code changes. Never say "done" untested.
5. **End each run with a concrete improvement.** One actionable upgrade per task.
6. **Prompt the next step.** State the next logical action unless the task is fully complete.
7. **Update the process after major corrections.** Capture meaningful fixes that prevent future issues.

---

## How to Respond

Explain like you're talking to a 15-year-old with no coding background.

Every response includes:
- **What I just did** — plain English, no jargon
- **What you need to do** — step by step
- **Why** — one sentence
- **Next step** — one clear action
- **Errors** — if something went wrong, explain simply and say how to fix it

For tools, platforms, or environments unfamiliar to beginners: walk through exactly where to find what's needed, describe what each setting does in one sentence, explain SQL/commands before running them. Be concise.

---

## How to Write Code

- Simple, readable code — clarity over cleverness
- One change at a time
- Don't change unrelated code
- Don't over-engineer
- Explain big structural changes before making them

---

## Secrets & Safety

- Never put API keys or passwords directly in code
- Never commit `.env` to GitHub
- Ask before deleting or renaming important files

---

## Before Acting

Before touching a file:
- Read the relevant files first
- Check adjacent tests, configs, and docs
- Run `git diff` / `git status` if relevant

While editing:
- Preserve unrelated changes
- Prefer minimal, targeted diffs
- Fix root causes, not symptoms
- Match existing code style
- If behavior changes, update tests/docs/configs

For APIs, auth, schemas, databases, or CI/CD:
- Identify blast radius first
- Identify rollback path
- Verify against current docs

---

## Truth Protocol

**Ground rule:** Never invent facts, file contents, function names, command outputs, URLs, error messages, API behavior, or any verifiable detail. If you didn't read it, run it, or retrieve it — you don't know it.

**Confidence tiers:**
| Tier | Meaning | Action |
|------|---------|--------|
| Verified | Read/ran/retrieved this session | State as fact |
| High confidence | Core behavior unlikely to change | State it, note if version-sensitive |
| Uncertain | Recall but haven't verified | Say "let me verify" then verify |
| Unknown | Don't have the info | Say "I don't know" and look it up |

**Never generate:** unread file contents, unrun command outputs, unchecked signatures/flags/versions, unverified URLs, fabricated stack traces, guesses about code behavior.

---

## Quality Gate

Before every response:
1. Did I read every file I'm referencing?
2. Did I run every command I'm reporting on?
3. Am I stating anything unverified?
4. Am I confusing expectation with confirmation?

---

## Verification

Before marking any task as done:
- Run the relevant script/command and confirm success
- Check stdout/stderr for errors
- Trace the full execution path end-to-end
- Verify existing behavior wasn't broken

---

## Recovery Protocol

When something fails:
- Capture the exact error, output, and context
- Research the failure before changing anything
- Try at least one alternate approach
- Report: what failed, what you checked, why the new approach is better

---

## Planning

For multi-step, multi-file, new feature, or refactor work — maintain an explicit plan with: objective, scope, milestones, acceptance criteria, known risks.

---

## Agent & Skill Usage (Enforced via Hooks)

- **Every prompt**: Evaluate available agents and skills for relevance before implementing
- **After code edits**: Security-sensitive files trigger security-reviewer agent
- **Before completing**: Quality verification runs automatically (tests, security, analysis)
- **Non-trivial tasks**: Use researcher → plan-builder → implement → test-runner → security-reviewer → analyze

Available agents: security-reviewer, test-runner, debugger, researcher, plan-builder, linter
Available skills: analyze, plan-builder, plan-implementation, researcher, security-reviewer, test-runner

Context tools: Use context7 MCP when libraries/frameworks are involved. Use exa MCP for advanced web search.

---

## Available Tools — Use Automatically When Beneficial

### Documentation & Research
- **context7** (MCP server) — Use for any library, framework, SDK, or API
- **microsoft-docs** — Use for any Microsoft, Azure, .NET, or Windows technology

### Code Quality & Security
- **semgrep** — Scans files after edits when `SEMGREP_APP_TOKEN` is set
- **security-guidance** — Reference when writing auth, crypto, input handling, HTTP headers
- **code-simplifier** — Use when code looks overly complex or after a refactor

### Browser & Frontend
- **chrome-devtools** (MCP server) — Use for debugging web UI
- **playwright** (MCP server) — Use for browser automation, E2E testing

### AI & Agent Development
- **agent-sdk-dev** — Use when building agents with the Anthropic Agent SDK
- **atomic-agents** — Reference when designing modular agent pipelines

### Productivity & Workflow Intelligence
- **superpowers** — Provides systematic-debugging, verification-before-completion, writing-plans skills

### Developer Workflow
- **hookify** — Use for automated behavior on file edits, commits, or Claude Code events
- **plugin-dev / mcp-server-dev** — Use when building plugins or MCP servers
- **claude-md-management** — Use after significant corrections to update CLAUDE.md

### Language Servers (LSP)
All LSP plugins activate automatically for their file types.

## Task Master AI Instructions
@./.taskmaster/CLAUDE.md
```

### File: /home/karson/Patchy_Bot/CLAUDE.md
**Size:** ~5KB | **Modified:** Current

Patchy Bot project intelligence with system overview, package map, domain boundaries, coding conventions, testing patterns, safety rules, service operations, phase 2 refactor targets, and subagent routing for 9 project-specific agents.

### File: /home/karson/cracking_station/CLAUDE.md
**Size:** ~700 bytes | Authorized security research/CTF tool, mixed C/Bash/Python.

### File: /home/karson/File-Window/CLAUDE.md
**Size:** ~700 bytes | SPY vertical spread trading system, Python 3.12, IBKR integration.

### File: /home/karson/FuzzyAI/CLAUDE.md
**Size:** ~700 bytes | LLM fuzzing and jailbreak testing tool, Python 3.10+, 20+ providers.

### File: /home/karson/openclaw-kraken-trading-system/CLAUDE.md
**Size:** ~700 bytes | Kraken Spot trading scaffold, dry-run-first design, Python 3.12.

### File: /home/karson/Patchy_Bot_backup/CLAUDE.md
**Size:** ~5KB | Mirror of Patchy_Bot/CLAUDE.md (backup copy).

### File: /home/karson/Patchy_Bot/telegram-qbt/CLAUDE.md
**Size:** ~1.5KB | Telegram Bot + Mini App UX rules.

### File: /home/karson/.taskmaster/CLAUDE.md
**Size:** ~14KB | Task Master AI agent integration guide (full workflow commands, MCP integration, structure).

---

## 3. Settings & Configuration

### File: /home/karson/.claude/settings.json (User Settings)
**Modified:** 2026-04-04 19:07

```json
{
  "permissions": {
    "allow": [
      "Agent(*)",
      "Bash",
      "Edit",
      "Glob",
      "Grep",
      "MultiEdit",
      "Read",
      "TodoRead",
      "TodoWrite",
      "WebFetch",
      "WebSearch",
      "Write",
      "mcp__*"
    ],
    "deny": [],
    "defaultMode": "bypassPermissions"
  },
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/mandatory-activation.sh"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/allow-all.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/pre-bash-safety.sh"
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/pre-commit-gate.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/post-edit-lint.sh"
          }
        ]
      },
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/post-edit-security.sh"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/session-start.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /home/karson/.claude/hooks/pre-exit.sh"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Verify the following before allowing completion:\n\n1. If any .py, .sh, .bash, or config files were written or edited, check if a security agent was invoked during this session. If not, flag this.\n\n2. If code was written, check if tests exist for the changed code. Run a quick test if a test suite is available.\n\n3. If the task was non-trivial, check if the analyze skill was used.\n\nIf all checks pass, respond with 'ok'. If any check fails, respond with a reason explaining what was missed.\n\n$ARGUMENTS",
            "timeout": 120
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/auto-approve.sh",
            "statusMessage": "Auto-approving..."
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "bash /home/karson/.claude/statusline-command.sh"
  },
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "context7@claude-plugins-official": true,
    "code-review@claude-plugins-official": true,
    "code-simplifier@claude-plugins-official": true,
    "feature-dev@claude-plugins-official": true,
    "playwright@claude-plugins-official": true,
    "typescript-lsp@claude-plugins-official": true,
    "claude-md-management@claude-plugins-official": true,
    "security-guidance@claude-plugins-official": true,
    "claude-code-setup@claude-plugins-official": true,
    "pyright-lsp@claude-plugins-official": true,
    "agent-sdk-dev@claude-plugins-official": true,
    "plugin-dev@claude-plugins-official": true,
    "hookify@claude-plugins-official": true,
    "rust-analyzer-lsp@claude-plugins-official": true,
    "chrome-devtools-mcp@claude-plugins-official": true,
    "semgrep@claude-plugins-official": true,
    "microsoft-docs@claude-plugins-official": true,
    "atomic-agents@claude-plugins-official": true,
    "mcp-server-dev@claude-plugins-official": true,
    "pai@jeffh-claude-plugins": true,
    "frontend-design@claude-plugins-official": false,
    "skill-creator@claude-plugins-official": false,
    "telegram@claude-plugins-official": false,
    "gopls-lsp@claude-plugins-official": false,
    "csharp-lsp@claude-plugins-official": false,
    "jdtls-lsp@claude-plugins-official": false,
    "php-lsp@claude-plugins-official": false,
    "huggingface-skills@claude-plugins-official": false,
    "clangd-lsp@claude-plugins-official": false,
    "swift-lsp@claude-plugins-official": false,
    "firecrawl@claude-plugins-official": false,
    "kotlin-lsp@claude-plugins-official": false,
    "lua-lsp@claude-plugins-official": false,
    "ruby-lsp@claude-plugins-official": false,
    "remember@claude-plugins-official": false,
    "goodmem@claude-plugins-official": false,
    "optibot@claude-plugins-official": false,
    "ai-plugins@claude-plugins-official": false,
    "elixir-ls-lsp@claude-plugins-official": false,
    "ui5@claude-plugins-official": false,
    "ui5-typescript-conversion@claude-plugins-official": false,
    "figma@claude-plugins-official": false
  },
  "extraKnownMarketplaces": {
    "jeffh-claude-plugins": {
      "source": {
        "source": "github",
        "repo": "jeffh/claude-plugins"
      }
    }
  },
  "effortLevel": "high",
  "advisorModel": "claude-opus-4-6",
  "skipDangerousModePermissionPrompt": true
}
```

### File: /home/karson/.claude/settings.local.json (Local Override)
**Modified:** 2026-04-04 15:13

```json
{
  "permissions": {
    "defaultMode": "bypassPermissions",
    "allow": [
      "Bash(*)",
      "Read(*)",
      "Write(*)",
      "Edit(*)",
      "Glob(*)",
      "Grep(*)",
      "WebFetch(*)",
      "WebSearch(*)",
      "Agent(*)",
      "Skill(*)",
      "NotebookEdit(*)",
      "LSP(*)",
      "mcp__*",
      "mcp__tavily__*",
      "mcp__chrome-devtools__*",
      "mcp__playwright__*",
      "mcp__context7__*",
      "mcp__exa__*",
      "mcp__plugin_microsoft-docs_microsoft-learn__*"
    ]
  }
}
```

### File: /home/karson/Patchy_Bot/.claude/settings.json
```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(npm run lint:*)",
      "Bash(npm run test:*)",
      "Bash(npm run storybook:*)",
      "Bash(npx playwright test:*)",
      "Bash(git diff:*)",
      "Bash(git status:*)"
    ],
    "ask": ["Bash(git push:*)", "Bash(npm publish:*)", "WebFetch"],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(./config/credentials/**)"
    ]
  },
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["docker"]
  },
  "enabledMcpjsonServers": ["figma"],
  "outputStyle": "Explanatory",
  "respectGitignore": true,
  "alwaysThinkingEnabled": true,
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -20"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest tests/ -q --tb=short 2>&1 | tail -20"
          }
        ]
      }
    ]
  }
}
```

### File: /home/karson/Patchy_Bot/.claude/settings.local.json
```json
{
  "permissions": {
    "allow": [
      "WebFetch(domain:core.telegram.org)",
      "WebFetch(domain:github.com)",
      "WebFetch(domain:docs.telegram-mini-apps.com)",
      "WebFetch(domain:telegram.org)",
      "WebFetch(domain:docs.pydantic.dev)",
      "WebFetch(domain:support.plex.tv)",
      "WebFetch(domain:tailscale.com)",
      "WebFetch(domain:code.claude.com)",
      "WebFetch(domain:mcpmarket.com)",
      "Bash(systemctl cat:*)",
      "Bash(systemctl status:*)",
      "Bash(systemctl list-units:*)",
      "Bash(systemctl list-timers:*)",
      "Bash(crontab -l)",
      "Bash(sudo crontab:*)"
    ]
  }
}
```

### Keybindings: /home/karson/.claude/keybindings.json
```json
{
  "$schema": "https://www.schemastore.org/claude-code-keybindings.json",
  "$docs": "https://code.claude.com/docs/en/keybindings",
  "bindings": [
    {
      "context": "Chat",
      "bindings": {
        "alt+m": "chat:modelPicker",
        "alt+p": "chat:cycleMode"
      }
    }
  ]
}
```

---

## 4. Custom Skills

### Location: /home/karson/.claude/skills/ (12 skills)

#### 4.1 analyze
**Path:** `~/.claude/skills/analyze/SKILL.md`
**Supporting files:** `review-rubric.md`
```yaml
name: analyze
description: Deep post-completion review. Use PROACTIVELY immediately after code changes, fixes, refactors, installs, config edits, migrations, or automation work. Trigger before claiming any task is complete. Finds missed issues, patches them, and validates the final state.
argument-hint: "[optional focus]"
effort: high
```
Post-completion audit skill. Runs 7-step workflow: reconstruct task → gather evidence → audit deeply (functional, integration, config, edge cases, security, data integrity, performance, validation, cleanup) → patch fixable issues → validate → re-check second-order → report with verdict (Ready / Ready with noted limitations / Not fully validated).

#### 4.2 audit
**Path:** `~/.claude/skills/audit/SKILL.md`
```yaml
name: audit
description: Run a deep, professional, read-only audit of a repo, service, system, config set, bot, workflow, or prompt system and return a structured findings report directly in chat.
argument-hint: "[target to audit]"
context: fork
agent: Plan
effort: high
```
Read-only audit. Checks correctness, logic, architecture, security, reliability, performance, operability, maintainability, testing. Rankings: Critical/High/Medium/Low/Info. Output in chat only — never writes files.

#### 4.3 debugger
**Path:** `~/.claude/skills/debugger/SKILL.md`
```yaml
name: debugger
description: Debugging specialist. Follows reproduce-isolate-identify-fix-verify methodology.
context: fork
agent: general-purpose
allowed-tools: Read, Bash, Glob, Grep
```

#### 4.4 expert-analysis
**Path:** `~/.claude/skills/expert-analysis/SKILL.md`
```yaml
name: expert-analysis
description: Deep, evidence-first analysis with current web research and precise action plan.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch
```

#### 4.5 linter
**Path:** `~/.claude/skills/linter/SKILL.md`
```yaml
name: linter
description: Auto-lint and format specialist. Runs ruff (Python), shellcheck (Bash), and prettier (JS/HTML/CSS) on edited files.
context: fork
agent: general-purpose
allowed-tools: Read, Bash, Glob, Grep
```

#### 4.6 plan-builder
**Path:** `~/.claude/skills/plan-builder/SKILL.md`
**Supporting files:** `references/plan-output-template.md`, `references/plan-quality-bar.md`, `references/research-standards.md`
```yaml
name: plan-builder
description: Research-first implementation planner. Produces a durable ExecPlan-style spec. Do not use for direct execution from an already approved plan.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch, Agent
```

#### 4.7 plan-implementation
**Path:** `~/.claude/skills/plan-implementation/SKILL.md`
**Supporting files:** `references/execution-playbook.md`, `references/delegation-and-review.md`, `references/verification-gates.md`
```yaml
name: plan-implementation
description: Execute an already approved plan, report, analysis, or set of next steps from a prior planning process.
effort: high
```

#### 4.8 prompt-engineer
**Path:** `~/.claude/skills/prompt-engineer/SKILL.md`
**Supporting files:** `references/core_prompting.md`, `references/advanced_patterns.md`, `references/quality_improvement.md`
```yaml
name: prompt-engineer
description: Create, improve, or optimize prompts using best practices
```
Covers: clarity, system prompts, XML tags, chain of thought, multishot, prompt chaining, long context, extended thinking, hallucination reduction, consistency, jailbreak mitigation.

#### 4.9 researcher
**Path:** `~/.claude/skills/researcher/SKILL.md`
```yaml
name: researcher
description: Research specialist for gathering current information. Finds current best practices, library versions, security advisories.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch
```

#### 4.10 security-reviewer
**Path:** `~/.claude/skills/security-reviewer/SKILL.md`
```yaml
name: security-reviewer
description: Security-focused code reviewer. Uses semgrep, bandit, and manual pattern checks. Flags HIGH/CRITICAL issues as blocking.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash
```

#### 4.11 test-runner
**Path:** `~/.claude/skills/test-runner/SKILL.md`
```yaml
name: test-runner
description: Test execution specialist. Runs pytest, unittest, or bash test scripts and reports pass/fail summary.
context: fork
agent: general-purpose
allowed-tools: Read, Bash, Glob, Grep
```

#### 4.12 undo
**Path:** `~/.claude/skills/undo/SKILL.md`
**Supporting files:** `undo-checklist.md`
```yaml
name: undo
description: Fully undo the work Claude just completed in this session.
argument-hint: "[optional rollback instructions or scope]"
disable-model-invocation: true
effort: high
```

---

## 5. Custom Subagents

### Location: /home/karson/.claude/agents/ (12 agents)

| Agent | Model | Tools | Description |
|-------|-------|-------|-------------|
| python-pro | sonnet | Read, Write, Edit, Bash, Glob, Grep | Type-safe, production-ready Python code |
| fastapi-developer | sonnet | Read, Write, Edit, Bash, Glob, Grep | Modern async Python APIs with FastAPI |
| cli-developer | sonnet | Read, Write, Edit, Bash, Glob, Grep | CLI tools and terminal applications |
| docker-expert | sonnet | Read, Write, Edit, Bash, Glob, Grep | Docker containers and orchestration |
| quant-analyst | opus | Read, Write, Edit, Bash, Glob, Grep | Quantitative trading and financial models |
| security-engineer | opus | Read, Write, Edit, Bash, Glob, Grep | Infrastructure security and DevSecOps |
| security-auditor | opus | Read, Grep, Glob | Read-only security audits and compliance |
| error-detective | sonnet | Read, Write, Edit, Bash, Glob, Grep | Error diagnosis and root cause analysis |
| performance-engineer | sonnet | Read, Write, Edit, Bash, Glob, Grep | Performance bottleneck elimination |
| incident-responder | sonnet | Read, Write, Edit, Bash, Glob, Grep | Active breach and outage response |
| dependency-manager | haiku | Read, Write, Edit, Bash, Glob, Grep | Dependency audits and CVE scanning |
| penetration-tester | opus | Read, Grep, Glob, Bash | Authorized offensive security testing |

### Patchy Bot Project Agents (/home/karson/Patchy_Bot/.claude/agents/)
9 project-specific agents: schedule-agent, remove-agent, search-download-agent, plex-agent, config-infra-agent, database-agent, ui-agent, test-agent, security-agent.

---

## 6. Hooks Configuration

### Event: UserPromptSubmit
| Handler | Type | Script |
|---------|------|--------|
| mandatory-activation.sh | command | Outputs mandatory pre-task evaluation instructions. Forces Claude to evaluate agents/skills before implementing. Maps task types to specific agents. |

**Script content:**
```bash
#!/bin/bash
cat <<'EOF'
MANDATORY PRE-TASK EVALUATION:
Before implementing anything, you MUST follow this sequence:
1. EVALUATE SUBAGENTS: Match the task to installed agents in ~/.claude/agents/
2. EVALUATE SKILLS: Check available skills for relevance
3. ACTIVATE: For each relevant agent/skill, invoke it
4. ONLY THEN proceed with implementation.
CRITICAL: Activating agents/skills is NOT optional for non-trivial tasks.
EOF
```

### Event: PreToolUse (matcher: "")
| Handler | Type | Script |
|---------|------|--------|
| allow-all.sh | command | Returns `{"decision": "allow"}` to bypass all permission checks |

### Event: PreToolUse (matcher: "Bash")
| Handler | Type | Script |
|---------|------|--------|
| pre-bash-safety.sh | command | Blocks dangerous commands: rm -rf on system dirs, writes to block devices, mkfs, dd, chmod 777 on system dirs, fork bombs, iptables flush |
| pre-commit-gate.sh | command | Intercepts `git commit` and `git push`. Detects test framework (npm test, pytest, make test) and runs tests. Blocks commit if tests fail (exit 2). Skips for home dir repo. |

### Event: PostToolUse (matcher: "Write|Edit")
| Handler | Type | Script |
|---------|------|--------|
| post-edit-lint.sh | command | Auto-runs ruff check+format (Python), shellcheck (Bash), prettier (JS/HTML/CSS) on edited files |
| post-edit-security.sh | command | Runs semgrep scan (all files) and bandit (Python files) on edited files, reports findings |

### Event: SessionStart
| Handler | Type | Script |
|---------|------|--------|
| session-start.sh | command | Checks for semgrep, bandit, ruff, shellcheck, trivy installation and reports warnings |

### Event: Stop
| Handler | Type | Script |
|---------|------|--------|
| pre-exit.sh | command | Checks for uncommitted changes in CWD and warns |
| (Stop agent) | agent | Verifies: (1) security agent was invoked if .py/.sh/.bash/config files were edited, (2) tests exist and pass for changed code, (3) analyze skill was used for non-trivial tasks. Timeout: 120s |

### Event: PermissionRequest
| Handler | Type | Script |
|---------|------|--------|
| auto-approve.sh | command | Returns `{"hookSpecificOutput":{"hookEventName":"PermissionRequest","permissionDecision":"allow"}}` — zero prompts |

---

## 7. MCP Servers

### File: /home/karson/.mcp.json

| Server | Command | Notes |
|--------|---------|-------|
| playwright | node .../playwright-mcp-0.0.69/.../cli.js --headless | Browser automation |
| chrome-devtools | node .../chrome-devtools-mcp-0.20.3/.../chrome-devtools-mcp.js | Chrome debugging |
| context7 | node .../context7-mcp-2.1.6/.../index.js | Library docs lookup (has API key configured) |
| exa | URL-based: https://mcp.exa.ai/mcp | Advanced web search |

### MCP via Plugins (auto-configured)
- **task-master-ai** — Task Master MCP (available via slash commands)
- **tavily** — Web search/crawl/extract (tavily_search, tavily_crawl, tavily_extract, tavily_research, tavily_map, tavily_skill)
- **microsoft-learn** — Microsoft docs search, code sample search, docs fetch

---

## 8. Slash Commands

### Location: /home/karson/.claude/commands/tm/ (46 Task Master commands)

All slash commands are Task Master related (`/tm:*`):
add-dependency, add-subtask, add-task, analyze-complexity, analyze-project, auto-implement-tasks, command-pipeline, complexity-report, convert-task-to-subtask, expand-all-tasks, expand-task, fix-dependencies, help, init-project-quick, init-project, install-taskmaster, learn, list-tasks-by-status, list-tasks-with-subtasks, list-tasks, next-task, parse-prd-with-research, parse-prd, project-status, quick-install-taskmaster, remove-all-subtasks, remove-dependency, remove-subtask, remove-subtasks, remove-task, setup-models, show-task, smart-workflow, sync-readme, tm-main, to-cancelled, to-deferred, to-done, to-in-progress, to-pending, to-review, update-single-task, update-task, update-tasks-from-id, validate-dependencies, view-models

No custom user slash commands outside of Task Master.

---

## 9. Installed Plugins

### Enabled Plugins (21 active)
| Plugin | Source | Version |
|--------|--------|---------|
| superpowers | claude-plugins-official | 5.0.7 |
| context7 | claude-plugins-official | 01790af90f8b |
| code-review | claude-plugins-official | 01790af90f8b |
| code-simplifier | claude-plugins-official | 1.0.0 |
| feature-dev | claude-plugins-official | 01790af90f8b |
| playwright | claude-plugins-official | 01790af90f8b |
| typescript-lsp | claude-plugins-official | 1.0.0 |
| claude-md-management | claude-plugins-official | 1.0.0 |
| security-guidance | claude-plugins-official | 01790af90f8b |
| claude-code-setup | claude-plugins-official | 1.0.0 |
| pyright-lsp | claude-plugins-official | 1.0.0 |
| agent-sdk-dev | claude-plugins-official | 01790af90f8b |
| plugin-dev | claude-plugins-official | 01790af90f8b |
| hookify | claude-plugins-official | 01790af90f8b |
| rust-analyzer-lsp | claude-plugins-official | 1.0.0 |
| chrome-devtools-mcp | claude-plugins-official | latest |
| semgrep | claude-plugins-official | 0.5.1 |
| microsoft-docs | claude-plugins-official | 0.3.1 |
| atomic-agents | claude-plugins-official | a369239875ff |
| mcp-server-dev | claude-plugins-official | 01790af90f8b |
| pai | jeffh-claude-plugins | 2025-12-26 |

### Extra Marketplace
- **jeffh-claude-plugins** (GitHub: jeffh/claude-plugins)

### Disabled Plugins
frontend-design, skill-creator, telegram, gopls-lsp, csharp-lsp, jdtls-lsp, php-lsp, huggingface-skills, clangd-lsp, swift-lsp, firecrawl, kotlin-lsp, lua-lsp, ruby-lsp, remember, goodmem, optibot, ai-plugins, elixir-ls-lsp, ui5, ui5-typescript-conversion, figma

---

## 10. Memory & Context

### Home Project Memory: /home/karson/.claude/projects/-home-karson/memory/

#### MEMORY.md (Index)
```
- user_profile.md — Karson: solo dev, Python/Bash, security tools + trading systems, wants max automation
- feedback_claude_code_setup.md — Research and decide autonomously on tool/config choices, don't ask
- project_security_stack_upgrade.md — Status of 2026-03 security stack upgrade, eBPF FIM issue, completed/blocked tasks
- project_av_optimization.md — 2026-03-31 AV optimization: security.slice, idle orchestrator, single clamd, fixed wazuh syscheck
```

#### user_profile.md
```
type: user
Solo developer on Ubuntu 24.04.4 LTS. Primary languages: Python and Bash. Work spans security tools (FuzzyAI, cracking_station), trading systems (File-Window, openclaw-kraken-trading-system), sysadmin automation, and web frontend.
Prefers maximum automation: auto-lint, auto-scan, auto-test, block bad commits. Wants subagents to fire automatically. Values aggressive web search for best practices.
Git workflow: solo repos, commits straight to main. Effort preference: always maximum.
Explain things simply — like talking to a 15-year-old.
```

#### feedback_claude_code_setup.md
```
type: feedback
When researching tool/plugin options, do deep web research and make the best-fit decision autonomously rather than asking the user to choose.
Why: User explicitly said "use hyper deep expert level web research and analysis to identify the best current options."
```

### Patchy Bot Project Memory: /home/karson/.claude/projects/-home-karson-Patchy-Bot/memory/

#### MEMORY.md (Index)
```
- Subagent model preference — Never hardcode model in Agent tool calls; let global settings.json control it
- No empty checkbox emoji — Never use ⬜ in bot UI; selected = ✅ prefix, unselected = plain text
- Restart bot after changes — Always run sudo systemctl restart telegram-qbt-bot.service after any bot code change
- Movies/TV feature parity — Any change to Movie Search must also be applied to TV Search and vice versa
- Package structure — Edit patchy_bot/ package modules for runtime changes; qbt_telegram_bot.py is backward-compat shim
- No git for Patchy Bot — No git/commits/branches in Patchy_Bot; edit files directly and restart service
- No plan files — Never save plans to files; present all plans inline in chat only
- No prompt-type security hooks — Prompt PostToolUse hooks cause mid-process halts; use script hooks only
```

### Rules Directories
No `.claude/rules/` directories found.

---

## 11. Permission Mode & Model Configuration

| Setting | Value |
|---------|-------|
| Default permission mode | `bypassPermissions` |
| Effort level | `high` |
| Advisor model | `claude-opus-4-6` |
| Skip dangerous mode prompt | `true` |
| Current session model | Claude Opus 4.6 (1M context) |

### Permission Escalation Chain
1. `settings.local.json` — bypassPermissions + wildcard allow for all tools
2. `settings.json` — bypassPermissions + allow list for core tools
3. `PreToolUse` hook (allow-all.sh) — returns `{"decision": "allow"}` for everything
4. `PermissionRequest` hook (auto-approve.sh) — auto-allows protected directory writes

**Result:** Zero permission prompts in any context.

---

## 12. Available Built-in Features

### Available Plugin Skills (from session)
analyze, audit, debugger, expert-analysis, linter, plan-builder, plan-implementation, prompt-engineer, researcher, security-reviewer, test-runner, undo, update-config, keybindings-help, simplify, loop, schedule, claude-api, code-review:code-review, feature-dev:feature-dev, claude-md-management:revise-claude-md, agent-sdk-dev:new-sdk-app, plugin-dev:create-plugin, hookify:configure/help/hookify/list, semgrep-plugin:setup-semgrep-plugin, superpowers:* (brainstorming, writing-plans, executing-plans, finishing-a-development-branch, subagent-driven-development, dispatching-parallel-agents, systematic-debugging, verification-before-completion, receiving-code-review, requesting-code-review, test-driven-development, using-git-worktrees, writing-skills, using-superpowers), chrome-devtools-mcp:* (a11y-debugging, debug-optimize-lcp, troubleshooting, chrome-devtools), microsoft-docs:* (microsoft-docs, microsoft-code-reference, microsoft-skill-creator), mcp-server-dev:build-mcp-server/build-mcp-app/build-mcpb, pai:* (fabric, prompting, CORE, create-skill, research, story-explanation), plugin-dev:* (agent-development, plugin-settings, hook-development, skill-development, command-development, mcp-integration, plugin-structure), hookify:writing-rules, tm:* (46 taskmaster commands)

### Available Deferred Tools
AskUserQuestion, CronCreate, CronDelete, CronList, EnterPlanMode, EnterWorktree, ExitPlanMode, ExitWorktree, LSP, ListMcpResourcesTool, NotebookEdit, ReadMcpResourceTool, RemoteTrigger, TaskCreate, TaskGet, TaskList, TaskOutput, TaskStop, TaskUpdate, WebFetch, WebSearch, plus all MCP tools from: chrome-devtools, playwright, microsoft-learn, task-master, tavily

---

## 13. Git & Project Context

### Git Version
```
git version 2.43.0
```

### Git Hooks
Only sample hooks in `/home/karson/.git/hooks/` — no active custom git hooks. Claude Code hooks handle pre-commit gating via `pre-commit-gate.sh` (settings.json PreToolUse).

### .gitignore (Home Directory)
```
# Ignore everything by default - this repo exists only so Claude Code
# plan mode (git worktrees) works from the home directory.
*

# Track only this file and CLAUDE.md
!.gitignore
!CLAUDE.md
```

### Status Line Script
Custom Kali-style PS1 status line showing: user@host, CWD, context window %, model name, 5-hour usage %, weekly usage %, reset times.

---

## 14. Current Claude Code Feature Reference (April 2026)

### Hook Event Types (13 types)
| Event | When it fires | Input |
|-------|--------------|-------|
| `PreToolUse` | Before any tool executes | Tool name, input, session info |
| `PostToolUse` | After any tool completes | Tool name, input, output, session info |
| `UserPromptSubmit` | When user submits a prompt | User message text |
| `Stop` | When Claude finishes responding | Final message, session info |
| `SessionStart` | When session begins | Session metadata |
| `SessionEnd` | When session ends | Session metadata |
| `SubagentStart` | When a subagent launches | Agent info |
| `SubagentStop` | When a subagent completes | Agent output |
| `Notification` | System notifications | Notification data |
| `PermissionRequest` | Protected operation needs approval | Operation details |
| `TaskStart` | Background task begins | Task info |
| `TaskStop` | Background task ends | Task output |
| `Error` | When an error occurs | Error details |

### Hook Handler Types (3 types)
| Type | How it works |
|------|-------------|
| `command` | Runs a shell command. Stdin = JSON with tool_input/cwd. Stdout = fed back as context. Exit 0 = pass, Exit 2 = block. |
| `prompt` | Sends a text prompt to Claude as additional context. No shell execution. |
| `agent` | Spawns a subagent with the given prompt. Agent output determines pass/fail. Has configurable timeout. |

### Subagent Frontmatter Fields
```yaml
name: string              # Agent name
description: string       # When-to-use description (shown in Agent tool)
tools: string             # Comma-separated tool list (Read, Write, Edit, Bash, Glob, Grep, etc.)
model: string             # Model override (sonnet, opus, haiku)
permissionMode: string    # Permission mode for the agent
context: string           # "fork" for isolated context
agent: string             # Base agent type (general-purpose, Plan, etc.)
allowed-tools: string     # Alternative tool specification
```

### Skill Frontmatter Fields
```yaml
name: string              # Skill name (used in /skillname invocation)
description: string       # Trigger description and usage guidance
argument-hint: string     # Hint shown for arguments
context: string           # "fork" for isolated context
agent: string             # Agent type to use (general-purpose, Plan)
allowed-tools: string     # Tools available to the skill
effort: string            # Effort level (low, medium, high)
disable-model-invocation: boolean  # Prevent model invocation
```

### Current Model Options
| Model | ID | Context | Notes |
|-------|-----|---------|-------|
| Opus 4.6 | `claude-opus-4-6` | 1M tokens | Most capable, used as default and advisor |
| Sonnet 4.6 | `claude-sonnet-4-6` | Standard | Fast mode (same model, faster output) |
| Haiku 4.5 | `claude-haiku-4-5-20251001` | Standard | Lightweight, used for dependency-manager |

### Key CLI Flags for Prompt Engineering
| Flag | Purpose |
|------|---------|
| `--model <model>` | Override model (sonnet, opus, haiku, or full ID) |
| `-p, --print` | Non-interactive pipe mode |
| `--system-prompt <prompt>` | Custom system prompt |
| `--append-system-prompt <prompt>` | Append to default system prompt |
| `--effort <level>` | low, medium, high, max |
| `-r, --resume [id]` | Resume conversation |
| `-c, --continue` | Continue most recent conversation |
| `--add-dir <dirs>` | Additional directory access |
| `-w, --worktree [name]` | Create git worktree for session |
| `--agent <agent>` | Use specific agent |
| `--agents <json>` | Define inline agents |
| `--allowedTools <tools>` | Restrict tool set |
| `--disallowedTools <tools>` | Block specific tools |
| `--mcp-config <configs>` | Load MCP servers |
| `--json-schema <schema>` | Structured output validation |
| `--output-format <fmt>` | text, json, stream-json |
| `--max-budget-usd <amount>` | Cost cap |
| `--permission-mode <mode>` | acceptEdits, auto, bypassPermissions, default, dontAsk, plan |
| `--bare` | Minimal mode, skip hooks/LSP/plugins |
| `--plugin-dir <path>` | Load plugins from directory |
| `--settings <file>` | Additional settings file |
| `--fallback-model <model>` | Auto-fallback when overloaded |
| `-n, --name <name>` | Session display name |
| `--fork-session` | New session ID when resuming |
| `--tools <tools>` | Specify built-in tool set |

### Key Environment Variables
| Variable | Purpose |
|----------|---------|
| `CLAUDECODE=1` | Indicates running inside Claude Code |
| `CLAUDE_CODE_ENTRYPOINT` | How Claude was invoked (cli, ide, etc.) |
| `CLAUDE_CODE_EXECPATH` | Path to Claude Code installation |
| `CLAUDE_CODE_SIMPLE=1` | Set by `--bare` mode |
| `SEMGREP_APP_TOKEN` | Enables authenticated semgrep scanning |
| `ANTHROPIC_API_KEY` | API key (when not using OAuth) |

### Permission Modes
| Mode | Behavior |
|------|----------|
| `default` | Ask for each tool use |
| `acceptEdits` | Auto-allow file edits, ask for Bash |
| `auto` | AI classifies risk level |
| `dontAsk` | Never ask, deny if not allowed |
| `bypassPermissions` | Allow everything (current setting) |
| `plan` | Plan mode, no edits allowed |

---

## How to Use This File

Hand this entire file to Claude in claude.ai chat with the instruction:

"Use this audit of my Claude Code environment to update my prompt-engineer skill with accurate, current information about Claude Code features, my configuration, my subagents, my hooks, my skills, and my workflows. The updated skill should generate prompts that are perfectly tailored to my actual setup."
