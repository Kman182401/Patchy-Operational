# Plan Quality Bar

A final plan is not complete until these questions are answered at the level relevant to the task.

## Objective
- What is being built, changed, fixed, or decided?
- What outcome counts as success?
- Who or what is affected?

## Scope And Constraints
- What is in scope?
- What is explicitly out of scope?
- What constraints matter:
  - compatibility
  - migration safety
  - repo conventions
  - runtime limits
  - security or compliance boundaries

## Implementation Shape
- Which subsystems or surfaces will change?
- Which public interfaces, APIs, types, schemas, configs, or workflows will change?
- What is the expected data flow or control flow after the change?

## Risks And Edge Cases
- What can fail?
- What assumptions are brittle?
- Which edge cases are important enough to handle in v1?

## Verification
- What tests, checks, builds, linting, manual repros, or operational validations are required?
- What evidence will prove the work is done?

## Execution Readiness
- Could a different strong engineer execute this plan without making policy decisions?
- Could the work resume from the plan after a context reset?
- Does the plan state what is already decided, what remains pending, and where execution should resume next?
If the answer is no, the plan is still incomplete.
