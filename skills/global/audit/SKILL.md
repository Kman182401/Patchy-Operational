---
name: audit
description: Run a deep, professional, read-only audit of a repo, service, system, config set, bot, workflow, or prompt system and return a structured findings report directly in chat. Use when the user explicitly asks for a full audit, assessment, review, or health/security/reliability analysis.
argument-hint: "[target to audit]"
context: fork
agent: Plan
effort: high
---

# Audit

Run a **hyper in-depth, expert-level, professional-grade, elite audit** of the target below and return the full report **in chat**.

## Target

$ARGUMENTS

## Core operating mode

This is a **read-only audit**.

You must:
- inspect thoroughly
- reason carefully
- prioritize evidence over guesses
- surface concrete risks, weaknesses, broken assumptions, and improvement opportunities
- return the full audit directly in the chat

You must **not**:
- create a plan file
- create a report file
- write findings to disk
- modify code
- edit configs
- install packages
- run destructive commands
- make external changes
- claim certainty when evidence is incomplete

If a command could change state, do **not** run it.

Use **ultrathink** before finalizing conclusions.

## Scope resolution rules

1. Treat the argument as the target audit scope.
2. If the argument is a path, repo, service name, directory, file set, or component name, audit that target directly.
3. If the argument is a plain-language system description, map it to the most likely local target using the current working context and any directly relevant project files.
4. If the target is broader than can be fully audited in one pass, prioritize the highest-risk and highest-impact areas first, then clearly state what was and was not inspected.
5. If the target is underspecified but still auditable, state the assumption and proceed instead of stalling.

## Audit objectives

Your job is to identify:
- correctness issues
- logic flaws
- architectural weaknesses
- fragile assumptions
- edge cases
- reliability risks
- security issues
- secrets handling problems
- auth/authz weaknesses
- unsafe defaults
- configuration mistakes
- operational hazards
- performance bottlenecks
- concurrency or state risks
- observability gaps
- test gaps
- maintainability problems
- upgrade and deployment risks
- documentation or runbook gaps

## Required audit workflow

Follow this sequence:

### 1. Establish context
Determine:
- what the target is
- what it appears to do
- its major components
- likely runtime boundaries
- likely trust boundaries
- where the highest-risk surfaces are

### 2. Inventory the target
Inspect the most relevant:
- entrypoints
- configs
- scripts
- dependencies
- environment assumptions
- process boundaries
- storage and network touchpoints
- auth/session/token handling
- secrets and credentials handling
- logging and error handling
- tests
- docs and operational notes

### 3. Audit by category
Check the target across these categories:

#### A. Correctness and logic
Look for:
- broken logic
- missing branches
- impossible assumptions
- silent failure modes
- invalid state transitions
- bad parsing
- brittle conditionals
- dangerous fallback behavior

#### B. Security
Look for:
- hardcoded secrets
- unsafe secret loading
- privilege escalation paths
- missing input validation
- unsafe shell usage
- injection risk
- insecure file permissions
- weak auth/authz checks
- token/session leakage
- logging of sensitive data
- dangerous network exposure
- dependency risk visible from project state
- insecure default settings

#### C. Reliability and resilience
Look for:
- no retries where needed
- retries without backoff
- no timeout limits
- unbounded loops
- race conditions
- queue/backpressure issues
- brittle external dependency handling
- poor crash recovery
- no graceful degradation
- state corruption risks

#### D. Performance and efficiency
Look for:
- obviously wasteful hot paths
- repeated expensive work
- unnecessary polling
- unbounded memory growth
- needless subprocess spawning
- bad I/O patterns
- expensive startup paths
- scaling bottlenecks

#### E. Operability and observability
Look for:
- weak logs
- missing structured logging
- poor metrics coverage
- no health checks
- poor alerting hooks
- weak debugging ergonomics
- hidden failure signals
- unclear run procedures

#### F. Maintainability
Look for:
- over-complex structure
- tightly coupled modules
- duplicated logic
- magic constants
- hidden configuration
- weak naming
- unclear ownership boundaries
- undocumented assumptions

#### G. Validation and testing
Look for:
- no tests for critical paths
- missing negative tests
- missing edge-case tests
- missing regression coverage
- mismatch between implementation and documented behavior
- no validation of risky config combinations

### 4. Stress the edges mentally
Actively search for:
- “what happens if this input is empty?”
- “what happens if this service is slow?”
- “what happens if this file is missing?”
- “what happens if state is partially written?”
- “what happens if a retry overlaps another run?”
- “what happens if logs or metrics are unavailable?”
- “what happens if an attacker controls this input?”
- “what happens if a dependency returns malformed output?”

### 5. Rank findings
Assign each issue one of:
- Critical
- High
- Medium
- Low
- Info

Use severity based on real impact, exploitability, blast radius, and likelihood.

### 6. Tie every major claim to evidence
For each meaningful finding, include concrete evidence such as:
- file paths
- function/class names
- config keys
- command output
- log excerpts
- exact behavioral reasoning

Do not make unsupported claims.

### 7. Produce actionable fixes
For every finding, give a practical fix direction.
Prefer:
- exact change area
- what should be changed
- why that change helps
- priority level

Do not write the fix unless the user explicitly asks for implementation.

## Output format

Return the audit **directly in chat** using this structure:

# Audit Report — <target>

## Executive Summary
- 3 to 7 bullets
- overall health/risk posture
- biggest problems
- biggest strengths if relevant

## Scope and Assumptions
- what you audited
- what you did not audit
- any assumptions you had to make

## Method
- brief summary of how you inspected the target

## Findings Summary
- Critical: <count>
- High: <count>
- Medium: <count>
- Low: <count>
- Info: <count>

## Detailed Findings

For each finding, use this exact format:

### [Severity] <short finding title>
**Area:** <security / reliability / performance / etc.>  
**Confidence:** <high / medium / low>  
**Evidence:** <specific evidence with paths, symbols, config names, command output, or behavioral reasoning>  
**Why it matters:** <impact in plain language>  
**Recommended fix:** <clear corrective action>  

Repeat for every significant finding.

## Priority Actions
### Do first
- highest-value immediate actions

### Do next
- medium-term actions

### Do later
- lower-priority structural improvements

## Unknowns and Blind Spots
- what could not be verified
- what would need more access, runtime data, or testing

## Final Verdict
- 1 short paragraph
- direct, honest bottom line

## Report quality rules

- Be direct and evidence-driven.
- Do not pad the report with filler.
- Do not invent issues to make the audit look bigger.
- If the target is in good shape, say so clearly.
- If evidence is partial, explicitly label uncertainty.
- Prefer precise statements over dramatic wording.
- Explain impact in plain language.
- Keep the report useful to an operator or developer.

## Hard constraints

- **Do not create `PLAN.md`, `REPORT.md`, `AUDIT.md`, or any other file for the output.**
- **Do not write the report to disk.**
- **Return the full report in the chat only.**
- **Do not modify anything unless the user separately asks for fixes.**

## Success criteria

The audit is only complete if:
- the scope is clear
- the highest-risk areas were inspected first
- findings are ranked by severity
- major claims are tied to evidence
- fixes are actionable
- unknowns are stated honestly
- the final output is entirely in chat
