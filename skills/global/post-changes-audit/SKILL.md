---
name: post-changes-audit
description: >
  Universal post-completion audit skill — run after ANY Claude Code process finishes.
  Use after: code implementations (/code-changes), debug sessions (/debug-fix), plan
  executions, agent tasks, swarm completions, refactors, infrastructure changes, or any
  multi-step workflow. Also triggers on: "audit this", "review what was done",
  "post-implementation review", "check everything", "full audit", "validate the changes",
  "is this ready for PR", "final review", "quality gate", "sign-off check",
  "post-changes audit", "/post-changes-audit", "verify the work", "run post-check".
  Sequences 18+ skills across 4 phases: inventory → deep review → security & compliance
  → verdict. Read-only by default — fixes only applied when explicitly requested.
  NOT for implementing changes (use /code-changes) or planning (use /read-only-plans).
---

# Post-Changes Audit — Comprehensive Review Orchestration

$ARGUMENTS

Execute a thorough post-implementation audit through four mandatory phases. This audit is read-only by default — findings are reported, not auto-fixed, unless the user explicitly requests fixes.

---

## Phase 1: Change Inventory

**Goal:** Understand exactly what changed before evaluating quality.

**Sequential — inventory must be complete before review begins.**

1. **`/diff-review`** — Capture and scan the full git diff. Identify all changed files, added/removed lines, and flag debug leftovers, accidental changes, leaked secrets, and scope violations. Produce the initial change inventory.
2. **`/scope-guard`** — Compare the actual changes against the original task scope. Flag any files or modules modified outside the stated scope. Determine if scope violations are intentional or accidental.
3. **`/assumptions-audit`** — Extract and verify assumptions embedded in the implementation. Check that pre-implementation assumptions still hold. Identify any new assumptions introduced by the changes.

---

## Phase 2: Deep Multi-Dimensional Review

**Goal:** Evaluate the changes across every quality dimension.

**Parallel where possible — these are independent review lenses.**

4. **`/code-reviewer`** — Structured code review across correctness, architecture, performance, maintainability, and test coverage. Produce a categorized report with severity-rated findings.
5. **`/analyze`** — Deep post-completion review. Check for functional bugs, incomplete implementation, broken integration, wrong paths/imports/names, stale config, missing error handling, and unhandled edge cases.
6. **`/expert-analysis`** — Evidence-first investigation of the changes through security, architecture, operations, and developer experience lenses. Separate verified findings from inferences.
7. **`/full-orchestration`** — Run the Phase 4 (Verification) checklist from full-orchestration. Ensure no verification step was missed during implementation.

**Spawn specialized review agents in parallel:**
- Spawn `security-auditor` agent — read-only vulnerability assessment
- If performance-sensitive code was changed → spawn `performance-engineer` agent
- If dependencies were changed → spawn `dependency-manager` agent

8. **`/subagent-driven-development`** — Coordinate review agent dispatch.
9. **`/dispatching-parallel-agents`** — Run independent review agents in parallel for maximum coverage.

---

## Phase 3: Security, Testing & Compliance

**Goal:** Verify security posture and test coverage of the changes.

**Sequential — security findings may require re-testing.**

10. **`/security-review`** — Run semgrep, bandit, and manual pattern checks on all changed files. Flag HIGH/CRITICAL issues as blocking. Check for OWASP Top 10 violations.
11. **`/security-scan`** — Broader security scanning beyond code review: dependency vulnerabilities, secrets detection, permission analysis, and attack surface assessment.
12. **`/test-runner`** — Run the full test suite for all touched modules. Report pass/fail status, coverage percentage, and any tests that were added/modified/deleted.
13. **`/linter`** — Verify all changed files pass linting. Report any remaining style or formatting issues.
14. **`/verification-loop`** — Run the complete verification chain: build → typecheck → lint → test → security scan → diff review. Produce a structured verification report.

---

## Phase 4: Synthesis & Verdict

**Goal:** Produce a single, authoritative audit verdict.

**Sequential — verdict synthesizes all previous findings.**

15. **`/researcher`** — If any findings reference external standards, CVEs, or best practices, verify them against current sources. Ensure recommendations are based on up-to-date information.
16. **`/using-superpowers`** — Leverage any additional plugin skills (brainstorming, verification, code review superpowers) that add value to the final assessment.

**Task manager checkpoint:**
17. **`/tm:update-task`** — Update task tracker with audit results, findings summary, and verdict.

---

## Audit Verdict Format

After all phases complete, produce a final verdict using this structure:

```
## Audit Verdict

**Changes reviewed:** [summary of what was audited]
**Scope compliance:** PASS | WARN | FAIL
**Test coverage:** X% (target: 80%+)
**Security findings:** X critical, X high, X medium, X low
**Lint status:** CLEAN | X issues remaining
**Build status:** PASS | FAIL

### Critical Findings (must fix before merge)
- [finding 1 — severity, location, recommended fix]

### Warnings (should fix, not blocking)
- [finding 1 — severity, location, recommended fix]

### Observations (informational)
- [finding 1 — context]

### Verdict: APPROVED | APPROVED WITH CONDITIONS | BLOCKED

**Blocking conditions:** [if any]
**Recommended follow-up:** [if any]
```

---

## Verdict Decision Rules

- **APPROVED** — No critical/high findings. Tests pass. Lint clean. Build succeeds. Scope compliant.
- **APPROVED WITH CONDITIONS** — No critical findings. 1-3 high findings that have clear fixes. Tests pass. Conditions listed explicitly.
- **BLOCKED** — Any critical findings. Test failures. Build failures. Significant scope violations. Security blockers.

---

## Read-Only vs Fix Mode

By default, this audit is **read-only** — findings are reported, not auto-fixed.

If the user says "fix what you find", "auto-fix", or "fix and report":
- Apply fixes for WARN and below severity
- Report fixes applied
- Re-run verification after fixes
- Do NOT auto-fix CRITICAL or HIGH without explicit user approval per finding

---

## Skills Checklist

Before delivering the audit verdict, confirm every applicable skill was invoked:

- [ ] diff-review
- [ ] scope-guard
- [ ] assumptions-audit
- [ ] code-reviewer
- [ ] analyze
- [ ] expert-analysis
- [ ] full-orchestration (verification phase)
- [ ] subagent-driven-development
- [ ] dispatching-parallel-agents
- [ ] security-review
- [ ] security-scan
- [ ] test-runner
- [ ] linter
- [ ] verification-loop
- [ ] researcher (if external references needed)
- [ ] using-superpowers
- [ ] tm:update-task
