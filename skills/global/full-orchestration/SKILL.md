---
name: full-orchestration
description: This skill should be used when the user asks to "use all agents", "maximize delegation", "full orchestration", "use every tool available", "don't miss any agents", "leverage all skills", "orchestrate this properly", or when beginning any non-trivial task where comprehensive agent and skill coverage matters. Ensures Claude Code systematically identifies and activates all beneficial subagents and skills across every phase of a task. Also trigger when beginning implementation of plans, features, refactors, debugging sessions, or any multi-step work.
---

# Full Orchestration

## Purpose

Ensure every task systematically leverages all available and beneficial subagents, skills, and tools. This skill acts as an orchestration checklist — preventing missed delegation opportunities across the five phases of any task.

## When to Trigger

Activate at the start of any non-trivial task. Particularly valuable for:
- Multi-step implementations, features, or refactors
- Debugging sessions or incident response
- Infrastructure or security work
- Any task where missing an agent or skill would reduce quality

### When NOT to Trigger

Skip full orchestration for:
- Simple questions answerable from a single file read or quick lookup
- One-line fixes, typo corrections, or trivial config changes
- Quick clarifications about existing code or project state
- Single-domain tasks with no security, testing, or cross-cutting concerns
- Conversations that are purely informational with no implementation

## The Five-Phase Orchestration Process

Every task flows through five phases. At each phase, scan for matching agents and skills before proceeding.

### Phase 1: Intake — Understand the Task

**Goal:** Classify the task and identify all applicable domains.

| Check | Action |
|-------|--------|
| Creative/new feature? | Invoke `brainstorming` skill first |
| Unfamiliar library/framework? | Use `context7` MCP for current docs |
| Bug/error/failure? | Invoke BOTH `debugger` AND `debugging-wizard` skills (mandatory per project rules) |
| External research needed? | Invoke `researcher` skill or `pai:research` |
| Microsoft technology? | Use `microsoft-docs` MCP tools |

**Domain classification — tag ALL that apply:**
- Python code → `python-pro` agent
- FastAPI / async API → `fastapi-developer` agent
- CLI / terminal → `cli-developer` agent
- Docker / containers → `docker-expert` agent
- Trading / finance → `quant-analyst` agent
- Security implementation → `security-engineer` agent
- Errors / debugging → `error-detective` agent
- Performance → `performance-engineer` agent
- Active incident → `incident-responder` agent
- Offensive security → `penetration-tester` agent
- Dependency issues → `dependency-manager` agent
- Skill creation → `skill-builder` agent
- Agent creation → `subagent-builder` agent

### Phase 2: Planning — Design the Approach

**Goal:** Plan before coding. Multi-step work needs explicit plans.

| Check | Action |
|-------|--------|
| Multi-step task? | Invoke `plan-builder` skill |
| System/architecture design? | Invoke `system-design` or `architecture-designer` skill |
| Feature requirements unclear? | Invoke `feature-forge` skill |
| Tech debt assessment? | Invoke `tech-debt` skill |
| Deployment involved? | Invoke `deploy-checklist` skill |
| Testing strategy needed? | Invoke `testing-strategy` skill |

**Framework/language skills — activate the matching one:**
- Check `references/skill-phase-map.md` for the full list of 30+ language/framework skills
- Each domain skill provides specialized patterns and best practices
- Multiple can apply (e.g., `react-expert` + `typescript-pro` for a React TypeScript app)

### Phase 3: Execution — Delegate to Agents

**Goal:** Never execute inline what a colored subagent can handle.

**Dispatch rules:**
- **Parallel dispatch** — 3+ independent tasks, no shared files, no dependency between outputs
- **Sequential dispatch** — tasks have dependencies, shared files, or unclear scope
- **Standard workflow** — domain agent implements, then `security-auditor` reviews

**Agent delegation is mandatory when a match exists.** Verify each spawned agent's color tag is visible in the dispatch summary.

| Task Type | Primary Agent | Model |
|-----------|--------------|-------|
| Python code (any .py) | `python-pro` | opus |
| FastAPI / Pydantic | `fastapi-developer` | opus |
| CLI tools / shell scripts | `cli-developer` | opus |
| Dockerfiles / compose | `docker-expert` | opus |
| Financial models | `quant-analyst` | opus |
| Security controls | `security-engineer` | opus |
| Errors / debugging | `error-detective` | opus |
| Performance profiling | `performance-engineer` | opus |
| Active incidents | `incident-responder` | sonnet |
| Offensive testing | `penetration-tester` | opus |
| Dependency audits | `dependency-manager` | sonnet |
| Skill SKILL.md files | `skill-builder` | opus |
| Agent .md files | `subagent-builder` | opus |

**Execution skills to consider:**
- `tdd-workflow` — test-driven development for any feature/bugfix
- `linter` — auto-lint after any file edit (Python, Bash, JS)
- `security-review` — for auth, user input, secrets, API endpoints
- `secure-code-guardian` — for custom security implementations
- Domain skills matching the tech stack (see Phase 2)

### Phase 4: Verification — Validate Everything

**Goal:** Never claim completion without evidence. Run every relevant check.

| Check | Action |
|-------|--------|
| Code was written/changed | Invoke `test-runner` skill |
| Any code changes at all | Invoke `linter` skill |
| Security-sensitive code | Spawn `security-auditor` agent (read-only review) |
| Performance-sensitive code | Spawn `performance-engineer` agent |
| Dependencies changed | Spawn `dependency-manager` agent |
| Complex implementation | Invoke `analyze` skill |
| Major feature complete | Invoke `code-reviewer` skill |
| Full audit needed | Invoke `audit` skill |
| Verify before claiming done | Invoke `verification-before-completion` skill |

**Mandatory post-implementation chain:**
1. `test-runner` — run tests, confirm pass
2. `linter` — lint edited files
3. `security-auditor` agent — review for vulnerabilities
4. `analyze` skill — deep post-completion review

### Phase 5: Completion — Close Out

**Goal:** Clean handoff with concrete next step.

| Check | Action |
|-------|--------|
| Code review needed? | Invoke `requesting-code-review` skill |
| Branch ready to merge? | Invoke `finishing-a-development-branch` skill |
| Plan needs updating? | Update the plan with results |
| Documentation needed? | Invoke `documentation` or `code-documenter` skill |
| Standup summary? | Invoke `standup` skill |

## Quick Decision Tree

```
Task arrives
  ├── Is it a bug/error? → debugger + debugging-wizard + error-detective
  ├── Is it creative/new? → brainstorming → plan-builder
  ├── Is it multi-step? → plan-builder → domain agents
  ├── Is it a security task? → classify: engineer vs auditor vs pentester
  └── Is it simple/quick? → domain agent only → verify
Always finish with: test-runner → linter → security-auditor → analyze
```

## Parallel vs Sequential

**Launch in parallel when:**
- Research + planning (independent information gathering)
- Multiple domain agents on separate files
- Testing + linting (independent checks)

**Run sequentially when:**
- Implementation then security review (review needs final code)
- Debugging then fix (fix needs diagnosis)
- Plan then execute (execution needs the plan)

## Additional Resources

### Reference Files

For detailed catalogs, consult:
- **`references/agent-catalog.md`** — All 14 agents with detailed selection criteria and disambiguation
- **`references/skill-phase-map.md`** — 90+ skills organized by task phase with trigger conditions

### Key Plugin Skills to Remember

Beyond standalone skills, these plugin skills add significant value:
- **superpowers** — brainstorming, plans, TDD, verification, code review, debugging, git workflows
- **pai** — research, fabric content processing, skill creation
- **chrome-devtools-mcp** — browser debugging, performance, accessibility
- **feature-dev** — guided feature development
- **hookify** — creating hooks from conversation patterns

### Routing Reference

Consult `~/.claude/references/plugin-skill-agent-routing.md` for the full plugin skill → agent delegation mapping.
