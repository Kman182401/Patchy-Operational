# Verification Gates

Do not declare success until verification passes at the level required by the task.

## Required Checks
- relevant tests
- type checks
- linters
- builds
- targeted repro steps
- manual verification for user-visible behavior when needed

## Python Rule
- If you touched Python and tests exist for the touched modules, run `pytest -q` for those modules or the smallest relevant scope.

## Diff Review
- Review the final diff for:
  - unintended behavior changes
  - missing docs or tests
  - compatibility risks
  - dead code or partial refactors

## Reporting
- State what you verified.
- State what you could not verify.
- Do not claim completion on unverified assumptions.
