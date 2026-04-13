---
name: scope-guard
description: Prevent scope creep by comparing current work to the original request. Trigger on "scope check", "am I on track", "staying focused", or during multi-step tasks.
---

# Scope Guard

Prevent scope creep by continuously comparing work against the original user request. Act as a discipline layer that catches drift before it compounds.

## Purpose

Most task failures are not from doing the wrong thing — they come from doing too many things. Scope Guard enforces a single rule: do what was asked, nothing more, nothing less. Every addition not in the original request is suspect until explicitly approved.

## When to Activate

### Automatic Triggers
- Any multi-step implementation task (3+ file changes or 3+ logical steps)
- Any task involving refactoring, migration, or architecture changes
- When a plan is being built or revised
- Before claiming a task is "done"

### Manual Triggers
- User says "scope check", "am I on track", "staying focused"
- User asks "what was I asked to do" or "am I drifting"
- Any time uncertainty arises about whether current work serves the original ask

## Core Workflow

### Phase 1 — Capture the Ask

At the start of every non-trivial task, extract and lock the original request:

1. Record the user's exact words (quote them verbatim, do not paraphrase).
2. Identify the deliverables — what concrete outputs were requested.
3. Identify the boundaries — what was explicitly excluded or not mentioned.
4. Note any constraints the user stated (time, scope, approach).

Store this as the **Scope Anchor**. Everything is measured against it.

### Phase 2 — Guard During Implementation

At each decision point, apply the Scope Test:

> "Does this change directly serve one of the deliverables in the Scope Anchor?"

If yes, proceed. If no, flag it.

#### Decision Points That Require the Scope Test
- Before creating a new file
- Before modifying a file not mentioned in the original request
- Before adding a dependency or import
- Before writing tests for code that was not changed
- Before adding error handling beyond what the task requires
- Before refactoring code adjacent to the change
- Before adding documentation to unchanged code
- Before introducing an abstraction layer
- Before adding configuration options or feature flags

### Phase 3 — Detect and Name Drift

When the Scope Test fails, stop immediately and name the drift using this format:

```
SCOPE DRIFT DETECTED
  Anchor: [original request, quoted]
  Current action: [what is about to happen]
  Drift type: [category from list below]
  Recommendation: skip / ask user / defer to follow-up
```

Do not silently skip the drifting work. Name it explicitly so the user can decide.

### Phase 4 — Final Scope Check

Before marking any task complete, produce the Scope Report (see Output Format below). Verify every deliverable from the Scope Anchor was addressed. Verify nothing outside the Scope Anchor was added without explicit approval.

## Drift Categories

Recognize and label these specific anti-patterns:

### "While I'm Here" Changes
Modifying code near the target that was not part of the request. Renaming variables, reformatting, fixing lint warnings in adjacent lines, updating comments on unchanged functions.

**Test:** Was this file or function mentioned in the original request? If not, do not touch it.

### "Nice to Have" Additions
Adding error handling, logging, validation, or retry logic that was not requested. These are often good ideas — but they are not what was asked for.

**Test:** Did the user ask for this specific behavior? If not, flag it.

### Premature Abstraction
Extracting a helper function, creating a base class, or introducing a design pattern to make the code "more maintainable" when the request was for a specific concrete change.

**Test:** Does the original request mention reusability, abstraction, or architecture? If not, implement the simplest concrete solution.

### Scope Expansion Through Testing
Writing tests for pre-existing code that was not modified. Adding integration tests when only unit tests were implied. Building test infrastructure (fixtures, factories, mocks) beyond what the specific test needs.

**Test:** Does this test verify the specific change requested? If not, skip it.

### Backwards-Compatibility Shims
Adding migration paths, deprecation warnings, or compatibility layers that were not requested. Often triggered by changing an interface and feeling obligated to preserve the old one.

**Test:** Did the user ask for backwards compatibility? If not, make the change directly.

### Documentation Drift
Updating READMEs, adding docstrings to unchanged functions, creating architecture diagrams, or writing migration guides that were not part of the request.

**Test:** Did the user ask for documentation? If not, skip it.

### Gold Plating
Adding configuration options, environment variable support, CLI flags, or feature toggles to make the change "more flexible" when a hardcoded or simple approach satisfies the request.

**Test:** Did the user ask for configurability? If not, implement the direct solution.

## Output Format — Scope Report

When performing a scope check (automatic or manual), produce this brief comparison:

```
SCOPE REPORT
  Original ask: "[user's exact words]"
  Deliverables identified: [numbered list]
  Current work summary: [what has been done so far]
  Drift items: [list any work outside scope, or "None"]
  Status: ON TRACK / DRIFTING
  Recommendation: [continue as-is / refocus on X / ask user about Y]
```

Keep the report concise — 10 lines maximum. The goal is a quick calibration, not a lengthy review.

## Integration Rules

### With Planning
When building a plan, apply the Scope Test to every planned step. Remove steps that fail the test before presenting the plan. If a step is borderline, mark it as "optional — not in original scope" rather than including it silently.

### With Implementation
During implementation, check scope at natural breakpoints: after each file is modified, after each logical step completes, before starting a new phase of work.

### With Completion
Before saying "done," always produce the Scope Report. If any drift items exist that were not explicitly approved, call them out.

### Handling Approved Expansions
If the user explicitly approves a scope expansion ("yes, also do X"), update the Scope Anchor to include the new deliverable. Note that it was added mid-task. Continue guarding against further drift from the updated anchor.

## Edge Cases

- **Necessary prerequisites:** Sometimes a dependency must be fixed before the requested change can work. This is not drift — it is unblocking. Note it as "prerequisite, not scope expansion" in the report.
- **Broken code discovered:** If the original code is broken in a way that blocks the request, fixing it is in scope. Fixing unrelated broken code nearby is not.
- **Security issues discovered:** Flag them to the user but do not fix them inline unless the user approves. Security findings are important but they are a separate task.
- **User changes direction mid-task:** Update the Scope Anchor. The new direction becomes the anchor. Guard against drift from the new anchor, not the old one.
