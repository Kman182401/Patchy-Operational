---
name: post-changes-audit
description: >
  Universal post-completion audit orchestrator — run after ANY Claude Code process finishes.
  Triggers on: "audit this", "audit what was done", "post-changes-audit", "/post-changes-audit",
  "review what was done", "post-implementation review", "check everything", "full audit",
  "validate the changes", "is this ready for PR", "final review", "quality gate",
  "sign-off check", "verify the work", "run post-check", "run the audit", "audit the session",
  "post-audit", "what did claude do", "review the session", "check what changed".
  Use after: code implementations, debug sessions, plan executions, agent tasks, swarm
  completions, refactors, infrastructure changes, migrations, installs, or any multi-step
  workflow. Sequences 22 skills across 5 phases: forensic inventory → deep review →
  impact & regression → security & compliance → verdict & paper trail. Read-only by default
  — fixes only applied when explicitly requested. NOT for implementing changes or planning.
argument-hint: "[optional: 'fast' for quick audit, 'fix' to auto-apply fixes, focus path, or ticket ID]"
---

<!-- Upgraded: 2026-04-06 | Focus: full — integrated change-forensics, impact-radar, regression-guard, audit-trail -->

# Post-Changes Audit — Comprehensive Review Orchestration

$ARGUMENTS

Execute a thorough post-implementation audit through five mandatory phases. Read-only by default — findings are reported, not auto-fixed, unless the user explicitly passes `fix` in `$ARGUMENTS` or requests fixes during the session.

**Fast mode:** If `$ARGUMENTS` contains `fast` or `quick`, run only Phases 1, 3, and 5 (Stages 1, 2, 7, 8, 14). Mark report as `[FAST MODE — partial coverage]`.

---

## Phase 1: Forensic Change Inventory

**Goal:** Build a precise, classified inventory of everything that changed — before evaluating quality. Every subsequent phase depends on this inventory. Do not skip or abbreviate.

**Sequential — inventory must be complete before any review begins.**

### Stage 1: `/change-forensics`
Run the forensic change mapping skill. Capture the complete classified inventory:
- All files created, modified, deleted (with `PRIMARY / COLLATERAL / LOCKFILE / GENERATED / CONFIG / TEST / UNEXPECTED` classification)
- Per-file line counts, function/class diffs, import changes, export changes
- Intent vs. reality comparison against the stated task
- Side effect detection (lock file churn, env file touches, binary modifications, out-of-scope mutations)

Store the output as `$FORENSIC_INVENTORY`. Feed the file list and UNEXPECTED items into all subsequent phases.

### Stage 2: `/diff-review`
Run the pre-commit quality gate on the full git diff. Scan added lines for:
- Debug leftovers (`console.log`, `print(`, `breakpoint()`, `debugger`)
- TODO/FIXME/HACK comments introduced
- Commented-out code blocks
- Hardcoded test values in production files
- Leaked secrets or API keys
- Accidental whitespace-only or import-reorder changes

### Stage 3: `/scope-guard`
Compare actual changes against original task scope. Use the UNEXPECTED files from `$FORENSIC_INVENTORY` as primary input. Produce a SCOPE REPORT with drift items and ON TRACK / DRIFTING status.

---

## Phase 2: Deep Multi-Dimensional Review

**Goal:** Evaluate the changes across every quality and correctness dimension.

**Stages 4–7 run in parallel where the environment supports it — they are independent review lenses.**

### Stage 4: `/code-reviewer`
Structured code review across correctness, architecture, performance, maintainability, and test coverage. Produce a categorized report with severity-rated findings.

### Stage 5: `/analyze`
Deep post-completion audit. Check for:
- Functional bugs and incorrect logic
- Incomplete implementation (wired but never called, config added in one place but not another)
- Wrong paths, imports, names, flags, env vars, permissions, or file locations
- Stale or conflicting old configuration left behind
- Missing rollback, retry, timeout, or failure handling
- Unhandled edge cases and missing error checks

### Stage 6: `/expert-analysis`
Evidence-first investigation through security, architecture, operations, and developer experience lenses. Separate verified findings from inferences.

### Stage 7: `/full-orchestration` (verification phase only)
Run the Phase 4 Verification checklist from `full-orchestration`. Confirm no verification step was skipped during implementation. Report which checks were done and which were missed.

**Spawn specialized review agents in parallel (use `/dispatching-parallel-agents`):**
- Always spawn `security-auditor` agent (read-only vulnerability assessment)
- If performance-sensitive code changed → spawn `performance-engineer` agent
- If dependencies changed → spawn `dependency-manager` agent

---

## Phase 3: Impact Analysis & Regression Detection

**Goal:** Determine what else the changes could affect and verify nothing previously working has broken.

**Sequential — impact analysis must complete before regression targeting.**

### Stage 8: `/impact-radar`
Trace the full downstream blast radius of the changes using `$FORENSIC_INVENTORY` as input:
- Reverse dependency trace (what imports/requires the changed modules)
- Test coverage overlap (which tests exercise the changed code)
- API contract change detection (signature changes and their callers)
- Config and environment variable consumer mapping
- Database schema impact assessment
- Impact scoring: Reach × Criticality

Store `Recommended regression targets` from the impact report as `$REGRESSION_TARGETS`.

### Stage 9: `/regression-guard`
Run systematic regression detection using `$REGRESSION_TARGETS` as priority input:
- Execute full test suite; report pass/fail, counts, and failing test names
- Import integrity check (Python imports, TypeScript type check)
- Interface regression check (removed/renamed exports, signature changes)
- Configuration regression check (removed or renamed config keys)
- Targeted smoke tests for HIGH-risk interfaces identified by impact-radar
- Performance check for hot paths

Flag any regression as BLOCKING. Do not proceed to Phase 4 without noting regression status.

---

## Phase 4: Security, Testing & Compliance

**Goal:** Verify security posture, test coverage, and compliance of the changes.

**Stages 10–13 run sequentially — security findings may require targeted re-testing.**

### Stage 10: `/security-review`
Run semgrep, bandit (Python), and manual pattern checks on all changed files. Flag HIGH/CRITICAL findings as blocking. Check for:
- OWASP Top 10 violations
- Hardcoded secrets, API keys, tokens
- SQL injection vectors, XSS risks, unsafe shell usage
- Overly permissive file permissions, debug mode in configs

### Stage 11: `/security-scan`
Broader security scanning: dependency vulnerability audit, secrets detection (gitleaks/trufflehog patterns), permission analysis, and attack surface changes introduced by the diff.

### Stage 12: `/test-runner`
Run the full test suite for all touched modules. Report:
- Total tests / passed / failed / skipped
- Coverage percentage for changed files (target: 80%+)
- Tests added/modified/deleted during the session

### Stage 13: `/linter`
Verify all changed files pass linting. Report remaining style or formatting issues.

### Stage 14: `/verification-loop`
Run the complete verification chain: build → typecheck → lint → test → security scan → diff review. Produce the structured verification report (PASS/FAIL per gate).

---

## Phase 5: Synthesis, Verdict & Paper Trail

**Goal:** Produce a single authoritative verdict and a complete paper trail of the session.

**Sequential — verdict synthesizes all prior findings; trail captures the final state.**

### Stage 15: Findings Synthesis
Collect all findings from Phases 1–4. Deduplicate overlapping findings across skills. Classify every unique finding:
- **BLOCKING** — must fix before merge/deploy (any CRITICAL/HIGH security issue, test failure, build failure, scope violation, regression)
- **WARNING** — should fix, not blocking (MEDIUM findings, missing tests for non-critical paths)
- **OBSERVATION** — informational, no action required

### Stage 16: `/audit-trail`
Generate the complete structured paper trail:
- **Executive Summary** (3–5 sentences, plain language, for a tech lead)
- **Technical Audit Log** (all files changed, issues found, fixes applied, verification results)
- **Commit Message** (Conventional Commits format, copy-pasteable)
- **PR Description** (GitHub/GitLab format with checklist)

If `$ARGUMENTS` contains a ticket ID (e.g., `JIRA-1234`), pass it to `audit-trail` for inclusion in commit footer and PR title.

### Stage 17: Task Tracker Update
Run `/tm:update-task` to update the task tracker with audit results, findings summary, and final verdict.

---

## Audit Verdict Format

After all phases complete, produce this consolidated report:

```
╔══════════════════════════════════════════════════════════════════╗
║              POST-CHANGES AUDIT REPORT                           ║
╠══════════════════════════════════════════════════════════════════╣
║  Task reviewed:    [one-line summary of what was audited]        ║
║  Files changed:    [N files, +X lines / -Y lines]               ║
║  Audit timestamp:  [datetime]                                    ║
╠══════════════════════════════════════════════════════════════════╣

## PHASE RESULTS

| Phase | Stage              | Status      | Key Findings              |
|-------|--------------------|-------------|---------------------------|
| 1     | Change Forensics   | ✅ / ⚠️ / 🚫 | N files, M unexpected     |
| 1     | Diff Review        | ✅ / ⚠️ / 🚫 | [summary]                 |
| 1     | Scope Guard        | ✅ / ⚠️ / 🚫 | ON TRACK / DRIFTING       |
| 2     | Code Review        | ✅ / ⚠️ / 🚫 | [summary]                 |
| 2     | Deep Analyze       | ✅ / ⚠️ / 🚫 | [summary]                 |
| 2     | Expert Analysis    | ✅ / ⚠️ / 🚫 | [summary]                 |
| 3     | Impact Radar       | ✅ / ⚠️ / 🚫 | Blast radius: N files     |
| 3     | Regression Guard   | ✅ / ⚠️ / 🚫 | N tests / CLEAN / REGRESS |
| 4     | Security Review    | ✅ / ⚠️ / 🚫 | X critical, Y high        |
| 4     | Security Scan      | ✅ / ⚠️ / 🚫 | [summary]                 |
| 4     | Test Runner        | ✅ / ⚠️ / 🚫 | N/M passed, X% coverage   |
| 4     | Linter             | ✅ / ⚠️ / 🚫 | CLEAN / N issues          |
| 4     | Verification Loop  | ✅ / ⚠️ / 🚫 | Build/Type/Lint/Test gates|

## BLOCKING ISSUES (must fix before merge/deploy)
[Numbered list with file:line, severity, and recommended fix — or "None found"]

## WARNINGS (review recommended, not blocking)
[Numbered list — or "None found"]

## OBSERVATIONS (informational)
[Numbered list — or "None"]

## FIXES APPLIED (only in fix mode)
[List of changes made during this audit — or "Read-only mode: no fixes applied"]

## REMAINING RISKS
[Honest assessment of what could not be fully verified]

╠══════════════════════════════════════════════════════════════════╣
║  VERDICT:  ✅ APPROVED | ⚠️ APPROVED WITH CONDITIONS | 🚫 BLOCKED ║
║  [One sentence explaining the verdict]                           ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Verdict Decision Rules

- **✅ APPROVED** — Zero BLOCKING issues. Tests pass. Lint clean. Build succeeds. Scope compliant. No regressions.
- **⚠️ APPROVED WITH CONDITIONS** — Zero BLOCKING issues. 1–3 warnings with clear fixes. Conditions listed explicitly. Safe to merge after addressing conditions.
- **🚫 BLOCKED** — Any CRITICAL/HIGH security finding. Test failures. Build failure. Significant scope violations. Regressions detected. Do not merge until resolved.

---

## Read-Only vs. Fix Mode

**Default: read-only.** Findings are reported, not auto-applied.

Activate fix mode when `$ARGUMENTS` contains `fix`, `auto-fix`, or `fix and report`:
- Apply fixes for WARN severity and below automatically
- Report every fix applied (file, line, what changed)
- Re-run verification after fixes
- **Never auto-fix CRITICAL or HIGH** — present each to the user and require explicit approval before applying

---

## Skills Checklist

Confirm every applicable stage was executed before delivering the verdict:

**Phase 1 — Forensic Inventory**
- [ ] change-forensics
- [ ] diff-review
- [ ] scope-guard

**Phase 2 — Deep Review**
- [ ] code-reviewer
- [ ] analyze
- [ ] expert-analysis
- [ ] full-orchestration (verification phase)
- [ ] security-auditor agent (spawned)
- [ ] performance-engineer agent (if applicable)
- [ ] dependency-manager agent (if applicable)

**Phase 3 — Impact & Regression**
- [ ] impact-radar
- [ ] regression-guard

**Phase 4 — Security & Compliance**
- [ ] security-review
- [ ] security-scan
- [ ] test-runner
- [ ] linter
- [ ] verification-loop

**Phase 5 — Synthesis & Trail**
- [ ] findings synthesis
- [ ] audit-trail
- [ ] tm:update-task
