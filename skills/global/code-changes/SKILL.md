---
name: code-changes
description: >
  Master orchestration skill for implementing code changes with full safety coverage.
  This skill should be used when the user says "implement this", "build this feature",
  "make these changes", "code this up", "write the code", "implement the plan",
  "full implementation", "code changes", "/code-changes", or when beginning any
  non-trivial code implementation, feature build, refactor, or infrastructure change.
  Sequences 20+ skills across 5 phases: research → plan → implement → verify → close.
  Ensures no skill or agent is missed during implementation work.
  NOT for read-only analysis (use /read-only-plans) or debugging (use /debug-fix) or
  post-completion audits (use /post-changes-audit).
---

# Code Changes — Full Implementation Orchestration

$ARGUMENTS

Execute code changes through five mandatory phases. Every phase invokes specific skills in order. Do not skip phases. Do not skip skills within a phase unless explicitly inapplicable to the task.

---

## Phase 1: Research & Reconnaissance

**Goal:** Understand the problem space before touching code.

**Sequential — complete before moving to Phase 2.**

1. **`/researcher`** — Gather current best practices, library versions, API docs, security advisories for any technology involved. Skip only if the task is purely internal with no external dependencies.
2. **`/reuse-check`** — Scan the codebase for existing implementations, utilities, or patterns that solve part of the problem. Prevent reinventing existing code.
3. **`/the-fool`** — Challenge the proposed approach. Identify blind spots, unstated assumptions, and alternative designs before committing to a direction.

---

## Phase 2: Planning & Scoping

**Goal:** Produce a decision-complete plan before writing code.

**Sequential — complete before moving to Phase 3.**

4. **`/plan-builder`** — Produce a durable, restartable implementation plan with milestones, validation gates, and risk assessment. Ground the plan in the actual repo state.
5. **`/assumptions-audit`** — Extract and classify every assumption in the plan. Verify critical assumptions. Flag risky ones as blockers.
6. **`/scope-guard`** — Lock the scope boundary. Define what files, modules, and systems are in-scope and what is explicitly out-of-scope. Enforce this boundary throughout execution.
7. **`/subagent-driven-development`** — Identify which subagents to delegate implementation work to. Map tasks to domain agents (python-pro, fastapi-developer, cli-developer, etc.).
8. **`/dispatching-parallel-agents`** — Determine which agent tasks can run in parallel (independent files, no shared state) vs. which must run sequentially (dependencies, shared files).

---

## Phase 3: Execution

**Goal:** Implement the plan using domain agents and safety skills.

**Mixed parallel/sequential — follow dispatch decisions from Phase 2.**

9. **`/full-orchestration`** — Activate the five-phase orchestration checklist. Ensure every applicable domain agent and skill is identified and dispatched.
10. **`/plan-implementation`** — Execute the plan milestone by milestone. Follow the plan. Do not quietly substitute a different design.
11. **`/secure-code-guardian`** — Apply security controls during implementation: input validation, auth, encryption, OWASP Top 10 prevention. Invoke for any security-sensitive code as it is written.
12. **`/simplify-code`** — After each major implementation milestone, review for unnecessary complexity. Simplify abstractions, reduce indirection, flatten where possible.
13. **`/linter`** — Auto-lint every file immediately after editing. Run ruff (Python), shellcheck (Bash), prettier (JS/HTML/CSS). Do not batch — lint as you go.
14. **`/documentation`** — Update or create documentation for any new public APIs, config changes, or architectural decisions made during implementation.

**Task manager checkpoint:**
15. **`/tm:update-task`** — Update the task tracker with implementation progress after each milestone.

---

## Phase 4: Verification & Security

**Goal:** Validate everything before claiming completion. Never skip.

**Sequential — each step feeds the next.**

16. **`/test-runner`** — Run the full test suite for touched modules. Confirm all tests pass. Report coverage.
17. **`/security-review`** — Scan all changed files for vulnerabilities using semgrep, bandit, and manual pattern checks. Flag HIGH/CRITICAL issues as blocking.
18. **`/diff-review`** — Inspect the actual git diff for debug leftovers, accidental changes, leaked secrets, and scope violations.
19. **`/verification-loop`** — Run the full verification chain: build → typecheck → lint → test → security scan → diff review.
20. **`/analyze`** — Deep post-completion review. Audit correctness, integration wiring, edge cases, and second-order effects of the changes.

---

## Phase 5: Completion

**Goal:** Clean handoff with evidence of completion.

21. **`/tm:update-task`** — Final task status update with completion evidence.
22. If a code review is needed, invoke `/requesting-code-review`.
23. If a branch is ready to merge, invoke `/finishing-a-development-branch`.

---

## Parallel vs Sequential Decision Rules

Launch in **parallel** when:
- Research + reuse-check (Phase 1 — independent information gathering)
- Multiple domain agents working on separate files (Phase 3)
- test-runner + linter (Phase 4 — independent checks)

Run **sequentially** when:
- Plan must exist before execution starts
- Security review needs final code
- Analyze needs all changes committed
- Scope-guard must be set before implementation begins

---

## Abort Conditions

Stop execution and report if:
- `assumptions-audit` returns a **Red** risk assessment with unresolved blockers
- `security-review` flags **CRITICAL** severity findings
- `test-runner` reports failing tests that cannot be resolved within scope
- `scope-guard` detects scope violations that would require re-planning

---

## Skills Checklist

Before claiming the task is complete, confirm every applicable skill was invoked:

- [ ] researcher
- [ ] reuse-check
- [ ] the-fool
- [ ] plan-builder
- [ ] assumptions-audit
- [ ] scope-guard
- [ ] subagent-driven-development
- [ ] dispatching-parallel-agents
- [ ] full-orchestration
- [ ] plan-implementation
- [ ] secure-code-guardian
- [ ] simplify-code
- [ ] linter
- [ ] documentation
- [ ] tm:update-task
- [ ] test-runner
- [ ] security-review
- [ ] diff-review
- [ ] verification-loop
- [ ] analyze
