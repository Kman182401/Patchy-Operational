---
name: assumptions-audit
description: This skill should be used when the user asks to "check my assumptions", "what am I assuming", "assumptions audit", "verify assumptions", "assumption check", "what are the risks", or needs implicit assumptions surfaced. Also trigger proactively during planning phases, before executing approved plans, and when making architectural or design decisions.
---

# Assumptions Audit

Systematically extract, categorize, and risk-rate every assumption embedded in a plan, proposal, or discussion before it becomes a silent failure mode.

## Purpose

Make implicit assumptions explicit so they can be verified before they cause problems. Most failures trace back to something taken for granted that turned out to be false. This skill catches those before execution begins.

Complements the-fool (which challenges the approach itself) by tracking what is being taken for granted underneath the approach. The-fool asks "is this the right idea?" -- assumptions-audit asks "what must be true for this idea to work?"

## When to Trigger

- During plan creation (pair with plan-builder)
- Before executing an approved plan (pair with plan-implementation)
- When making architectural or design decisions
- When the user explicitly asks to audit assumptions
- When a plan depends on external systems, APIs, or services
- When working in unfamiliar codebases or with unfamiliar tools

## Core Workflow

### Step 1: Extract Assumptions

Mine the current plan, discussion, or proposal for every assumption -- stated or implied. Scan for:

**Technical assumptions:**
- "This API/library/function exists and works as expected"
- "This file/module has this structure"
- "This dependency is installed and at this version"
- "This service is running and accessible"
- "This language feature or syntax is supported in the target version"
- "This tool is installed and on PATH"

**Environmental assumptions:**
- "The user has these permissions (root, sudo, file ownership)"
- "This path exists and is writable"
- "This port is available and not firewalled"
- "This config value is set correctly"
- "This OS/kernel/shell version supports this feature"
- "Sufficient disk space, memory, or CPU is available"

**Behavioral assumptions:**
- "This function returns this type/shape"
- "This error is handled upstream"
- "This data is always in this format"
- "This operation is idempotent/atomic/thread-safe"
- "This process completes within a reasonable time"
- "This library handles edge cases (nulls, empty strings, Unicode)"

**Scope assumptions:**
- "This change won't affect other parts of the system"
- "No other process reads from or writes to this file/table"
- "The database schema won't change during implementation"
- "Backwards compatibility isn't needed"
- "No migration or rollback path is required"
- "Downstream consumers won't break"

**Ordering and timing assumptions:**
- "This runs before that"
- "This lock is released before the next call"
- "This event fires exactly once"
- "These steps can run in parallel safely"

### Step 2: Classify Each Assumption

Assign every extracted assumption one of four confidence levels:

| Level | Meaning | Evidence Required |
|-------|---------|-------------------|
| **Verified** | Read the file, ran the command, checked the docs this session | Cite the specific evidence (file path, command output, doc URL) |
| **High confidence** | Stable, well-known behavior unlikely to have changed | Note why it is stable (e.g., "POSIX standard", "unchanged since v2.0") |
| **Unverified** | Have not checked yet but low blast radius if wrong | Flag for verification; proceed with caution |
| **Risky** | Unverified AND high impact if wrong | Must verify before proceeding; block execution on this |

Classification rules:
- Default to **Unverified**, not High confidence. Optimism is the enemy.
- Anything involving versions, external APIs, or network services starts as **Unverified** at best.
- Anything the plan depends on critically (would require a full redesign if wrong) is **Risky** until verified.
- "I've always seen it work this way" is not verification. Run the check.

### Step 3: Generate Verification Actions

For every Unverified and Risky assumption, produce a concrete verification action:

- **File existence/structure:** `Read the file at [path]` or `ls [path]`
- **Dependency version:** `pip show [pkg]`, `node -e "require('[pkg]/package.json').version"`, etc.
- **Service availability:** `curl -s [endpoint]`, `systemctl status [service]`
- **Permission check:** `ls -la [path]`, `id`, `sudo -l`
- **Port availability:** `ss -tlnp | grep [port]`
- **Config value:** `grep [key] [config-file]`
- **API behavior:** Read the current docs, run a test request
- **Function signature/return type:** Read the source file or type definitions

Do not produce vague actions like "check the docs" -- specify which doc, which section, or which command to run.

### Step 4: Assess Risk

Score the overall risk profile:

- **Green** -- All critical assumptions verified; unverified assumptions are low-impact. Safe to proceed.
- **Yellow** -- Some unverified assumptions with moderate impact. Proceed but verify during early steps; build in checkpoints.
- **Red** -- Risky assumptions remain unverified. Do not proceed until resolved. Specify which assumptions block execution.

### Step 5: Produce Output

## Output Format

Present findings in this structure:

```
## Assumptions Audit

### Summary
[One-line risk assessment: Green/Yellow/Red + reason]

### Assumption Table

| # | Category | Assumption | Status | Impact if Wrong | Evidence/Action |
|---|----------|-----------|--------|-----------------|-----------------|
| 1 | Technical | pandas >= 2.0 is installed | Verified | High | `pip show pandas` returned 2.1.4 |
| 2 | Environmental | /opt/data/ is writable | Unverified | Medium | Run: `test -w /opt/data/ && echo ok` |
| 3 | Behavioral | API returns JSON, not XML | Risky | High -- redesign parser | Read: current API docs at [url] |
| 4 | Scope | Migration is backwards-compatible | Unverified | High | Check: consumer contracts |

### Verification Queue (ordered by risk)
1. [Risky] #3 — Check API response format: `curl -s [endpoint] | head -c 200`
2. [Unverified] #4 — Review consumer contracts in [file]
3. [Unverified] #2 — Test write permissions: `test -w /opt/data/`

### Risk Assessment
[Which unverified assumptions could derail the work and why]

### Recommendation
[Proceed / Verify first / Reconsider approach]
```

## Integration Points

- **plan-builder:** Run assumptions-audit on the draft plan before finalizing. Assumptions become plan prerequisites. Risky assumptions become open questions or blockers.
- **plan-implementation:** Run assumptions-audit before executing an approved plan. Verify assumptions that may have gone stale since planning.
- **the-fool:** Feed verified assumptions to the-fool for deeper challenge. The-fool may question whether a "verified" assumption is actually relevant or sufficient.
- **scope-guard:** Scope assumptions from the audit become explicit guardrails. If the audit says "this change won't affect module X," scope-guard enforces that boundary.
- **verification-loop:** Verification actions from the audit feed directly into verification-loop checkpoints.

## Constraints

### MUST DO
- Extract at least 5 assumptions from any non-trivial plan (there are always more than zero)
- Classify every assumption -- no "unclassified" items
- Provide concrete, runnable verification actions for every Unverified and Risky item
- Order the verification queue by risk (highest first)
- Cite evidence for every Verified assumption (file path, command output, or doc link)
- Re-run the audit if the plan changes significantly after initial audit

### MUST NOT DO
- Assume "obvious" things are verified -- check them
- Produce vague verification actions ("look into it", "check the docs")
- Skip the risk assessment or recommendation
- Mark something Verified without evidence from this session
- Treat High confidence as Verified -- they are different levels
- Let Risky assumptions pass without flagging them as execution blockers
