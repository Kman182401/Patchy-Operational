# Research Standards

Use this file whenever the task depends on facts that may be stale, external, version-sensitive, security-sensitive, standards-related, or expensive to get wrong.

## Local First
1. Read the repo and environment first.
2. Form concrete sub-questions from local evidence.
3. Browse only after the local pass is strong enough to make targeted queries.

## Minimum Web Research Bar
1. Use multiple targeted queries, not one broad search.
2. Prefer primary sources:
   - official product docs
   - official API references
   - release notes
   - standards
   - maintainer guidance
   - peer-reviewed or primary research when relevant
3. Cross-check important claims across more than one source when possible.
4. Confirm exact versions, dates, and deprecations for anything version-sensitive.
5. For security, compliance, finance, or infrastructure claims, verify against current official guidance before treating them as facts.

## Required Output Labels
- `Verified facts`: directly supported by local evidence or sources you actually checked.
- `Inferences`: reasoned conclusions from verified facts.
- `Unknowns`: information you could not verify.
- `Risks`: concrete ways the plan could fail or create rework.

## Search Safety
- Never search for or paste:
  - secrets
  - credentials
  - private file contents
  - personal data
  - internal-only URLs or tokens

## Source Handling
- Cite only sources actually consulted.
- Prefer current official docs over memory.
- If sources conflict, say so explicitly and choose the highest-authority source.
- When a researched claim affects the plan, record the URL and current date context in the final artifact.
- If you cannot verify a key claim safely, say `I don't know` and record the missing evidence.
