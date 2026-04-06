# Plan Output Template

Use this structure for the final deliverable.

## Final Shape Rules
- Emit exactly one final artifact.
- Include exactly one `Evidence Memo` section.
- Include exactly one `Durable Plan` section.
- Do not restate the same plan twice with a second heading sequence.
- If the user asked for the artifact only, omit progress notes, recap paragraphs, and post-plan commentary.
- **Return the plan directly in the chat. Do not write it to a file. Do not create PLANS.md, PLAN.md, or any other plan file on disk.**

## Evidence Memo
- `Verified facts`
- `Inferences`
- `Unknowns`
- `Risks`
- `Sources consulted` when external research materially informed the plan

Keep the memo short and factual. Do not repeat generic repo context.

## Durable Plan

1. Title
2. Summary
3. Current status
4. Milestones
5. Implementation details
6. Validation gates
7. Decision log
8. Surprises and discoveries
9. Assumptions and defaults
10. Open questions, only if they are truly blocking and cannot be resolved safely

## Plan Writing Rules
- Use one heading sequence only.
- Make milestones ordered and executable.
- Use checkboxes or another explicit progress marker for milestones.
- State exact artifacts to create or update when known.
- Include concrete validation commands or checks when they are knowable.
- When external research matters, record the source URL and the as-of date in the evidence memo or source section.
- Record defaults you chose so execution does not have to guess.
- Prefer compact completeness over long prose.
