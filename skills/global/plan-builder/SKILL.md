---
name: plan-builder
description: Research-first implementation planner. Use PROACTIVELY before any non-trivial multi-step task, new feature, architecture change, or refactor. Trigger when the task requires planning, scoping, design, implementation strategy, phased rollout, or risk analysis. Produces a durable ExecPlan-style spec. Do not use for direct execution from an already approved plan.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch, Agent
---

# Plan Builder

Produce a durable, restartable implementation plan before code changes begin.

$ARGUMENTS

## Mission
- Turn a fuzzy request into a decision-complete execution spec.
- Ground the work in the actual repo first.
- Use current web research when facts, tools, APIs, versions, security guidance, or best practices could be stale.
- Leave no important decisions to the implementer.

## Required Workflow
1. Identify the real objective, success criteria, audience, scope boundaries, and constraints.
2. Inspect local evidence before asking questions or browsing:
   - relevant files
   - configs
   - tests
   - docs
   - types and schemas
   - entrypoints
   - current git state when relevant
3. If external facts matter, read `/home/karson/.claude/skills/plan-builder/references/research-standards.md` and follow it exactly.
4. Ask only the minimum clarifying questions needed to remove high-impact ambiguity that local evidence cannot resolve.
5. If the task is broad enough to benefit from parallel investigation, use subagents for independent research branches or adversarial review. Do not spawn agents just to look busy.
6. Read `/home/karson/.claude/skills/plan-builder/references/plan-quality-bar.md` before drafting the final artifact.
7. Produce the deliverable using `/home/karson/.claude/skills/plan-builder/references/plan-output-template.md` with the exact section structure unless the host platform makes that impossible.
8. Before sending the result, do a final shape check:
   - emit exactly one final planning artifact
   - include the evidence memo once
   - include the durable plan once
   - suppress extra recap if the user asked for the artifact only

## Output Contract
- The canonical deliverable is a durable ExecPlan-style document, not an informal note.
- Make it self-contained and restartable:
  - a new agent should be able to resume from the plan alone plus the working tree
  - include concrete milestones, validation gates, assumptions, and open risks
  - include enough implementation detail that execution does not require re-planning
- Include explicit execution state:
  - current status
  - milestone checklist
  - decision log
  - surprises or discoveries section for future updates
- **Always return the complete plan directly in the chat. Never write the plan to a file.**
- Do not create `PLANS.md`, `PLAN.md`, or any other file for the plan output.
- Do not save the plan to disk in any form.
- Emit the final artifact once. Do not repeat the memo, the plan, or the whole response in a second pass.
- If the user asked for the final artifact only, do not include process commentary before or after it.

## Decision Rules
- Separate clearly:
  - verified facts
  - inferences
  - unknowns
  - recommendations
- Do not propose implementation steps that depend on unverified external behavior.
- Do not browse until local grounding is complete enough to form targeted queries.
- Do not stop at a high-level sketch if concrete APIs, file touch points, rollout steps, or tests are knowable.
- Do not leave unresolved open questions in the final plan unless they are truly unavoidable. If a decision is needed and you can choose a safe default, choose it and record it.

## Quality Bar
- The plan must be precise enough that `plan-implementation` can execute it without inventing policy.
- The plan must include:
  - the intended user-visible outcome
  - important interfaces, schemas, config surfaces, or operational behaviors that will change
  - failure modes and edge cases worth handling
  - exact validation expectations
  - assumptions and defaults chosen where the user did not decide explicitly

## References
- Read `references/research-standards.md` whenever the task touches anything current, external, version-sensitive, or high-stakes.
- Read `references/plan-quality-bar.md` before finalizing the plan.
- Read `references/plan-output-template.md` when drafting the final plan artifact.

## Inline Skeleton
Use this exact heading order unless the host format prevents it:
- `Verified facts`
- `Inferences`
- `Unknowns`
- `Risks`
- `Sources consulted` when external research materially informed the plan
- `Title`
- `Summary`
- `Current status`
- `Milestones`
- `Implementation details`
- `Validation gates`
- `Decision log`
- `Surprises and discoveries`
- `Assumptions and defaults`
- `Open questions` only if they are truly blocking
