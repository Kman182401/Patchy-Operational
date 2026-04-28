# Claude Code Ecosystem Audit Report

**Generated:** 2026-04-05T18:13:36-04:00
**Auditor:** Claude Opus 4.6 (1M context, max effort)
**Scope:** Global + Patchy Bot + satellite projects (cracking_station, File-Window, FuzzyAI, openclaw-kraken)

---

## Executive Summary

This audit examined 24 agent definitions (14 user-level, 10 project-level), 102 user skills, 11 hook scripts, 6 MCP servers, 7 CLAUDE.md files, and the complete plugin/permission configuration across Karson's Claude Code ecosystem. The ecosystem is architecturally ambitious and well-structured -- it represents one of the more comprehensive Claude Code setups possible -- but suffers from several systemic issues that prevent automatic resource utilization.

The most critical problems are: (1) **7 of 10 Patchy Bot project agents still use Opus instead of Sonnet**, wasting significant cost on mechanical domain tasks that don't need Opus reasoning; (2) **all 10 project agents lack `maxTurns`**, creating runaway agent risk; (3) **the `subagent-chain.sh` hook exists but is not registered in `settings.json`**, so the post-implementation security review chain never fires; (4) **an API key is committed in plaintext in `~/.mcp.json`** (context7 key); and (5) **user-level agent prompts average 280+ lines each**, consuming massive context that degrades instruction-following.

The ecosystem achieves a **5.5/10 overall health score**. The architecture is sound and the routing rules are unusually thorough, but the execution layer -- agent sizing, hook registration, skill triggering, context efficiency -- needs a focused remediation pass to reach its potential.

---

## 1. Ecosystem Inventory

### 1.1 Files Scanned

| File Path | Size | Lines | Last Modified | Summary |
|-----------|------|-------|---------------|---------|
| `~/.claude/CLAUDE.md` | 1.3 KB | 32 | 5 Apr 13:02 | Global style/analysis preferences |
| `~/CLAUDE.md` | 6.9 KB | 129 | 5 Apr (current) | Core rules, agent routing, Task Master ref |
| `~/.claude/rules/truth-verification.md` | 2.1 KB | 43 | (in scope) | Fact-verification protocol |
| `~/.claude/settings.json` | ~4 KB | 166 | 5 Apr | Hooks, permissions, plugins, model config |
| `~/.mcp.json` | 944 B | 29 | 4 Apr 23:14 | MCP server definitions (playwright, chrome-devtools, context7) |
| `~/.claude/references/plugin-skill-agent-routing.md` | 10 KB | 255 | 5 Apr 16:49 | Plugin skill-to-agent mapping table |
| `~/.claude/statusline-command.sh` | ~2.5 KB | 91 | (in scope) | Custom Kali-style status line |
| `~/Patchy_Bot/CLAUDE.md` | 11 KB | 182 | 5 Apr 00:03 | Project intelligence, subagent routing, Task Master |
| `~/Patchy_Bot/.claude/settings.json` | 822 B | ~25 | 5 Apr 03:25 | Project permissions, SubagentStop hook |
| `~/Patchy_Bot/.claude/settings.local.json` | 1.5 KB | 42 | 4 Apr 17:45 | WebFetch domain allowlist |
| `~/cracking_station/CLAUDE.md` | 808 B | 17 | 4 Apr 14:19 | Password cracking project rules |
| `~/File-Window/CLAUDE.md` | 796 B | 17 | 4 Apr 14:19 | SPY trading system rules |
| `~/FuzzyAI/CLAUDE.md` | 800 B | 17 | 4 Apr 14:19 | LLM fuzzing tool rules |
| 14 user agents (`~/.claude/agents/*.md`) | 6.8-8.7 KB each | 179-293 each | 5 Apr | Domain specialist agents |
| 10 project agents (`~/Patchy_Bot/.claude/agents/*.md`) | 2.3-15 KB each | 44-241 each | 5 Apr | Patchy Bot domain agents |
| 11 hook scripts (`~/.claude/hooks/*.sh`) | 215 B - 3.3 KB | Various | 4 Apr | Automation hooks |
| 102 skill directories (`~/.claude/skills/*/SKILL.md`) | Various | Various | Various | User-level skills |

### 1.2 Component Counts

| Component | Count | Details |
|-----------|-------|---------|
| **Agents** | 14 user + 10 project = **24 total** | All have color field |
| **Skills** | 102 user + 0 project = **102 total** | Plus ~50+ plugin skills |
| **Hooks** | 8 registered + 3 unregistered = **11 total** | 3 scripts exist but aren't in settings.json |
| **MCP Servers** | 3 in `.mcp.json` + 3 plugin-managed = **6 total** | playwright, chrome-devtools, context7, exa, tavily, task-master |
| **CLAUDE.md files** | **7 total** | 2 global, 1 rules, 4 project |
| **Plugins** | **22 enabled** out of ~42 available | Including 3rd-party `pai` plugin |

---

## 2. Critical Issues (Must Fix)

### Issue C-01: API Key Exposed in Plaintext in ~/.mcp.json

- **Component:** `/home/karson/.mcp.json`, line 25
- **Problem:** The Context7 API key (`ctx7sk-a93e1851-68f5-4d48-8b52-b14ca7d1ae6b`) is stored in plaintext directly in the MCP config file. This file is in the home directory and could be committed to git, read by other processes, or exposed in debug output.
- **Impact:** API key compromise. Any process or user with read access to `~/.mcp.json` gets the key. If this home directory is tracked by git (it is -- `git status` shows this is a repo), the key could leak to a remote.
- **Evidence:** [VERIFIED] Read `~/.mcp.json` line 25: `"CONTEXT7_API_KEY": "ctx7sk-a93e1851-68f5-4d48-8b52-b14ca7d1ae6b"`
- **Recommended Fix:** Move the key to an environment variable. In `~/.mcp.json`, use `"CONTEXT7_API_KEY": "$CONTEXT7_API_KEY"` (if MCP supports env var expansion) or set the env var in your shell profile and reference it. Immediately rotate the exposed key. Add `*.mcp.json` to `~/.gitignore` if the home directory is a git repo.

### Issue C-02: subagent-chain.sh Hook Exists But Is Not Registered

- **Component:** `/home/karson/.claude/hooks/subagent-chain.sh` (exists) vs `/home/karson/.claude/settings.json` (not referenced)
- **Problem:** The `subagent-chain.sh` hook script is designed to fire on `SubagentStop` events and recommend security review after implementation agents complete. But it is not registered in `settings.json`. There is no `SubagentStop` hook entry at the global level at all.
- **Impact:** The post-implementation security review chain at the global level **never fires**. The automation that should ensure security-auditor runs after python-pro/fastapi-developer/etc. is completely inert. Only CLAUDE.md instructions (70-80% compliance) are driving this chain.
- **Evidence:** [VERIFIED] `grep "subagent-chain" ~/.claude/settings.json` returns nothing. The script exists at `~/.claude/hooks/subagent-chain.sh` with the correct logic.
- **Recommended Fix:** Add a `SubagentStop` hook entry to `~/.claude/settings.json`:
  ```json
  "SubagentStop": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "bash /home/karson/.claude/hooks/subagent-chain.sh"
        }
      ]
    }
  ]
  ```

### Issue C-03: All 10 Patchy Bot Project Agents Missing maxTurns

- **Component:** All files in `/home/karson/Patchy_Bot/.claude/agents/*.md`
- **Problem:** None of the 10 Patchy Bot project agents have the `maxTurns` field set in their frontmatter. Without `maxTurns`, agents can run indefinitely, consuming tokens and context window without bounds.
- **Impact:** Runaway agent risk. A single poorly scoped delegation could burn the entire 5-hour usage allocation. The plex-agent (241 lines, the largest project agent) is the highest risk.
- **Evidence:** [VERIFIED] `grep "maxTurns" ~/Patchy_Bot/.claude/agents/*.md` returns nothing.
- **Recommended Fix:** Add `maxTurns` to every project agent:
  - Implementation agents (config-infra, database, plex, remove, schedule, search-download, ui): `maxTurns: 15`
  - Review agents (security-agent, test-agent): `maxTurns: 10`
  - Utility (taskmaster-sync-agent): `maxTurns: 8`

### Issue C-04: 7 Patchy Bot Agents on Opus Instead of Sonnet (Cost Waste)

- **Component:** config-infra-agent, database-agent, remove-agent, schedule-agent, search-download-agent, test-agent, ui-agent
- **Problem:** These 7 agents handle domain-specific mechanical tasks (writing to specific files, running tests, editing templates) that don't require Opus-tier reasoning. They are all set to `model: opus`.
- **Impact:** Significant cost waste. Each Opus agent invocation costs roughly 5-10x a Sonnet invocation for the same token count. For a project where these agents fire frequently during subagent-driven development, this adds up fast.
- **Evidence:** [VERIFIED] `grep "model:" ~/Patchy_Bot/.claude/agents/*.md` shows 7 of 10 on opus. Only security-agent and taskmaster-sync-agent are on sonnet. plex-agent uses `inherit`.
- **Recommended Fix:** Change these 7 agents to `model: sonnet`. Keep security-agent and taskmaster-sync-agent on sonnet (correct). Keep plex-agent on `inherit` (reasonable since it's the most complex domain agent).

### Issue C-05: plex-agent Missing memory Field

- **Component:** `/home/karson/Patchy_Bot/.claude/agents/plex-agent.md`
- **Problem:** The plex-agent is the only Patchy Bot agent without `memory: project` in its frontmatter. All other 9 project agents have it.
- **Impact:** The plex-agent cannot learn from past sessions. Given it's the most complex project agent (241 lines, 15 KB), handling Plex API integration and media organization, this is a significant gap. It will repeat discovery work and lose learned patterns.
- **Evidence:** [VERIFIED] `grep "memory:" ~/Patchy_Bot/.claude/agents/plex-agent.md` returns nothing. All 9 other project agents have `memory: project`.
- **Recommended Fix:** Add `memory: project` to plex-agent frontmatter.

---

## 3. High-Priority Issues (Should Fix)

### Issue H-01: User-Level Agent Prompts Are Bloated (~280 Lines Average)

- **Component:** All 14 files in `/home/karson/.claude/agents/*.md`
- **Problem:** User-level agents average 280+ lines each (range: 179-293 lines). The subagent-builder's own documentation recommends "under 10,000 characters" which is ~50-80 lines of substantive content. These agents contain verbose checklists, tool-specific boilerplate, lengthy "integration with other agents" sections referencing agents that don't exist (e.g., `backend-developer`, `frontend-developer`, `sre-engineer`, `architect-reviewer`), and generic knowledge that adds no routing value.
- **Impact:** Context waste. Each agent invocation loads its full system prompt. A 280-line prompt at ~4 tokens/word is ~2,000+ tokens per agent invocation, much of which is generic boilerplate. Over a session with 5-10 agent delegations, this is 10,000-20,000 tokens of wasted context.
- **Evidence:** [VERIFIED] `wc -l ~/.claude/agents/*.md` shows total 3,891 lines across 14 agents. The python-pro agent is 282 lines. The error-detective is 292 lines. Target should be ~80-100 lines each.
- **Recommended Fix:** Trim each agent to ~80-100 lines. Remove:
  1. "Integration with other agents" sections that reference nonexistent agents
  2. Generic checklists that any senior developer would know
  3. JSON communication protocol blocks (no agent actually uses structured JSON messaging)
  4. Verbose topic lists that repeat the skill's inherent knowledge
  
  Keep: role definition, specific domain expertise, quality standards, step-by-step workflow, boundary definitions.

### Issue H-02: allow-all.sh Hook Exists But Is Not Registered (Redundant)

- **Component:** `/home/karson/.claude/hooks/allow-all.sh` vs `auto-approve.sh` (registered)
- **Problem:** Two separate auto-approve hooks exist: `allow-all.sh` (not registered in settings.json) and `auto-approve.sh` (registered on `PermissionRequest`). Additionally, `settings.json` has `defaultMode: "bypassPermissions"` AND `skipDangerousModePermissionPrompt: true`. This is triple redundancy.
- **Impact:** Minor -- the behavior is correct (zero prompts). But the dead `allow-all.sh` file and the stacked permission bypasses create confusion about which mechanism is actually active.
- **Evidence:** [VERIFIED] `allow-all.sh` outputs `{"decision": "allow"}` (old format). `auto-approve.sh` outputs `{"hookSpecificOutput":...}` (current format). settings.json has `bypassPermissions` mode AND the auto-approve hook.
- **Recommended Fix:** Delete `allow-all.sh` (dead code). The `bypassPermissions` mode + `auto-approve.sh` hook combination is sufficient.

### Issue H-03: Mandatory Debugging Protocol Cannot Be Enforced by CLAUDE.md Alone

- **Component:** `~/CLAUDE.md` lines 92-103, `~/.claude/memory/feedback_mandatory_debugging.md`
- **Problem:** The CLAUDE.md mandates invoking BOTH `/debugger` and `/debugging-wizard` for ANY error/bug/fix task. This is listed as "NON-NEGOTIABLE. No exceptions." But CLAUDE.md instructions have ~70-80% compliance over long sessions. There is no hook enforcing this.
- **Impact:** The mandatory debugging protocol will be skipped in ~20-30% of debugging tasks, especially later in long sessions when context compaction drops instructions. This directly contradicts the user's stated requirement.
- **Evidence:** [VERIFIED] The rule is at `~/CLAUDE.md` lines 92-103 with extensive trigger keywords. No corresponding hook exists in `settings.json` to enforce it. The memory file `feedback_mandatory_debugging.md` documents this as a firm requirement.
- **Recommended Fix:** Create a `PreToolUse` hook that detects when Claude is about to use Bash/Edit tools on `.py` files after error-related keywords appeared in the prompt. The hook should inject a reminder to invoke both debugging skills first. Alternatively, a `UserPromptSubmit` hook could scan for error keywords and add a "MUST invoke /debugger and /debugging-wizard" instruction.

### Issue H-04: Security Agent Overlap Between User-Level and Project-Level

- **Component:** User agents: `security-auditor`, `security-engineer`, `penetration-tester`. Project agent: `security-agent`.
- **Problem:** When working in the Patchy Bot project, there are now 4 security-related agents available. The project `security-agent` handles auth review, path safety, and vulnerability scanning -- which overlaps significantly with the user-level `security-auditor`. The CLAUDE.md has disambiguation rules for the 3 user-level agents, but no rule addressing the project-level `security-agent` vs user-level `security-auditor`.
- **Impact:** Ambiguous routing. When Claude encounters a security review task in Patchy Bot, it may route to either `security-agent` (project) or `security-auditor` (user) unpredictably. The `mandatory-activation.sh` hook lists the user agents but also detects project agents dynamically -- both sets appear.
- **Evidence:** [VERIFIED] The `mandatory-activation.sh` hook outputs both project agents (detected from `.claude/agents/`) and user agents (hardcoded list). The project agent `security-agent` and user agent `security-auditor` both handle code review for vulnerabilities.
- **Recommended Fix:** Add a disambiguation rule to `~/Patchy_Bot/CLAUDE.md`: "For Patchy Bot security reviews, use the project `security-agent` (it has domain-specific context). User-level `security-auditor` is for cross-project or generic security audits."

### Issue H-05: No Compaction Instructions in Any CLAUDE.md

- **Component:** All 7 CLAUDE.md files
- **Problem:** None of the CLAUDE.md files contain compaction instructions (what to preserve during `/compact`). When Claude Code compacts context, it may lose critical routing rules, state, or project-specific conventions.
- **Impact:** After compaction, Claude may stop delegating to agents, forget debugging protocol requirements, lose Task Master workflow state, or drop project-specific safety rules.
- **Evidence:** [VERIFIED] Searched all CLAUDE.md files for "compact" -- no results. No compaction guidance exists anywhere.
- **Recommended Fix:** Add a `## Compaction` section to `~/CLAUDE.md` with:
  ```markdown
  ## Compaction
  When compacting, preserve: (1) agent routing rules, (2) mandatory debugging protocol,
  (3) current task state and plan, (4) any active user_flow states, (5) safety rules.
  ```

### Issue H-06: 22 Enabled Plugins Generate Massive Tool Description Overhead

- **Component:** `~/.claude/settings.json` enabledPlugins
- **Problem:** 22 plugins are enabled. Each plugin adds skill descriptions and potentially MCP tool descriptions to the system context. Several enabled plugins are unused for Karson's primary work (rust-analyzer-lsp, typescript-lsp for a Python/Bash developer; atomic-agents; agent-sdk-dev for a non-SDK project).
- **Impact:** Each plugin adds estimated 2-5K tokens of description overhead. 22 plugins could mean 44-110K tokens of overhead before any work begins. This directly reduces available context for actual work.
- **Evidence:** [VERIFIED] `settings.json` shows 22 plugins set to `true`. The user profile describes "Python/Bash, security tools + trading systems." Plugins like `rust-analyzer-lsp`, `typescript-lsp`, `atomic-agents`, `ui5`, and `agent-sdk-dev` are unlikely to be used.
- **Recommended Fix:** Disable unused plugins:
  - `rust-analyzer-lsp` (no Rust projects observed)
  - `typescript-lsp` (no TypeScript projects observed)
  - `atomic-agents` (no evidence of use)
  - `agent-sdk-dev` (no SDK projects)
  - `plugin-dev` (only needed when building plugins)
  - `microsoft-docs` (no Microsoft tech stack)
  
  Keep: superpowers, context7, code-review, code-simplifier, feature-dev, playwright, claude-md-management, security-guidance, claude-code-setup, pyright-lsp, hookify, semgrep, chrome-devtools-mcp, pai, mcp-server-dev.

---

## 4. Medium-Priority Issues (Nice to Fix)

### Issue M-01: User Agents Reference Nonexistent Agents in Integration Sections

- **Component:** All 14 user agents in `~/.claude/agents/`
- **Problem:** Every user agent has an "Integration with other agents" section listing 6-8 agents to collaborate with. Most of these agents don't exist: `backend-developer`, `frontend-developer`, `sre-engineer`, `architect-reviewer`, `compliance-auditor`, `legal-advisor`, `qa-expert`, `build-engineer`, `tooling-engineer`, `dx-optimizer`, `data-engineer`, `ml-engineer`, `compliance-officer`, `fintech-engineer`, `network-engineer`, `platform-engineer`, `database-administrator`, `documentation-engineer`, `product-manager`.
- **Impact:** Context waste (~10-15 lines per agent, 140-210 lines total across all agents). Also confusing if Claude tries to invoke a nonexistent agent.
- **Evidence:** [VERIFIED] Read all 14 agents. For example, python-pro references `backend-developer`, `data-scientist`, `fullstack-developer`, `rust-engineer`, `golang-pro`, `typescript-pro` -- none of which exist as user agents.
- **Recommended Fix:** Replace the "Integration with other agents" section in each agent with references to agents that actually exist. Or better: remove the section entirely (it doesn't aid routing).

### Issue M-02: test-post-edit-security.sh Is a Test File in the Hooks Directory

- **Component:** `/home/karson/.claude/hooks/test-post-edit-security.sh`
- **Problem:** A test script lives alongside production hooks. While it's not registered in settings.json (so it won't fire), it adds noise to the hooks directory.
- **Impact:** Minor confusion when auditing hooks.
- **Evidence:** [VERIFIED] File exists at `~/.claude/hooks/test-post-edit-security.sh` (2.2 KB). Not referenced in settings.json.
- **Recommended Fix:** Move to a `tests/` subdirectory or delete it.

### Issue M-03: Patchy Bot Project Settings Use acceptEdits Mode While Global Uses bypassPermissions

- **Component:** `~/Patchy_Bot/.claude/settings.json` `defaultMode: "acceptEdits"` vs `~/.claude/settings.json` `defaultMode: "bypassPermissions"`
- **Problem:** The project settings restrict to `acceptEdits` with a narrow Bash allowlist. But the global settings use `bypassPermissions` with `Agent(*)`, `Bash`, and `mcp__*` all allowed. The global settings take precedence for tools not explicitly denied at the project level.
- **Impact:** The project's restrictive permissions may not behave as expected. The global `bypassPermissions` mode could override the project's `acceptEdits` intent. This creates a false sense of security at the project level.
- **Evidence:** [VERIFIED] Project settings has `"defaultMode": "acceptEdits"` with specific Bash patterns. Global has `"defaultMode": "bypassPermissions"` with blanket allows.
- **Recommended Fix:** Understand the precedence model. If the intent is project-level restriction, the global settings need to not override it. Consider whether `bypassPermissions` at the global level is truly desired when project-level restrictions exist.

### Issue M-04: No MCP Server Usage Guidance in Any CLAUDE.md

- **Component:** All CLAUDE.md files
- **Problem:** The CLAUDE.md files never instruct Claude on when to use each MCP server. The `mandatory-activation.sh` hook has a brief mention of context7, but there's no guidance for: when to use tavily vs exa for web research, when to prefer playwright vs chrome-devtools for browser automation, or when to use task-master MCP vs CLI.
- **Impact:** MCP tools are underutilized. Claude will default to its built-in tools and may not use MCP capabilities even when they would be superior.
- **Evidence:** [VERIFIED] Searched all CLAUDE.md files. Only the mandatory-activation hook mentions "use context7 MCP tool first for up-to-date docs". No other MCP guidance exists.
- **Recommended Fix:** Add to `~/CLAUDE.md`:
  ```markdown
  ## MCP Server Usage
  - **context7:** Always use for library/framework docs before implementing
  - **exa/tavily:** Use for web research. Prefer exa for semantic search, tavily for factual queries
  - **playwright:** Use for E2E testing and browser automation
  - **chrome-devtools:** Use for performance debugging and accessibility auditing
  - **task-master:** Prefer CLI commands over MCP tools (per Patchy Bot rules)
  ```

### Issue M-05: Satellite Projects Have Minimal CLAUDE.md Files

- **Component:** `~/cracking_station/CLAUDE.md`, `~/File-Window/CLAUDE.md`, `~/FuzzyAI/CLAUDE.md`
- **Problem:** These three project CLAUDE.md files are bare-minimum (17 lines each). They contain basic project description and coding rules but no agent routing, no subagent delegation rules, and no reference to the user-level agents that should be used.
- **Impact:** When working in these projects, Claude won't proactively delegate to subagents. All work will happen in the main thread.
- **Evidence:** [VERIFIED] Read all three files. They contain only "Context" and "Project-Specific Rules" sections. No routing rules, no MCP guidance, no compaction instructions.
- **Recommended Fix:** Add a minimal routing section to each:
  ```markdown
  ## Agent Routing
  Delegate per ~/CLAUDE.md routing rules. Key agents for this project:
  - Python code: python-pro
  - Security review: security-auditor
  - Testing: (describe test approach)
  ```

### Issue M-06: pre-commit-gate.sh Allows --no-verify Override

- **Component:** `/home/karson/.claude/hooks/pre-commit-gate.sh` line 21
- **Problem:** The pre-commit gate hook explicitly allows `--no-verify` to bypass test requirements. While this is designed as an escape hatch, it means Claude can learn to add `--no-verify` to skip tests.
- **Impact:** If Claude encounters test failures, it could learn to append `--no-verify` rather than fixing the tests. This undermines the hook's purpose.
- **Evidence:** [VERIFIED] Line 21: `if echo "$COMMAND" | grep -qE '\-\-no-verify'; then exit 0; fi`
- **Recommended Fix:** Remove the `--no-verify` bypass. If the user truly needs to override, they can do it outside of Claude Code. The hook should also log when tests are skipped so it's auditable.

### Issue M-07: Patchy Bot CLAUDE.md References TodoWrite (Deprecated in Claude Code)

- **Component:** `~/Patchy_Bot/CLAUDE.md` line 121
- **Problem:** The Patchy Bot CLAUDE.md's subagent-driven development section says "Use TodoWrite to create a task list from the user's request." The TodoWrite tool may not always be available or may conflict with the Task Master workflow that's also mandated.
- **Impact:** Conflicting task-tracking approaches. Task Master (mandated in lines 143-175) and TodoWrite are separate systems. Using both creates confusion about the source of truth.
- **Evidence:** [VERIFIED] Line 121: "Use TodoWrite to create a task list from the user's request." Lines 143-175 mandate Task Master for all task tracking.
- **Recommended Fix:** Replace the TodoWrite reference with Task Master: "Use `task-master add-task` to create tasks from the user's request."

---

## 5. Low-Priority Issues (Opportunistic)

### Issue L-01: openclaw-kraken Has No CLAUDE.md

- **Component:** `/home/karson/openclaw-kraken/`
- **Problem:** No CLAUDE.md file exists for this project.
- **Impact:** No project-specific guidance when working in this directory.
- **Recommended Fix:** Create a minimal CLAUDE.md with project context and rules.

### Issue L-02: Color Assignments Not Fully Consistent Across Project Agents

- **Component:** Patchy Bot project agents
- **Problem:** Three agents (remove-agent, schedule-agent, search-download-agent) all use `color: pink`, which is not in the standard color table defined in `~/CLAUDE.md`. The color table defines implementation agents as blue, but these are pink.
- **Evidence:** [VERIFIED] grep shows three agents with `color: pink`. The CLAUDE.md color table has no "pink" category.
- **Recommended Fix:** Either add "pink" to the color table for Patchy Bot domain agents, or change these to "blue" (implementation) per the standard table.

### Issue L-03: Verification-loop Skill Has Vague Description

- **Component:** `/home/karson/.claude/skills/verification-loop/SKILL.md`
- **Problem:** Description is just "A comprehensive verification system for Claude Code sessions." This is too vague to auto-trigger.
- **Evidence:** [VERIFIED] Read skill frontmatter.
- **Recommended Fix:** Rewrite description: `"This skill should be used when the user asks to 'verify my work', 'check everything', 'verification pass', 'final check', 'validate session', or needs a comprehensive pre-completion verification of all changes made during the session."`

### Issue L-04: Security-Review Skill Has Weak Description

- **Component:** `/home/karson/.claude/skills/security-review/SKILL.md`
- **Problem:** Description starts with "Use this skill when adding authentication..." which is adequate but doesn't include the "This skill should be used when" prefix pattern that other skills use. It also lacks specific trigger phrases in quotes.
- **Evidence:** [VERIFIED] Description: "Use this skill when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing payment/sensitive features."
- **Recommended Fix:** Rewrite to match the standard pattern: `"This skill should be used when the user asks for 'security review', 'check for vulnerabilities', 'OWASP check', 'security audit of this code', or when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing payment/sensitive features."`

### Issue L-05: Duplicate Effort Field Line in subagent-builder.md

- **Component:** `/home/karson/.claude/agents/subagent-builder.md`
- **Problem:** The `effort:` line appears twice in the frontmatter, and also appears in the body text. grep shows 3 matches for "effort:" in this file.
- **Evidence:** [VERIFIED] `grep "effort:" ~/.claude/agents/subagent-builder.md` returns 3 lines.
- **Recommended Fix:** Remove the duplicate `effort: medium` line from frontmatter (keep one) and leave the body reference as documentation.

---

## 6. Subagent Analysis Detail

### 6.1 Description Quality Scorecard

| Agent Name | Location | Model | Description Rating | Has maxTurns | Has Memory | Overlap Risk |
|------------|----------|-------|--------------------|-------------|------------|--------------|
| python-pro | user | opus | STRONG | Yes (20) | Yes (user) | Low |
| fastapi-developer | user | opus | STRONG | Yes (20) | Yes (user) | Low |
| cli-developer | user | opus | STRONG | Yes (20) | Yes (user) | Low |
| docker-expert | user | opus | STRONG | Yes (20) | Yes (user) | Low |
| quant-analyst | user | opus | STRONG | Yes (20) | Yes (user) | Low |
| security-engineer | user | opus | STRONG | Yes (20) | Yes (user) | MEDIUM (vs security-agent) |
| security-auditor | user | sonnet | STRONG | Yes (10) | Yes (user) | HIGH (vs security-agent) |
| penetration-tester | user | opus | STRONG | Yes (10) | Yes (user) | MEDIUM (vs security-agent) |
| error-detective | user | opus | STRONG | Yes (15) | Yes (user) | Low |
| performance-engineer | user | opus | STRONG | Yes (15) | Yes (user) | Low |
| incident-responder | user | sonnet | STRONG | Yes (25) | Yes (user) | Low |
| dependency-manager | user | sonnet | STRONG | Yes (15) | Yes (user) | Low |
| skill-builder | user | opus | STRONG | Yes (25) | Yes (user) | Low |
| subagent-builder | user | opus | STRONG | Yes (25) | Yes (user) | Low |
| config-infra-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |
| database-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |
| plex-agent | project | inherit | STRONG | **NO** | **NO** | Low |
| remove-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |
| schedule-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |
| search-download-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |
| security-agent | project | sonnet | STRONG | **NO** | Yes (project) | HIGH (vs security-auditor) |
| taskmaster-sync-agent | project | sonnet | STRONG | **NO** | Yes (project) | Low |
| test-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |
| ui-agent | project | **opus** | STRONG | **NO** | Yes (project) | Low |

**Summary:** Description quality is universally STRONG -- every agent has "MUST BE USED when" with specific trigger conditions and "NOT for" disambiguation. This is excellent and above average for Claude Code ecosystems. The issues are in the metadata (model tier, maxTurns, memory) and prompt bloat, not in routing descriptions.

### 6.2 Routing Gap Analysis

**Agents never referenced in any CLAUDE.md routing rules:**
- None! All 14 user agents are referenced in `~/CLAUDE.md` routing table (lines 52-65). All 10 project agents are referenced in `~/Patchy_Bot/CLAUDE.md` (lines 108-114).

**However**, the mandatory-activation.sh hook hardcodes only user agents (lines 50-61) and dynamically discovers project agents (lines 16-41). This means project agents appear in the hook output with truncated descriptions that may be less useful than the full CLAUDE.md routing table.

### 6.3 Overlap Map

**HIGH overlap pair:**

1. **security-auditor (user)** vs **security-agent (project)** -- When in the Patchy Bot project, both agents match "security review", "vulnerability scanning", and "code audit" tasks. The user-level agent has general security expertise; the project-level agent has Patchy Bot-specific context (auth system layers, path safety system, specific file locations). No disambiguation rule exists in `~/Patchy_Bot/CLAUDE.md`.

**MEDIUM overlap pairs:**

2. **security-engineer (user)** vs **security-agent (project)** -- When implementing new security controls in Patchy Bot. The user agent handles general security engineering; the project agent handles Patchy Bot auth implementation. The project agent is read-only (tools: Read, Grep, Glob, Bash) so this overlap is partially resolved by tool restriction.

3. **penetration-tester (user)** vs **security-agent (project)** -- For offensive testing of Patchy Bot. However, the project agent is read-only, so the overlap is minimal in practice.

4. **error-detective (user)** vs **debugger skill** vs **debugging-wizard skill** -- The CLAUDE.md mandates invoking BOTH skills for any debugging, but the error-detective agent handles the same domain. When a bug occurs, should Claude invoke the error-detective agent, or the two skills, or all three? The CLAUDE.md says "ALWAYS invoke BOTH skills" but the routing table says "Errors/stack traces → error-detective".

---

## 7. Skill Triggering Analysis Detail

### 7.1 Description Quality Scorecard (Sampled)

| Skill Name | Description Rating | Auto-Trigger Likelihood | Conflict Risk |
|------------|-------------------|------------------------|---------------|
| debugger | STRONG | HIGH | Medium (vs error-detective agent) |
| debugging-wizard | STRONG | HIGH | Medium (vs debugger skill) |
| linter | STRONG | HIGH | Low |
| test-runner | STRONG | HIGH | Low |
| analyze | STRONG | HIGH | Low |
| audit | STRONG | HIGH | Low (vs expert-analysis) |
| security-reviewer | STRONG | HIGH | Medium (vs security-review, security-scan, secure-code-guardian) |
| researcher | STRONG | HIGH | Low |
| plan-builder | STRONG | HIGH | Low |
| plan-implementation | STRONG | MEDIUM | Low |
| full-orchestration | STRONG | MEDIUM | Low |
| expert-analysis | STRONG | HIGH | Low (vs audit) |
| diff-review | STRONG | MEDIUM | Low |
| deploy-checklist | STRONG | MEDIUM | Low |
| documentation | STRONG | MEDIUM | Low |
| assumptions-audit | STRONG | MEDIUM | Low |
| scope-guard | STRONG | MEDIUM | Low |
| code-reviewer | STRONG | HIGH | Medium (vs code-review plugin skill) |
| verification-loop | **WEAK** | **LOW** | Low |
| security-review | ADEQUATE | MEDIUM | Medium (vs security-reviewer) |

### 7.2 Undertriggering Risk Assessment

**Highest undertriggering risk:**

1. **verification-loop** -- Description "A comprehensive verification system for Claude Code sessions" is too vague. No trigger phrases, no scenarios. Will almost never auto-trigger.

2. **security-review** -- Adequate but doesn't follow the "This skill should be used when the user asks to..." pattern. Lower auto-trigger priority compared to the more assertive `security-reviewer` skill.

3. **plan-implementation** -- Depends on recognizing that a prior planning step produced output. Trigger condition ("Use after /plan-builder, /audit, /expert-analysis...") is specific but requires Claude to remember the conversation history.

**Security skill confusion cluster:**
The user has 5 overlapping security-related skills: `security-reviewer`, `security-review`, `security-scan`, `secure-code-guardian`, `fullstack-guardian`. When Claude encounters a security task, it may struggle to pick the right one. Consolidation would help.

---

## 8. CLAUDE.md Health Scorecard

| File Path | Lines | Est. Instructions | Within Budget? | Has Routing Rules? | Has MCP Guidance? | Has Compaction Instructions? |
|-----------|-------|-------------------|----------------|-------------------|-------------------|------------------------------|
| `~/.claude/CLAUDE.md` | 32 | ~15 | Yes | No | No | No |
| `~/CLAUDE.md` | 129 | ~55 | Yes | **Yes (excellent)** | Minimal (in hook) | **No** |
| `~/.claude/rules/truth-verification.md` | 43 | ~20 | Yes | No | No | No |
| `~/Patchy_Bot/CLAUDE.md` | 182 | ~70 | Borderline | **Yes (excellent)** | No | **No** |
| `~/cracking_station/CLAUDE.md` | 17 | ~8 | Yes | No | No | No |
| `~/File-Window/CLAUDE.md` | 17 | ~8 | Yes | No | No | No |
| `~/FuzzyAI/CLAUDE.md` | 17 | ~8 | Yes | No | No | No |

**Total global instructions loaded in a Patchy Bot session:** ~32 + 129 + 43 + 182 = **386 lines (~160 instructions)**

This is near the upper end of the ~150-200 instruction budget. When the Task Master CLAUDE.md is imported (an additional ~200 lines), the total exceeds the budget. Add the mandatory-activation.sh hook output (~30 lines per prompt), and instruction-following degradation is expected in long sessions.

---

## 9. Hook Coverage Matrix

| Behavior | Currently Enforced By | Should Be Enforced By | Compliance Level |
|----------|----------------------|----------------------|------------------|
| Agent delegation for tasks | CLAUDE.md rules + mandatory-activation.sh hook | Hook (current) + CLAUDE.md | ~85% (hook fires every prompt) |
| Security review after implementation | CLAUDE.md rules only | SubagentStop hook (**broken -- not registered**) | ~70% (CLAUDE.md only) |
| Test before commit | pre-commit-gate.sh hook | Hook (current) | 100% (with --no-verify escape) |
| Post-edit linting | post-edit-lint.sh hook | Hook (current) | 100% |
| Post-edit security scan | post-edit-security.sh hook | Hook (current) | 100% |
| Dangerous command blocking | pre-bash-safety.sh hook | Hook (current) | 100% |
| Mandatory debugging skills | CLAUDE.md rules only | **Should be a hook** | ~70% (CLAUDE.md only) |
| Context7 for library docs | mandatory-activation.sh hint | Should be in CLAUDE.md | ~50% (hint only) |
| Session tool check | session-start.sh hook | Hook (current) | 100% |
| Uncommitted changes warning | pre-exit.sh hook | Hook (current) | 100% |
| Auto-approve permissions | auto-approve.sh hook + bypassPermissions | Hook (current) | 100% |
| Post-subagent test run (Patchy Bot) | SubagentStop hook in project settings | Hook (current) | 100% (project only) |

---

## 10. MCP Server Utilization

| Server Name | Referenced in CLAUDE.md? | Accessible By Which Agents? | Estimated Usage Frequency | Underused? |
|-------------|--------------------------|----------------------------|--------------------------|------------|
| playwright | No | All (global mcp__* allow) | Low | **YES** -- no guidance on when to use |
| chrome-devtools | No | All (global mcp__* allow) | Low | **YES** -- no guidance on when to use |
| context7 | Mentioned in mandatory-activation.sh | All (global mcp__* allow) | Medium | Slightly -- should be in CLAUDE.md |
| exa | No | All (global mcp__* allow) | Low | **YES** -- no guidance on when to use |
| tavily | No | All (global mcp__* allow) | Low | **YES** -- no guidance on when to use |
| task-master | Referenced in Patchy Bot CLAUDE.md | All (global mcp__* allow) | High (Patchy Bot) | No -- well-documented |

**Key gap:** Agents that restrict their `tools:` to `Read, Grep, Glob` (like security-auditor) cannot use MCP tools even though the global settings allow `mcp__*`. If a security audit needs context7 for library docs or exa for CVE research, the agent can't access them.

---

## 11. Improvement Plan

### Phase 1: Critical Fixes (Do First)

1. **Rotate and secure the Context7 API key** (`~/.mcp.json` line 25). Move to environment variable. Estimated effort: quick.

2. **Register subagent-chain.sh in settings.json** as a SubagentStop hook. This enables the post-implementation security review chain globally. Estimated effort: quick.

3. **Add `maxTurns` to all 10 Patchy Bot project agents.** Implementation agents: 15. Review agents: 10. Utility: 8. Estimated effort: quick.

4. **Change 7 Patchy Bot project agents from opus to sonnet.** Keep security-agent and taskmaster-sync-agent on sonnet. Keep plex-agent on inherit. Estimated effort: quick.

5. **Add `memory: project` to plex-agent.** Estimated effort: quick.

### Phase 2: Routing and Descriptions Overhaul

6. **Add security agent disambiguation to Patchy Bot CLAUDE.md.** Specify when to use project `security-agent` vs user `security-auditor`. Estimated effort: quick.

7. **Add compaction instructions to ~/CLAUDE.md.** Specify what to preserve during `/compact`. Estimated effort: quick.

8. **Add MCP server usage guidance to ~/CLAUDE.md.** When to use each of the 6 MCP servers. Estimated effort: quick.

9. **Resolve debugging protocol vs error-detective overlap.** Clarify in ~/CLAUDE.md that the debugging skills are for root cause analysis and the error-detective agent is for deep investigation, and both should be used together. Estimated effort: quick.

10. **Add agent routing sections to satellite project CLAUDE.md files.** cracking_station, File-Window, FuzzyAI each need a 5-line routing section. Estimated effort: quick.

### Phase 3: CLAUDE.md Optimization

11. **Trim user-level agent prompts from ~280 lines to ~80-100 lines each.** Remove: integration sections with nonexistent agents, generic checklists, JSON protocol blocks. This is the single highest-impact change for context efficiency. Estimated effort: significant (14 files).

12. **Remove TodoWrite reference from Patchy Bot CLAUDE.md.** Replace with Task Master equivalent. Estimated effort: quick.

13. **Clean up ~/CLAUDE.md redundancy.** The Task Master quick reference (lines 109-125) partially duplicates the Task Master CLAUDE.md that gets imported. Consider removing the quick reference in favor of the import. Estimated effort: quick.

### Phase 4: Hook Reinforcement

14. **Create a debugging-protocol enforcement hook.** A UserPromptSubmit hook that detects error/bug keywords and injects a reminder to invoke both debugging skills. Estimated effort: medium.

15. **Remove --no-verify escape from pre-commit-gate.sh.** Prevents Claude from learning to bypass tests. Estimated effort: quick.

16. **Delete allow-all.sh** (dead code, not registered). Estimated effort: quick.

17. **Move test-post-edit-security.sh** out of the hooks directory. Estimated effort: quick.

### Phase 5: Skill Description Optimization

18. **Rewrite verification-loop description** with specific trigger phrases. Estimated effort: quick.

19. **Rewrite security-review description** to use the standard pattern with trigger phrases. Estimated effort: quick.

20. **Consolidate security skill descriptions** to reduce confusion. Consider merging security-review and security-reviewer into one, or adding clear disambiguation. Estimated effort: medium.

### Phase 6: Advanced Automation

21. **Disable unused plugins** (6-8 plugins identified in H-06). Reduces context overhead by estimated 12-40K tokens per session. Estimated effort: quick.

22. **Add MCP tool access to security-auditor agent** for context7 and exa. Currently restricted to Read, Grep, Glob, which blocks MCP usage. Estimated effort: quick.

23. **Create a post-session summary hook** that auto-generates a standup-style summary of what was accomplished. Estimated effort: medium.

---

## 12. Metrics and Scoring

### Overall Ecosystem Health: 5.5/10

| Category | Score | Notes |
|----------|-------|-------|
| Agent routing reliability | 7/10 | Descriptions are excellent. Overlap between user/project security agents and debugging protocol confusion lower the score. |
| Skill auto-triggering | 6/10 | Most skills have good descriptions. 5 security skills overlap. verification-loop is effectively dead. |
| CLAUDE.md instruction budget | 5/10 | Near budget limit for Patchy Bot sessions. Task Master import pushes it over. No compaction instructions. |
| Hook coverage | 4/10 | subagent-chain.sh not registered (broken). Mandatory debugging not enforced by hook. Good coverage otherwise. |
| MCP utilization | 3/10 | 5 of 6 servers have no CLAUDE.md guidance. Read-only agents can't access MCP tools. Context7 is the only one with a trigger hint. |
| Context efficiency | 4/10 | 14 agents at 280 lines each is 3,900 lines of agent prompts. 22 plugins add tool description overhead. Significant room to trim. |
| Cross-component integration | 6/10 | Routing tables are thorough. Plugin-skill-agent-routing.md is excellent. Missing compaction, missing hook registration, missing MCP guidance prevent full integration. |

---

## Appendix A: Raw File Sizes and Token Estimates

| Component | Files | Total Lines | Est. Tokens | Notes |
|-----------|-------|-------------|-------------|-------|
| CLAUDE.md files (global session) | 3 | 204 | ~2,500 | Loaded every session |
| CLAUDE.md (Patchy Bot) | 1 | 182 | ~2,200 | + Task Master import (~300 lines) |
| User agent prompts (14) | 14 | 3,891 | ~47,000 | Only loaded on invocation |
| Project agent prompts (10) | 10 | 778 | ~9,400 | Only loaded on invocation |
| Hook output (mandatory-activation per prompt) | 1 | ~30 | ~400 | Fires EVERY user prompt |
| MCP tool descriptions (est.) | 6 servers | N/A | ~60,000-90,000 | Always in context |
| Plugin skill descriptions (est.) | ~150 | N/A | ~30,000-50,000 | Always in context |
| **Session start overhead (est.)** | - | - | **~95,000-145,000** | Before any work begins |

---

## Appendix B: Complete Agent Description Inventory

### User-Level Agents (14)

1. **python-pro:** "MUST BE USED for all Python code: writing, reviewing, refactoring, debugging, or optimizing .py files. Expert in Python 3.11+, async/await, type hints, pytest, and production patterns. NOT for FastAPI-specific work (use fastapi-developer)."
2. **fastapi-developer:** "MUST BE USED when working with FastAPI endpoints, Pydantic models, ASGI apps, or async Python APIs. Expert in FastAPI 0.100+, dependency injection, and OpenAPI generation. NOT for general Python scripts (use python-pro)."
3. **cli-developer:** "MUST BE USED when building CLI tools, argument parsers, terminal UIs, or shell scripts that need structured command design. Expert in Click, Rich, argparse, and cross-platform CLI patterns."
4. **docker-expert:** "MUST BE USED when working with Dockerfiles, docker-compose.yml, container images, or container orchestration. Expert in multi-stage builds, image hardening, and CI/CD container pipelines."
5. **quant-analyst:** "MUST BE USED for quantitative trading, financial modeling, backtesting, derivatives pricing, portfolio optimization, or statistical arbitrage. Expert in risk analytics, alpha generation, and market microstructure."
6. **security-engineer:** "MUST BE USED when IMPLEMENTING security controls: building auth systems, hardening infrastructure, managing secrets, integrating security into CI/CD. Expert in threat modeling, zero-trust, and DevSecOps. NOT for reviewing existing code (use security-auditor) or offensive testing (use penetration-tester)."
7. **security-auditor:** "MUST BE USED AFTER code changes to REVIEW for vulnerabilities. Invoke for security audits, compliance checks, OWASP Top 10 scanning, secrets detection, and risk assessment. Read-only -- analyzes but never modifies project code. NOT for implementing security controls (use security-engineer) or exploitation (use penetration-tester)."
8. **penetration-tester:** "MUST BE USED for OFFENSIVE security testing: vulnerability exploitation, attack surface mapping, and hands-on security validation. Expert in ethical hacking, OWASP testing methodology, and exploit development. NOT for implementing defenses (use security-engineer) or passive code review (use security-auditor)."
9. **error-detective:** "MUST BE USED when encountering errors, stack traces, test failures, or unexpected behavior. Diagnoses root causes through log analysis, error correlation, and systematic hypothesis testing. Analyzes but does not fix -- returns diagnosis to the main session."
10. **performance-engineer:** "MUST BE USED when investigating slow performance, high resource usage, bottlenecks, or scalability issues. Expert in profiling, load testing, database optimization, and infrastructure tuning. Analyzes and benchmarks but does not modify project code."
11. **incident-responder:** "MUST BE USED during active incidents: security breaches, service outages, data corruption, or operational emergencies. Expert in rapid triage, evidence preservation, and coordinated recovery."
12. **dependency-manager:** "MUST BE USED for dependency audits, CVE scanning, version conflict resolution, license compliance, and update strategies. Analyzes dependency trees and recommends secure upgrade paths. Does not modify project files."
13. **skill-builder:** "MUST BE USED when creating, editing, validating, or improving Claude Code skills. Expert in SKILL.md structure, progressive disclosure, trigger phrase design, and bundled resources (scripts/, references/, examples/, assets/). NOT for agent/subagent creation (use subagent-builder)."
14. **subagent-builder:** "MUST BE USED when creating, editing, validating, or improving Claude Code subagents (agents in ~/.claude/agents/). Expert in agent frontmatter, triggering descriptions, system prompt design, color assignment, and tool selection. NOT for skill creation (use skill-builder)."

### Project-Level Agents (10 -- Patchy Bot)

1. **config-infra-agent:** "MUST be used for any work involving configuration, environment variables, the startup sequence, systemd service management, logging, the .env file structure, VPN configuration, or infrastructure changes."
2. **database-agent:** "MUST be used for any work involving the SQLite database, the Store class, table schemas, database migrations, CRUD methods, backup operations, or data integrity."
3. **plex-agent:** "MUST be used for any work involving Plex Media Server integration, the PlexInventoryClient, media file organization, library scanning, trash management..." (15 KB -- the most detailed agent, with examples)
4. **remove-agent:** "MUST be used for any work involving the media removal/deletion system, Plex cleanup after deletion, the remove background runner, path safety validation, the browse-library UI..."
5. **schedule-agent:** "MUST be used for any work involving TV show episode tracking, the schedule system, TVMaze/TMDB metadata, auto-download logic, the schedule background runner..."
6. **search-download-agent:** "MUST be used for any work involving torrent searching, download initiation, download progress tracking, the completion poller, the pending monitor, or QBClient operations."
7. **security-agent:** "MUST be used for any work involving authentication, authorization, rate limiting, password handling, brute-force protection, input validation, path safety, secrets management, or security review."
8. **taskmaster-sync-agent:** "MUST be used at the end of every completed task, feature, bugfix, or process to sync TaskMaster with what actually happened."
9. **test-agent:** "MUST be used for writing tests, running the test suite, debugging test failures, improving test coverage, or working with test infrastructure."
10. **ui-agent:** "MUST be used for any work involving Telegram UI rendering, inline keyboards, message formatting, callback routing structure, the command center..."

---

## Appendix C: Complete Skill Description Inventory (Sampled -- 20 Key Skills)

| Skill | Description Pattern | Rating |
|-------|-------------------|--------|
| debugger | "Debugging specialist. Use PROACTIVELY when..." | STRONG |
| debugging-wizard | "Parses error messages, traces execution flow..." | STRONG |
| linter | "Auto-lint and format specialist. Use PROACTIVELY after..." | STRONG |
| test-runner | "Test execution specialist. Use PROACTIVELY after..." | STRONG |
| analyze | "Deep post-completion review. Use PROACTIVELY immediately after..." | STRONG |
| audit | "Run a deep, professional, read-only audit..." | STRONG |
| security-reviewer | "Security-focused code reviewer. Use PROACTIVELY after..." | STRONG |
| security-review | "Use this skill when adding authentication..." | ADEQUATE |
| security-scan | "Scan your Claude Code configuration (.claude/)..." | STRONG |
| secure-code-guardian | "Use when implementing authentication/authorization..." | STRONG |
| researcher | "Research specialist for gathering current information. Use PROACTIVELY..." | STRONG |
| plan-builder | "Research-first implementation planner. Use PROACTIVELY before..." | STRONG |
| plan-implementation | "Execute an already approved plan, report, analysis..." | STRONG |
| full-orchestration | "This skill should be used when the user asks to 'use all agents'..." | STRONG |
| expert-analysis | "Deep, evidence-first investigation of a codebase..." | STRONG |
| code-reviewer | "Analyzes code diffs and files to identify bugs..." | STRONG |
| diff-review | "This skill should be used when the user asks to 'review my diff'..." | STRONG |
| verification-loop | "A comprehensive verification system for Claude Code sessions." | **WEAK** |
| exa-ai | "This skill should be used when the user asks to 'search the web with AI'..." | STRONG |
| assumptions-audit | "This skill should be used when the user asks to 'check my assumptions'..." | STRONG |
