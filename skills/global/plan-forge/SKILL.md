---
name: plan-forge
description: >
  Transforms raw project input — notes, brain dumps, to-do lists, ideas, bug reports,
  issues, rough outlines — into a complete, Claude Code-ready implementation plan.
  Use when the user says "plan this", "build a plan for", "help me plan", "here are my
  notes", "I have some ideas", "I want to fix this bug", "here's my to-do list",
  "create an implementation plan", "turn this into a plan", "I need a Claude Code prompt",
  "forge a plan", or pastes raw project material and wants it structured.
  NOT for general code writing, chat, or analysis without a planning goal.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, Agent, WebSearch, WebFetch
---

# Plan Forge

Transform any raw project input into a zero-ambiguity Claude Code implementation plan.

$ARGUMENTS

**The pipeline:** Intake → File Audit (if provided) → Deep Interview → Analysis → Plan Construction → Deliverables.

-----

## What This Skill Does

Takes messy, incomplete, or informal project material — notes, ideas, bug reports, to-do lists, rough outlines — and turns it into two things:

1. **A plain-English summary** (inline in chat) — so the user can fully understand what the plan does and how it will change their system before Claude Code touches a single file.
2. **A Claude Code implementation plan** (inline in chat) — a hyper-specific, spec-driven prompt document built to the latest 2026 Claude Code best practices, ready to hand directly to a fresh Claude Code session for execution.

-----

## Phase 1: Intake

When this skill is triggered, immediately read all input provided. This includes:

- Pasted notes, ideas, brain dumps, to-do lists
- Bug reports or issue descriptions
- Referenced project files (code, configs, docs, CLAUDE.md, etc.)
- Any combination of the above

Identify:

- **Project name / context** (infer if not stated)
- **Input type(s):** notes / todos / bugs / ideas / partial plan
- **Apparent goal:** what the user seems to want to achieve
- **Gaps:** what is unclear, missing, or potentially ambiguous

Do not begin the interview until intake is complete. If no input is provided at all, ask the user to share their notes, ideas, or project material before proceeding.

-----

## Phase 2: File Audit (if project files are provided)

If the user has referenced project files or you are working within a project directory, run a full audit before the interview. This ensures interview questions are informed and specific rather than generic.

### Full Audit Checklist

Analyze every relevant file for:

**Structure & Architecture**

- Directory layout and organization patterns
- Module/component relationships and dependencies
- Entry points, main files, config files

**Code Quality**

- Naming conventions and consistency
- Code style and formatting patterns
- Dead code, TODOs, FIXMEs, commented-out blocks
- Error handling patterns (or lack thereof)
- Repeated logic that could be abstracted

**Issues & Patterns**

- Obvious bugs or logic errors visible in the code
- Inconsistent patterns across files
- Missing tests or test coverage gaps
- Security concerns (hardcoded secrets, unsafe inputs, etc.)
- Performance bottlenecks or inefficiencies

**Existing Context**

- CLAUDE.md contents (if present) — note all rules, conventions, agent setup
- README or docs — understand stated intent
- Package/dependency files — identify tech stack exactly

Produce an internal audit summary. Use it to:

- Ask sharper, more specific interview questions
- Avoid assumptions about things the code already answers
- Identify issues the user may not have mentioned

-----

## Phase 3: Deep Interview

This is the most important phase. The goal is to eliminate every gap, ambiguity, and assumption before building the plan. **There is no question limit. Ask as many as needed.**

### Interview Structure

Run the interview in rounds. Each round goes deeper.

**Round 1 — Clarify the Core**

- What is the end goal of this work? What does "done" look like?
- What is the scope? (single file fix / feature / full refactor / new system)
- Are there things that must NOT be changed or touched?
- What is the tech stack and runtime environment?
- Does this need to work with existing code, or is it greenfield?

**Round 2 — Dig Into the Details**

Based on Round 1 answers and the file audit, ask about:

- Specific behaviors: exact inputs, expected outputs, edge cases
- Integration points: what does this touch / connect to / depend on?
- Error handling: what should happen when things go wrong?
- For bugs: what exactly is the broken behavior vs. expected behavior? When does it happen?
- For features: what does the user experience / output look like?
- For refactors: what is the current pain point, and what does "better" mean?

**Round 3 — Validation & Constraints**

- How should success be verified? (tests, manual checks, logs, output format)
- Are there performance, security, or compatibility constraints?
- Should Claude Code commit changes? Create branches? Follow specific git conventions?
- Are there existing patterns in the codebase that must be followed?
- Any external dependencies, APIs, or services involved?

**Round 4+ — Fill Every Gap**

After each round, review what has been said and identify anything still unclear. Keep asking until:

- No assumptions remain
- Every edge case is covered
- The plan could be handed to a developer with zero additional context and they would know exactly what to build

**Interview Principles**

- Never guess. If something is unclear, ask.
- Ask one focused question at a time, or group tightly related questions.
- Reference the file audit when asking — "I noticed your code does X, should the new behavior also do X or change that?"
- Confirm understanding before moving forward: "So what I'm hearing is... Is that right?"

-----

## Phase 4: Analysis

Once the interview is complete, synthesize everything:

1. **Restate the goal** in one clear sentence
2. **List all changes** that will be made, in order
3. **Map dependencies** — what touches what
4. **Identify risks** — what could go wrong during implementation
5. **Define success criteria** — exactly how to verify the plan succeeded
6. **Note constraints** — things Claude Code must not do or must follow

This analysis feeds directly into both deliverables.

-----

## Phase 5: Build the Deliverables

Produce both outputs in sequence.

-----

### Deliverable 1: Plain-English Summary (inline in chat)

Before writing this deliverable, read the reference guide at:
`/home/karson/.claude/skills/plan-forge/references/summary-writing-guide.md`

Follow all guidance in that reference file. Write this directly in chat. Assume zero technical context required.

**Required sections:**

**What This Plan Achieves**
One paragraph. Plain English. What will be different when this is done?

**What Will Change**
List every change that will be made. For each:

- What file/component/system is affected
- What it does now vs. what it will do after

**How This Affects the System**
Describe the ripple effects. What behaviors will users/systems notice? What will stop happening? What will start happening?

**How to Know It Worked**
Plain-language success criteria. "You'll know it worked when..."

**Things to Be Aware Of**
Any risks, gotchas, or things to watch for during or after implementation.

-----

### Deliverable 2: Claude Code Implementation Plan (inline in chat)

Before writing this deliverable, read the reference guide at:
`/home/karson/.claude/skills/plan-forge/references/plan-writing-guide.md`

Follow all guidance in that reference file. Present the full plan inline in chat using this structure:

```markdown
# [Project Name] — Implementation Plan
_Generated: [date] | Target: Claude Code_

## Context & Background
[Project overview, tech stack, relevant CLAUDE.md rules if present,
 key architectural patterns Claude Code must follow]

## Objective
[Single clear sentence stating what this plan accomplishes]

## Scope
**In scope:**
- [Explicit list of what will be changed]

**Out of scope (do not touch):**
- [Explicit list of what must not be modified]

## Pre-Implementation Audit
[Instruct Claude Code to read specific files before starting.
 Example: "Before beginning, read: src/quality.py, tests/test_quality.py,
 CLAUDE.md. Understand the existing patterns before changing anything."]

## Implementation Tasks

### Task 1: [Descriptive Name]
**File(s):** `path/to/file.py`
**What to do:** [Exact description of the change]
**Current behavior:** [What the code does now]
**Required behavior:** [What it must do after]
**Constraints:** [Must follow existing pattern X / must not break Y]
**Verification:** [How to confirm this task succeeded]

### Task 2: [Descriptive Name]
[Same structure]

[...continue for all tasks...]

## Verification & Testing
[Exact commands to run. Exact outputs to check. Exact tests to pass.
 Example: "Run `pytest tests/test_quality.py -v`. All tests must pass."]

## Success Criteria
The plan is complete when:
- [ ] [Checkable criterion 1]
- [ ] [Checkable criterion 2]
- [ ] [All tests pass]
- [ ] [Specific output matches expected]

## Notes & Warnings
[Edge cases, gotchas, things Claude Code must watch for]
[Any patterns that must be preserved]
[Any anti-patterns to avoid]
```

**Plan writing rules:**

- Be explicit about file paths — never say "the main file," say `src/quality.py`
- Reference existing patterns by name — "follow the same pattern as `_score_resolution()`"
- Break work into atomic tasks — each task should be independently verifiable
- Every task has a verification step
- Never leave anything open to interpretation — if there's a choice, make it in the plan
- Include the tech stack, Python/Node/etc. version if known
- If CLAUDE.md exists for the project, reference its rules explicitly in the plan
- Scope the context: tell Claude Code exactly which files to read before starting
- Add a "do not touch" section for anything that must be preserved

-----

## Phase 6: Deliver

1. Present the plain-English summary inline (Deliverable 1)
2. Present the full implementation plan inline (Deliverable 2)
3. Say: **"Copy the implementation plan above into a fresh Claude Code session. It contains everything needed to implement this plan without any additional prompting."**

-----

## Edge Cases

- **No files provided:** Run the full interview, build the plan from interview answers alone. Note in the plan that Claude Code should run its own file audit at the start.
- **Bug report only:** Interview must establish exact reproduction steps, expected behavior, current behavior, and affected files before planning.
- **Large project with many files:** Prioritize reading CLAUDE.md, main entry points, and files directly related to the stated goal.
- **User wants to skip questions:** Acknowledge the preference but explain that gaps in the plan lead to wrong implementations. Offer to consolidate questions into fewer rounds.
- **Vague goal ("make it better"):** Ask the user to define one concrete thing that would feel like an improvement. Build from there.
