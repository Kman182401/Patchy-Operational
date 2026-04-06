# undo-checklist

Use this file while executing `/undo`.

Do not treat it as generic advice. Use it as a concrete rollback checklist for the work Claude most recently completed.

## 1. Session Reconstruction

Identify:
- what the just-completed task actually was
- what the intended result was
- which files, configs, commands, installs, services, and artifacts were touched
- whether the user passed extra rollback instructions after `/undo`

Primary evidence:
- current session context
- changed files
- git status / diff / log if available
- command output and local evidence
- nearby files related to the completed task

## 2. Scope Control

Default scope:
- undo only the just-completed work

If the user gave extra instructions:
- apply them as the rollback scope controller
- narrow or widen only as explicitly requested
- still avoid unrelated destructive changes

Check for accidental overreach:
- unrelated user edits
- older pre-existing local changes
- unrelated files modified in the same area
- assets or data not created by the just-completed task

## 3. File-System Rollback

Check and reverse:
- modified files
- newly created files
- renamed or moved files
- deleted or replaced files
- temporary files
- generated output
- duplicate backups or stale copies created during the task

Questions:
- Which files should be restored?
- Which files should be removed?
- Which deleted files need to come back?
- Did the task leave behind confusing copies of the same thing?

## 4. Config and Environment Rollback

Check and reverse:
- env var changes
- config keys
- service definitions
- ports, paths, permissions, units, or flags
- tool or runtime configuration
- project settings or local overrides

Questions:
- Was config changed in more than one place?
- Was anything added but not fully removed?
- Did the task create config drift or duplicates?

## 5. Dependency and Build-State Rollback

Check and reverse:
- package additions/removals
- lockfile changes
- venv or local environment changes
- build outputs
- installed tools used only for the reverted task
- generated caches or compiled assets

Questions:
- Do manifests and lockfiles match after rollback?
- Did the task install something that should now be removed?
- Did generated outputs survive after the source change was reverted?

## 6. Docs, Tests, and Script Consistency

Check and reverse where relevant:
- docs updated only for the reverted work
- tests added or changed only for the reverted work
- scripts or commands introduced for the reverted work
- README examples that now no longer match

Questions:
- If code was undone, do docs and tests need undo too?
- If a script was added only to support the reverted work, should it be removed?

## 7. Local Runtime / Service Rollback

Check and reverse where applicable:
- started services
- changed local processes
- modified cron/timers/unit files
- local permissions changes
- symlinks or startup entries

Questions:
- Did the task start or modify a service?
- Did it leave a running process or altered startup behavior?
- Did it change local execution state beyond the repo files?

## 8. Git-Aware Rollback

Use git carefully.

Prefer:
- targeted reversal
- restoring exact files
- reverse-applying only the relevant change

Avoid broad destructive git actions unless clearly justified.

Questions:
- Are there unrelated uncommitted changes that must be preserved?
- Was the completed task committed?
- Is a targeted file restore safer than a history rewrite?
- Would a broad reset wipe unrelated work?

## 9. Validation After Rollback

Perform the highest-value checks that fit the reverted work:
- inspect git status / diff
- verify restored/removed files
- run targeted tests if affected
- run config or syntax checks
- confirm services/processes are back to the intended state
- confirm no stale generated artifacts remain

Do not stop at "the files look right."

## 10. Final Status Rules

Use `Undo completed` only when:
- the just-completed work was identified correctly
- the intended changes were reversed
- relevant validation was actually performed
- no material known rollback gaps remain

Use `Undo completed with limitations` when:
- the main rollback succeeded
- but some environment-dependent or irreversible parts could not be fully reversed

Use `Undo not fully completed` when:
- the scope could not be recovered with confidence
- important parts could not be reversed
- or the rollback still has material unresolved gaps
