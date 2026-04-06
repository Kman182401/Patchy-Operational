---
name: undo
description: Fully undo the work Claude just completed in this session. Use immediately after a change, install, refactor, config edit, migration, file generation, or automation step when you want the repo and local state restored as closely as possible to the pre-task state.
argument-hint: "[optional rollback instructions or scope]"
disable-model-invocation: true
effort: high
---

# undo

## Purpose

Reverse the work Claude most recently completed in this session.

Treat this as a targeted rollback workflow, not a fresh implementation task. The goal is to restore the project and local environment as closely as possible to the state that existed before the just-completed work began, while avoiding damage to unrelated changes.

If the user provides arguments after `/undo`, treat them as rollback constraints, priorities, or scope overrides. Examples:
- `/undo config only`
- `/undo only undo the files from the last refactor`
- `/undo revert the install but keep the docs`
- `/undo fully restore the previous state and remove generated artifacts`

## When to Trigger

Use this skill when:
- Claude just completed a task and the user wants it reversed
- the recent work introduced bugs, wrong assumptions, bad edits, or unwanted changes
- the user wants a rollback of file edits, config changes, generated files, local installs, or related local state changes from the immediately preceding task
- the user wants `/undo` with extra instructions that change how the rollback should be carried out

## When Not to Trigger

Do not use this skill when:
- there is no recent Claude-completed work to reverse
- the user wants a fix or revision rather than a rollback
- the request is really a historical git operation unrelated to the just-completed task
- the rollback would require destructive reversal of unrelated user work
- the action would require undoing remote or external side effects that cannot be safely reversed from current evidence

## Inputs

### Required
- the current session context
- the most recent completed Claude task
- repository state and local filesystem evidence

### Optional
- `$ARGUMENTS`

If `$ARGUMENTS` is present, treat it as an instruction modifier with higher priority than the default rollback path, unless following it would cause unrelated or unsafe destructive changes.

## Output Requirements

Always produce all of the following:

1. What work is being undone
2. The rollback plan actually used
3. The changes reversed
4. The validation performed after rollback
5. Any remaining limits, uncertainties, or irreversible effects
6. A final status using exactly one of:
   - `Undo completed`
   - `Undo completed with limitations`
   - `Undo not fully completed`

Use this exact structure:

### undo result
**Work being undone:** <summary>

**Rollback scope / instructions:** <how `$ARGUMENTS` affected the rollback, or "default full rollback of the last completed task">

**Changes reversed:**  
- <item>
- <item>

**Validation performed:**  
- <check>
- <check>

**Remaining limitations / irreversible items:**  
- <item or "none known from completed checks">

**Final status:** `Undo completed` | `Undo completed with limitations` | `Undo not fully completed`

## Core Behavior

Your default behavior is:

- fully undo the work Claude just completed
- use evidence first, not guesswork
- reverse only the just-completed work unless the user explicitly broadens scope
- protect unrelated user edits and unrelated repo state
- be honest about anything that cannot be fully reversed

Load and use `undo-checklist.md` as your rollback checklist.

## Rollback Workflow

### Step 1 — Reconstruct the exact work to reverse

Determine:
- what Claude most recently completed
- which files were created, modified, renamed, or deleted
- which configs, scripts, docs, tests, dependencies, generated artifacts, services, or local state were changed
- whether the user supplied rollback instructions in `$ARGUMENTS`

Use:
- current session context
- changed files
- git status / diff / log when available
- command history or local evidence available in the session
- neighboring files related to the just-completed task

Do not start reverting until the scope is clear.

### Step 2 — Apply user-provided rollback instructions

If `$ARGUMENTS` is present:
- treat it as the primary rollback directive
- use it to narrow, widen, or shape the undo process
- still prevent unrelated destructive changes
- if the instruction conflicts with evidence, follow the safest evidence-backed interpretation and state that clearly in the final report

### Step 3 — Build the safest rollback path

Prefer rollback methods in this order:

1. targeted reversal of the exact changed files and local state from the just-completed task
2. restoration using repository evidence such as git diff, prior file contents, or clearly reconstructable pre-change state
3. removal of files, directories, generated outputs, caches, backups, or artifacts created only by the just-completed task
4. restoration of deleted or replaced files when their previous state can be recovered reliably
5. reversal of dependency/config/service changes directly tied to the just-completed task
6. commit-level reversal only if that is clearly the right scope and will not wipe unrelated work

Do not jump to a repo-wide destructive reset when a narrower rollback can correctly undo the work.

### Step 4 — Reverse the work

Undo all applicable recent changes from the just-completed task, including where relevant:

- file content edits
- newly created files and directories
- renamed or moved files
- deleted files that should be restored
- configuration changes
- dependency additions or removals
- generated artifacts
- test updates made solely for the reverted work
- documentation changes tied only to the reverted work
- service, script, or local runtime changes caused by the task
- duplicate backups, temporary files, or stale copies introduced during the task

Keep the rollback minimal, targeted, and evidence-backed.

### Step 5 — Protect unrelated work

Before each destructive action, check whether it would remove:
- unrelated user edits
- pre-existing local work
- intentional changes outside the just-completed task
- data or files not created or modified by the task being undone

If so, do not remove them unless the user explicitly instructed that broader rollback and the evidence supports it.

### Step 6 — Validate the rollback

After reversing the changes:
- verify the touched files and state now match the intended pre-task condition as closely as possible
- run the highest-value relevant checks
- prefer targeted validation first, then broaden if needed

Examples:
- git diff / status review
- targeted tests
- lint or typecheck if the undone work affected them
- config validation
- service status or syntax checks
- directory/file existence checks
- dependency manifest lockfile consistency checks

Do not claim the undo succeeded just because files were edited.

### Step 7 — Report clearly

Use the exact output format defined above.

## Guardrails

- Do not undo unrelated user work
- Do not use broad destructive commands by default when a targeted rollback is possible
- Do not claim "fully undone" unless the evidence reasonably supports that claim
- Do not pretend remote, external, or irreversible side effects were reversed if they were not
- Do not leave behind stale generated artifacts, backups, duplicate copies, or conflicting versions from the reverted task
- If part of the work cannot be reversed exactly, say so explicitly
- If the user gave extra rollback instructions, follow them as closely as safely possible and explain how they changed the rollback path
- If the just-completed work included commits, branches, installs, or local service changes, inspect those too rather than focusing only on file contents

## Failure Modes to Watch For

Common rollback failures:
- undoing the wrong scope
- restoring files but leaving config drift behind
- deleting newly created files but not restoring replaced files
- reverting code while leaving docs/tests/scripts inconsistent
- forgetting generated artifacts or lockfiles
- using a reset that wipes unrelated edits
- claiming success without checking the resulting state

Actively guard against these.

## Success Criteria

This skill succeeds only when it:
- correctly identifies the just-completed work
- reverses the intended changes as completely as current evidence allows
- avoids harming unrelated work
- validates the resulting state
- states any irreversible or unverified areas honestly

## Additional resources

- Use [undo-checklist.md](undo-checklist.md) as the detailed rollback checklist.

## Example invocations

- `/undo`
- `/undo config only`
- `/undo only reverse the changes from the last migration`
- `/undo revert the install and generated files but keep the README edits`
- `/undo restore the repo to the state before the last task`

## Version Metadata

- Version: 1.0
- Platform: Claude
- Artifact Type: skill
- Invocation Intent: user-invoked
- Status: ready to test
- Created: 2026-04-03
- Last Reviewed: 2026-04-03
