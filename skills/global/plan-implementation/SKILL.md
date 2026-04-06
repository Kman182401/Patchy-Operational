---
name: plan-implementation
description: Execute an already approved plan, report, analysis, or set of next steps from a prior planning process. Use after /plan-builder, /audit, /expert-analysis, /analyze, or any conversation that produced a plan, report with recommendations, next steps, or action items that the user wants carried out. Do not use to invent the plan from a vague goal.
effort: high
---

# Plan Implementation

Execute an approved plan end-to-end without re-planning the task from scratch.

$ARGUMENTS

## Mission
- Consume a plan, report, analysis, or set of action items from the current conversation or from `$ARGUMENTS` and carry it through implementation, verification, and reporting.
- Re-ground locally before changing files.
- Re-check current external facts when the plan depends on libraries, APIs, standards, or practices that may have changed.
- Maintain execution discipline so the plan remains the contract.

## Required Preconditions
- Start only when there is an approved, sufficiently detailed source of work to execute. Valid sources include:
  - a plan produced by `/plan-builder` earlier in the conversation
  - a report or findings from `/audit`, `/expert-analysis`, or `/analyze` with actionable recommendations
  - a set of next steps, action items, or prioritized fixes from any prior conversation output
  - a user-provided written spec, checklist, or detailed instructions passed as `$ARGUMENTS`
- The plan does **not** need to be saved to a file. Plans delivered in the chat are the expected input.
- If the user gives only a fuzzy goal with no prior plan or actionable output to execute, redirect to `/plan-builder` instead of silently inventing the plan.

## Required Workflow
1. Locate the plan to execute. Check in order:
   - `$ARGUMENTS` if the user provided inline instructions or a plan reference
   - the most recent plan, report, or action-item list from the current conversation (from `/plan-builder`, `/audit`, `/expert-analysis`, `/analyze`, or equivalent)
   - if nothing is found, ask the user what to execute rather than guessing
2. Read the plan carefully and identify the intended milestones, constraints, and validation gates.
3. Re-ground in local repo truth before editing:
   - relevant files
   - tests
   - docs
   - configs
   - current diffs and local state
4. Read `/home/karson/.claude/skills/plan-implementation/references/execution-playbook.md` before starting mutations.
5. If the task touches stale or external facts, do current web research before acting on them.
6. Execute the plan milestone by milestone.
7. Use delegation only under the rules in `references/delegation-and-review.md`.
8. Verify the work under `references/verification-gates.md` before claiming success.

## Execution Rules
- Follow the plan. Do not quietly substitute a different design unless new evidence forces a change.
- If new evidence invalidates the plan, stop, record the mismatch, and revise the plan explicitly before continuing.
- Prefer minimal, coherent diffs that satisfy the plan.
- Do not ask for "next steps" after every small milestone when the approved plan already answers that.

## Verification Standard
- Verification is part of execution, not a final garnish.
- Run the relevant tests, checks, builds, or repro steps that the plan requires.
- For Python changes, run `pytest -q` for touched modules if tests exist.
- Report exactly what was verified and what was not.

## References
- Read `references/execution-playbook.md` at the start of execution.
- Read `references/delegation-and-review.md` before spawning subagents.
- Read `references/verification-gates.md` before finalizing.
