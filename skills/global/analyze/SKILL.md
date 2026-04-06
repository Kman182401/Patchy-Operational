---
name: analyze
description: Deep post-completion review. Use PROACTIVELY immediately after code changes, fixes, refactors, installs, config edits, migrations, or automation work. Trigger before claiming any task is complete. Finds missed issues, patches them, and validates the final state.
argument-hint: "[optional focus]"
effort: high
---

# analyze

## Purpose

Run a professional post-completion audit on the work just completed in this session.

Treat this as a verification-and-repair pass, not a fresh implementation pass. The goal is to identify anything that was missed, misconfigured, left half-done, wired incorrectly, or insufficiently validated, then fix what is safely fixable now and prove the final state as far as the environment allows.

## When to Trigger

Use this skill when:
- Claude just finished implementing, refactoring, debugging, installing, configuring, migrating, packaging, or hardening something
- the user wants a deep review, hardening pass, or production-readiness check
- the recent work may have hidden edge cases, config mistakes, broken wiring, or incomplete validation
- the user wants Claude to make the necessary corrections, not just list problems

## When Not to Trigger

Do not use this skill when:
- there is no recent completed work to review
- the task is a brand-new implementation rather than a post-completion review
- the real need is a large redesign or a new plan rather than an audit/fix pass
- the required work would be mostly destructive, unrelated, or outside the scope of the just-completed task

## Inputs

### Required
- the current session context
- the immediately preceding completed task
- the current working tree, repository state, and relevant local files/configuration

### Optional
- slash-command arguments that narrow the review scope, such as:
  - a file
  - a directory
  - a feature name
  - a concern such as "config only" or "tests only"

If the user does not provide scope arguments, infer the scope from:
1. the most recent completed task in the conversation
2. changed files
3. git status / git diff if available
4. nearby config, tests, docs, scripts, and wiring related to that task

Prefer the narrowest scope that still fully covers the work just completed.

## Outputs

Always produce all of the following:

1. A short statement of what work was reviewed
2. A list of concrete issues found
3. The fixes applied during this review pass
4. The validation actually performed
5. Any remaining risks, blockers, or unverified areas
6. A final verdict using exactly one of:
   - `Ready`
   - `Ready with noted limitations`
   - `Not fully validated`

## Tool / Execution Expectations

Use the available repo-aware capabilities aggressively but intentionally.

Expected actions include:
- inspecting recent files, diffs, configs, logs, scripts, and tests
- reading neighboring code that affects the touched change
- running targeted validation commands first
- widening validation only when it materially improves confidence
- editing files directly when a clear fix is needed
- keeping changes minimal, localized, and aligned with existing project patterns

Avoid unrelated cleanup or speculative refactors unless they directly reduce risk for the reviewed work.

## Review Workflow

### Step 1 -- Reconstruct the just-completed task

Determine:
- what Claude most recently completed
- what outcome was intended
- which files, commands, configs, tests, and runtime surfaces were involved

Use session context first, then confirm with repository evidence.

### Step 2 -- Gather evidence

Inspect:
- changed files
- git status / git diff / recent file modifications when available
- directly touched configs and environment wiring
- related tests, scripts, docs, or registrations
- logs or command output relevant to the recent work

Then load and use `review-rubric.md` as the audit checklist.

### Step 3 -- Audit deeply

Check for all of the following classes of problems:

- functional bugs
- incomplete implementation
- broken integration or wiring
- wrong paths, imports, names, flags, env vars, permissions, ports, defaults, or file locations
- stale or conflicting old configuration left behind
- missing rollback, retry, timeout, or failure handling
- unhandled edge cases
- security weaknesses, secret leakage, unsafe shell usage, or overly permissive settings
- data/state integrity risks
- performance waste or unnecessary resource usage
- stale docs, broken tests, leftover debug code, dead code, temp files, backups, or duplicate copies that create confusion

### Step 4 -- Patch what is fixable now

For every issue that is clear and safe to fix:
- apply the smallest correct fix
- keep behavior aligned with existing project conventions
- avoid speculative rewrites
- avoid unrelated style churn

### Step 5 -- Validate after fixes

Run the highest-value validation that is actually relevant to the touched work.

Use existing project commands where available, such as:
- tests
- lint
- typecheck
- build
- smoke tests
- targeted runtime verification
- config validation
- service/unit syntax checks
- dry-run style validation where applicable

Do not assume something works just because the code looks right.

### Step 6 -- Re-check second-order issues

After patching:
- confirm the fix did not break neighboring logic
- confirm docs, config, and tests still match the new state
- confirm duplicate or conflicting old versions of the same logic were not left behind
- confirm the final state is internally consistent

### Step 7 -- Report clearly

Use this exact output structure:

### analyze result
**Reviewed work:** <what was reviewed>

**Issues found:**  
- <issue 1>
- <issue 2>

**Fixes applied:**  
- <fix 1>
- <fix 2>

**Validation performed:**  
- <actual command/check 1>
- <actual command/check 2>

**Remaining risks / limits:**  
- <risk or "none known from completed checks">

**Final verdict:** `Ready` | `Ready with noted limitations` | `Not fully validated`

## Guardrails

- Do not claim "no issues" unless the relevant surfaces were actually inspected and validated
- Do not claim production-readiness unless the evidence reasonably supports it
- Do not skip validation just because the change appears straightforward
- Do not make unrelated stylistic rewrites
- Do not silently widen scope into a full rewrite
- Do not modify secrets, credentials, remote infrastructure, production data, or destructive system state unless that was explicitly part of the just-completed task
- If a required validation step cannot run, say exactly why
- If the user's expectation conflicts with repository evidence, trust the repository evidence and explain the mismatch
- If the review finds uncertainty that cannot be resolved locally, say so explicitly instead of pretending confidence

## Failure Modes to Watch For

Common ways this skill can fail:
- reviewing the wrong scope
- missing files outside the main edit path
- checking the code but not the surrounding config/wiring
- fixing one problem while leaving conflicting old logic behind
- assuming tests passed without running them
- over-editing unrelated files
- declaring success with weak validation coverage

Actively guard against these.

## Success Criteria

This skill succeeds only when it:
- reviews the actual work that was just completed
- finds and fixes real issues where possible
- performs real validation
- reports remaining uncertainty honestly
- leaves the repo in a more correct and more consistent state than before the audit

## Example Invocations

- `/analyze`
- `/analyze src/auth only`
- `/analyze config and deployment wiring`
- `/analyze migration + rollback path`
- `/analyze tests and edge cases for the last change`

## Version Metadata

- Version: 1.0
- Platform: Claude
- Artifact Type: skill
- Invocation Intent: user-invoked
- Status: ready to test
- Created: 2026-04-03
- Last Reviewed: 2026-04-03
