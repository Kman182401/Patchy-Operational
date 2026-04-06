---
name: debug-fix
description: >
  Master orchestration skill for systematic debugging, root cause analysis, and fix implementation.
  This skill should be used when the user says "fix this bug", "debug this", "something is broken",
  "this error", "not working", "investigate this failure", "troubleshoot", "fix this issue",
  "what's wrong", "crash", "exception", "traceback", "stack trace", "error message",
  "failing test", "regression", "debug-fix", "/debug-fix", or when any error, bug, failure,
  or unexpected behavior needs to be diagnosed and resolved. Sequences 22+ skills across
  5 phases: diagnose → plan fix → implement fix → verify fix → close.
  Combines dual-debugger methodology (debugger + debugging-wizard) with TDD-driven fixes
  and full post-fix verification.
  NOT for greenfield implementation (use /code-changes) or read-only analysis (use /read-only-plans)
  or post-completion audits (use /post-changes-audit).
---

# Debug & Fix — Systematic Debugging Orchestration

$ARGUMENTS

Execute debugging and fix implementation through five mandatory phases. The dual-debugger approach (debugger + debugging-wizard) is mandatory — both must run on every bug investigation.

---

## Phase 1: Diagnosis & Root Cause Analysis

**Goal:** Understand the bug completely before attempting any fix.

**Sequential — diagnosis must be thorough before fixing.**

1. **`/debug`** — First-pass debugging. Reproduce the issue, gather error output, identify the failing component, and narrow down the failure location.
2. **`/debugging-wizard`** — Second-pass systematic debugging. Apply hypothesis-driven methodology: reproduce → isolate → hypothesize → test each hypothesis → identify root cause. Both debugger skills are mandatory per project rules — they catch different classes of issues.
3. **`/researcher`** — If the bug involves external libraries, APIs, or unfamiliar patterns, research current known issues, changelogs, migration guides, and community reports. Check for known bugs in the specific versions involved.
4. **`/expert-analysis`** — If the root cause is unclear after initial debugging, perform deep evidence-first investigation. Analyze the surrounding code, data flow, state transitions, and failure modes.
5. **`/analyze`** — Review the broader context around the bug. Check for related issues, similar patterns elsewhere in the codebase, and second-order effects that may have contributed.

**Spawn domain agents in parallel where applicable:**
- Error in Python code → spawn `error-detective` agent
- Performance-related failure → spawn `performance-engineer` agent
- Security-related failure → spawn `security-engineer` agent

---

## Phase 2: Fix Planning

**Goal:** Design the fix before implementing it.

**Sequential — plan must be complete before coding.**

6. **`/plan-builder`** — Produce a focused fix plan: root cause summary, proposed fix approach, files to modify, risk of regression, and validation criteria.
7. **`/assumptions-audit`** — Audit assumptions in the fix plan. Verify that the root cause diagnosis is correct, that the proposed fix addresses it, and that no hidden dependencies will break.
8. **`/scope-guard`** — Lock the fix scope. Define exactly which files and functions will change. Flag any temptation to "fix nearby issues while we're here" as scope creep.
9. **`/reuse-check`** — Before implementing the fix, check if a solution pattern already exists in the codebase. Avoid reinventing existing error-handling, retry logic, or validation patterns.
10. **`/the-fool`** — Challenge the fix approach. Ask: "Is this fixing the symptom or the root cause?" "What could go wrong with this fix?" "Is there a simpler approach?"
11. **`/subagent-driven-development`** — Identify which domain agents should implement the fix.
12. **`/dispatching-parallel-agents`** — Determine parallel vs. sequential dispatch for fix implementation.

---

## Phase 3: Fix Implementation

**Goal:** Implement the fix with TDD discipline and safety controls.

**Mixed — follow dispatch decisions from Phase 2.**

13. **`/tdd-workflow`** — Write a failing test that reproduces the bug FIRST. Confirm the test fails (RED). Then implement the minimal fix to make it pass (GREEN). Then refactor if needed. This is mandatory — no fix ships without a regression test.
14. **`/full-orchestration`** — Activate full orchestration to ensure domain agents and skills are properly dispatched for the fix implementation.
15. **`/plan-implementation`** — Execute the fix plan milestone by milestone.
16. **`/secure-code-guardian`** — If the fix touches security-sensitive code (auth, input handling, crypto, permissions), apply security controls during implementation.
17. **`/simplify`** — After the fix is implemented, review for unnecessary complexity introduced by the fix. Ensure the fix is minimal and clean.
18. **`/linter`** — Auto-lint every file modified during the fix.

**Task manager checkpoint:**
19. **`/tm:update-task`** — Update task tracker with fix progress.

---

## Phase 4: Fix Verification

**Goal:** Prove the fix works and didn't break anything else.

**Sequential — each step validates a different dimension.**

20. **`/test-runner`** — Run the full test suite for all touched modules. The new regression test must pass. All existing tests must still pass. Report coverage.
21. **`/security-review`** — Scan all changed files for security issues. Fixes under pressure are prone to introducing new vulnerabilities.
22. **`/diff-review`** — Inspect the git diff for debug leftovers, accidental changes, and scope violations. Fixes often include temporary debugging code that shouldn't ship.
23. **`/verification-loop`** — Run the complete verification chain: build → typecheck → lint → test → security scan → diff review.
24. **`/analyze`** — Post-fix deep review. Verify the fix is correct, complete, and doesn't introduce second-order problems. Check that the root cause is actually addressed, not just the symptom.

---

## Phase 5: Completion

**Goal:** Clean handoff with evidence that the bug is resolved.

25. **`/tm:update-task`** — Final status update with: root cause summary, fix description, test evidence, and any remaining risks.
26. If a code review is needed, invoke `/requesting-code-review`.
27. If a branch is ready to merge, invoke `/finishing-a-development-branch`.

---

## Dual-Debugger Rule

Both `/debug` AND `/debugging-wizard` must run on every bug investigation. This is a project rule, not a suggestion.

- `/debug` provides rapid first-pass diagnosis and reproduction
- `/debugging-wizard` provides systematic hypothesis-driven methodology
- Together they catch classes of bugs that either alone would miss

---

## Abort Conditions

Stop execution and report if:
- Root cause cannot be identified after both debugger passes and expert-analysis
- The fix would require changes outside the established scope boundary that need re-planning
- `security-review` flags CRITICAL findings introduced by the fix
- The regression test cannot be written (indicates the bug is not well-understood)

---

## Skills Checklist

Before claiming the bug is fixed, confirm every applicable skill was invoked:

- [ ] debug
- [ ] debugging-wizard
- [ ] researcher (if external dependencies involved)
- [ ] expert-analysis (if root cause unclear)
- [ ] analyze (broader context)
- [ ] plan-builder
- [ ] assumptions-audit
- [ ] scope-guard
- [ ] reuse-check
- [ ] the-fool
- [ ] subagent-driven-development
- [ ] dispatching-parallel-agents
- [ ] tdd-workflow (mandatory — regression test required)
- [ ] full-orchestration
- [ ] plan-implementation
- [ ] secure-code-guardian (if security-sensitive)
- [ ] simplify
- [ ] linter
- [ ] tm:update-task
- [ ] test-runner
- [ ] security-review
- [ ] diff-review
- [ ] verification-loop
- [ ] analyze (post-fix)
