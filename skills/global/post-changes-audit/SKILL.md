---
name: post-changes-audit
description: >
  Post-implementation audit that reviews code changes for correctness, performance,
  efficiency, security, and completeness. Auto-triggered by Stop hook or invoked
  manually. Supports three modes: quick (inline checks), standard (2 subagents),
  deep (4 subagents + skills). Use after any implementation task, before committing.
argument-hint: "[quick|standard|deep]"
---

<!-- SYNC: Canonical copy. After editing, copy to ~/Patchy_Bot/skills/global/post-changes-audit/SKILL.md -->

# Post-Changes Audit

Audit code changes made in this session. Three modes, escalating depth and token cost.

## Step 1: Determine Mode

If a mode argument was provided (quick/standard/deep), use it.
If no argument, auto-detect from the Stop hook output or count changes:
```bash
git diff --numstat -- patchy_bot/ | awk '{s+=$1+$2} END {print s+0}'
```
- <5 lines → quick
- 5–49 lines → standard
- 50+ lines → deep

## Step 2: Gather Context

For ALL modes, first run:
```bash
git diff --stat -- patchy_bot/
git diff -- patchy_bot/
```
This is the diff you are auditing.

## Step 3: Execute Audit by Mode

### Quick Mode (~500 tokens)
Run these checks INLINE (no subagents):
1. **Correctness scan** — Read the diff. Are there obvious logic errors, missing returns, broken conditions?
2. **Lint check** — Run `ruff check patchy_bot/` on changed files. Report any new violations.
3. **Domain rules** — Check: type hints on new function signatures? HTML parse mode for new Telegram messages? `_h()` escaping on user text? Callback data uses colon-delimited format? No ⬜ emoji?

### Standard Mode (~2-3K tokens)
Spawn two subagents in sequence:
1. **audit-correctness-agent** — Pass the full diff. Handles correctness, completeness, efficiency, verbosity, code quality.
2. **security-agent** — Pass the full diff. Handles security, input validation, path safety, auth checks.

### Deep Mode (~5-8K tokens)
Spawn four subagents:
1. **audit-correctness-agent** — Correctness, completeness, efficiency, verbosity
2. **security-agent** — Security, input validation, path safety
3. **audit-performance-agent** — Performance, resource use, over-engineering
4. **test-agent** — Identify test coverage gaps for the changes. Suggest specific test cases.

Then run these skills inline:
5. **scope-guard** — Check for scope drift from the original task
6. **diff-review** — Final pre-commit quality gate (debug leftovers, secrets, accidental files)

## Step 4: Consolidate & Report

Collect all findings from subagents and inline checks. Produce this report:

```
━━━ AUDIT REPORT ━━━
Mode: [quick|standard|deep]
Files changed: [count]
Lines changed: [count]

VERDICT: [PASS | CONCERNS | FAIL]

[If CONCERNS or FAIL, list findings in priority order:]

| # | Severity | File:Line | Dimension | Issue | Fix |
|---|----------|-----------|-----------|-------|-----|
| 1 | CRITICAL | store.py:142 | Correctness | Missing null check | Add `if row is None: return []` |
| 2 | HIGH | ... | ... | ... | ... |

Summary: X critical, Y high, Z medium, W low
━━━━━━━━━━━━━━━━━━━
```

**Verdict rules:**
- PASS = 0 critical, 0 high findings
- CONCERNS = 0 critical, 1+ high findings
- FAIL = 1+ critical findings

## Priority Weighting

When reviewing, weight dimensions in this order:
1. Correctness & completeness (logic errors, missing edge cases)
2. Performance & resource use (blocking async, N+1 queries, unclosed resources)
3. Code efficiency & verbosity (over-engineering, unnecessary abstractions)
4. Security & input validation (path traversal, auth bypass, secret exposure)
5. Scope drift (did changes go beyond the original task?)
6. Test coverage gaps (are the changes tested?)
7. Domain rules (Patchy Bot conventions — parity, UI, restart reminder)

## After the Audit

- If FAIL: List the critical findings and stop. Do not proceed until fixed.
- If CONCERNS: Present findings and ask Karson whether to fix now or proceed.
- If PASS: Confirm all clear. Remind to restart `telegram-qbt-bot.service` if any `patchy_bot/` code changed.
