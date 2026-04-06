# review-rubric

Use this file during the audit phase of `/analyze`.

Do not treat it as a generic essay prompt. Use it as a structured checklist while reviewing the work Claude just completed.

## 1. Functional Correctness

Check:
- Does the result actually do what the user asked for?
- Is the core logic correct?
- Are there obvious broken branches, wrong conditions, wrong paths, bad imports, or wrong assumptions?
- Are outputs, return values, and side effects correct?

Look for:
- off-by-one logic
- wrong variable or file names
- incorrect branch conditions
- partial implementations
- missing wiring into the actual execution path

## 2. Completeness and Integration

Check:
- Was every needed file updated?
- Was the change registered wherever the project expects it to be registered?
- Are config, docs, tests, scripts, imports, services, schedulers, or entrypoints still aligned?

Look for:
- added code that is never called
- config added in one place but not another
- tests not updated for changed behavior
- docs or comments that now contradict the implementation

## 3. Configuration and Environment Fit

Check:
- Are env vars named correctly?
- Are paths, ports, units, permissions, service names, container names, and file locations correct?
- Are defaults sane for this repo and environment?
- Did the change accidentally depend on local-only assumptions?

Look for:
- wrong env var names
- bad relative paths
- missing config keys
- incorrect service wiring
- permission mismatches
- config drift or duplicate definitions

## 4. Edge Cases and Failure Handling

Check:
- What happens with empty, invalid, partial, duplicate, missing, or malformed input?
- What happens if a command fails halfway through?
- What happens on retry or repeated execution?
- Is timeout, rollback, cleanup, or retry handling needed?

Look for:
- crashes on empty input
- infinite loops
- duplicate creation
- partial state left behind
- missing error checks
- one-way migrations with no safety path

## 5. Security and Safety

Check:
- Are secrets exposed in code, logs, config, or examples?
- Is shell usage safe?
- Is user input validated before file, command, query, or network use?
- Are permissions broader than necessary?
- Are trust boundaries explicit?

Look for:
- hardcoded tokens
- unsafe interpolation in shell commands
- path traversal risks
- missing input validation
- overbroad file globs
- excessive privileges
- debug logging of sensitive values

## 6. Data / State Integrity

Check:
- Does the change preserve correct state?
- Is it idempotent where it should be?
- Are duplicates, stale backups, or conflicting copies left behind?
- Could two runs collide or corrupt state?

Look for:
- duplicate config files
- stale backup copies that may be mistaken for the real one
- race conditions
- non-idempotent migrations
- conflicting sources of truth
- partial writes without recovery handling

## 7. Performance and Resource Use

Check:
- Did the change introduce wasteful polling, heavy scans, excessive subprocesses, or avoidable startup cost?
- Does it block where it should not block?
- Does it create unnecessary CPU, disk, memory, or network load?

Look for:
- unbounded loops
- repeated full-directory scans
- excessive process spawning
- synchronous work on hot paths
- unnecessary logging volume
- retries with bad intervals

## 8. Validation and Observability

Check:
- Were the right tests or validation commands run?
- Can failures be detected easily?
- Are logs, errors, and outputs actionable?
- Is there enough evidence to support the final claim?

Look for:
- no tests
- wrong tests
- only static inspection with no runtime check
- poor error messages
- silent failure modes
- unverifiable "looks good" conclusions

## 9. Cleanup and Consistency

Check:
- Was temporary/debug code removed?
- Are dead code, stale comments, obsolete scripts, extra backups, or duplicate configs still present?
- Is naming consistent?
- Is the final structure easy to understand?

Look for:
- TODO placeholders
- print/debug leftovers
- dead branches
- old copies of replaced logic
- conflicting docs
- confusing duplicate files

## 10. Final Verdict Rules

Use `Ready` only when:
- core paths were reviewed
- important issues were fixed
- relevant validation actually ran
- no material known issues remain

Use `Ready with noted limitations` when:
- the important issues were fixed
- the result appears sound
- but some meaningful validation or environment-dependent verification could not be completed

Use `Not fully validated` when:
- key checks could not run
- important uncertainty remains
- or the review found unresolved material issues
