---
name: read-only-plans
description: >
  Master orchestration skill for research, planning, and analysis — without modifying code.
  This skill should be used when the user says "plan this", "analyze this", "review this
  approach", "what should we do", "design this", "think through this", "scope this out",
  "write a plan", "read-only analysis", "investigate before implementing", "research and plan",
  "/read-only-plans", or when the task requires deep thinking, structured analysis, or
  planning before any code is touched. Sequences 15+ skills across 4 phases:
  research → analyze → plan → challenge. Produces a decision-complete plan or analysis
  report without modifying any project files.
  NOT for implementing changes (use /code-changes) or debugging (use /debug-fix) or
  post-completion audits (use /post-changes-audit).
---

# Read-Only Plans — Research & Analysis Orchestration

$ARGUMENTS

Execute research and planning through four mandatory phases. No project files are modified. All output is delivered in-chat as structured reports and plans.

---

## Phase 1: Research & Discovery

**Goal:** Gather all evidence before forming conclusions.

**Parallel where possible — these are independent information-gathering tasks.**

1. **`/researcher`** — Gather current information on technologies, libraries, APIs, patterns, and best practices relevant to the task. Use WebSearch and WebFetch aggressively. Prefer primary sources.
2. **`/expert-analysis`** — Deep, evidence-first investigation of the target (codebase, system, config, architecture, dependency, or plan). Produce a structured report separating verified facts from inferences from unknowns.
3. **`/subagent-driven-development`** — Identify which domain agents have relevant expertise. Dispatch read-only analysis agents in parallel for independent investigation branches.
4. **`/dispatching-parallel-agents`** — Coordinate parallel research agents. Ensure no overlap in investigation scope and merge findings.

---

## Phase 2: Analysis & Assessment

**Goal:** Evaluate findings through multiple lenses.

**Sequential — each builds on the previous.**

5. **`/analyze`** — Deep review of the target across correctness, security, reliability, performance, operability, and maintainability lenses. Produce findings with evidence classification (verified/inferred/external/uncertain).
6. **`/security-review`** — Security-focused analysis of any code, config, or infrastructure in scope. Run scanners if applicable. Produce severity-rated findings.
7. **`/scope-guard`** — Define clear boundaries for what the eventual implementation should and should not touch. Establish guardrails before planning begins.
8. **`/assumptions-audit`** — Extract every assumption embedded in the current understanding. Classify each as Verified, High-confidence, Unverified, or Risky. Produce a verification queue ordered by risk.
9. **`/feature-forge`** — If the task involves unclear requirements, use feature-forge to clarify scope, acceptance criteria, and edge cases before planning.

---

## Phase 3: Planning & Design

**Goal:** Produce a durable, decision-complete plan.

**Sequential — plan must incorporate all Phase 2 findings.**

10. **`/plan-builder`** — Produce a restartable ExecPlan-style document grounded in the repo state and research findings. Include milestones, validation gates, risk assessment, and enough implementation detail that execution does not require re-planning.
11. **`/system-design`** — If the task involves architecture or infrastructure decisions, produce system design documentation with component diagrams, data flow, and scaling considerations.
12. **`/tech-debt`** — If the task touches existing code, assess technical debt in the affected area. Identify what should be addressed during implementation vs. deferred.
13. **`/writing-plans`** — Format the final plan for readability and completeness. Ensure the plan is self-contained and can be handed off to any implementer.

---

## Phase 4: Challenge & Validate

**Goal:** Stress-test the plan before committing to it.

**Sequential — challenges must reference the completed plan.**

14. **`/the-fool`** — Apply structured critical reasoning to the plan. Run devil's advocate, pre-mortem, or red-team analysis. Identify the 3-5 strongest challenges.
15. **`/assumptions-audit`** (second pass) — Re-audit assumptions after the plan is complete. Verify that planning did not introduce new unverified assumptions.
16. **`/scope-guard`** (final check) — Confirm the plan stays within the established scope boundaries. Flag any scope creep introduced during planning.

**Task manager checkpoint:**
17. **`/tm:update-task`** — Update the task tracker with the completed plan, findings, and any blockers identified.

---

## Output Contract

The final deliverable is one or more of:
- **ExecPlan** — A durable implementation plan (from plan-builder)
- **Analysis Report** — A structured investigation report (from expert-analysis or analyze)
- **Research Summary** — Current state of relevant technologies (from researcher)
- **Risk Assessment** — Assumptions audit with risk scoring

All outputs are delivered in-chat. No files are created in the project.

---

## Parallel vs Sequential Decision Rules

Launch in **parallel** when:
- researcher + expert-analysis + domain agent research (Phase 1 — independent investigation)
- Multiple read-only agents analyzing separate parts of the codebase

Run **sequentially** when:
- Analysis must complete before planning starts
- The plan must exist before the-fool can challenge it
- Assumptions-audit needs the plan as input

---

## Skills Checklist

Before claiming the analysis/plan is complete, confirm every applicable skill was invoked:

- [ ] researcher
- [ ] expert-analysis
- [ ] subagent-driven-development
- [ ] dispatching-parallel-agents
- [ ] analyze
- [ ] security-review
- [ ] scope-guard
- [ ] assumptions-audit
- [ ] feature-forge (if requirements unclear)
- [ ] plan-builder
- [ ] system-design (if architecture involved)
- [ ] tech-debt (if touching existing code)
- [ ] writing-plans
- [ ] the-fool
- [ ] assumptions-audit (second pass)
- [ ] scope-guard (final check)
- [ ] tm:update-task
