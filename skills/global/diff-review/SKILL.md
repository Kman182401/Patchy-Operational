---
name: diff-review
description: Pre-commit diff quality gate. Use when the user asks to review a diff, check before commit, or scan changes. Catches debug leftovers, leaked secrets, accidental edits.
---

# Diff Review

Pre-commit quality gate that inspects the actual git diff to catch issues hiding in changed lines. Linters catch formatting, security-review catches design flaws — this skill catches the diff itself: debug statements left behind, accidental edits, leaked credentials, and dead code sneaking into a commit.

## When to Trigger

- Before any `git commit` — run this after implementation is "done" but before committing
- When the user says "review my diff", "check before commit", "what changed"
- When preparing a PR or pushing changes for review
- As a final sanity check after all other skills (linter, test-runner, security-review) have passed

## Core Workflow

### Step 1: Capture the Diff

Run `git diff --staged` first. If nothing is staged, fall back to `git diff`. If both are empty, check for untracked files with `git status` and report that there is nothing to review.

Also run `git diff --staged --stat` (or `git diff --stat`) to get the file-level summary of changes.

### Step 2: Scan Each Hunk

Walk through every hunk in the diff. Focus only on added lines (`+` prefix) — removals are not introducing new problems. For each added line, check against the categories below.

### Step 3: Cross-Reference Scope

If a task description or plan is available, compare the files touched against the expected scope. Flag any file modifications that fall outside the stated task.

### Step 4: Produce the Report

Output a structured report using the format defined in the Output Format section. Assign a verdict.

---

## Issue Categories

### Category 1: Debug Leftovers (Severity: WARN or BLOCK)

Scan added lines for patterns that should not ship to production.

**Print/log statements added for debugging:**
- `print(` / `pprint(` / `breakpoint()` in Python
- `console.log(` / `console.debug(` / `debugger` in JavaScript/TypeScript
- `var_dump(` / `dd(` / `dump(` in PHP
- `System.out.println(` in Java
- `fmt.Println(` used as debug output in Go
- `puts ` / `p ` used as debug output in Ruby

Distinguish intentional logging (using a logger, structured output) from debug prints (raw print to stdout). If a `print()` is inside a logging utility or CLI output function, do not flag it.

**TODO/FIXME/HACK/XXX comments added:**
- Only flag these on lines with the `+` prefix in the diff — pre-existing ones are not this skill's concern
- Severity: WARN — these indicate incomplete work that may ship accidentally

**Commented-out code blocks:**
- Three or more consecutive commented lines that look like code (contain assignments, function calls, control flow)
- Severity: WARN — dead comments clutter the codebase

**Hardcoded test values:**
- `localhost` / `127.0.0.1` in non-test, non-config files
- `test@test.com`, `example@example.com` in production code
- `password123`, `admin`, `changeme`, `secret` as string literals
- Severity: WARN in production code, INFO in test files

### Category 2: Accidental Changes (Severity: WARN)

Detect changes that are likely unintentional side effects of the editor or tooling.

**Whitespace-only changes:**
- Files where the diff shows only whitespace modifications (trailing spaces, line endings, indentation normalization) but no functional changes
- Flag if these files are not part of the stated task

**Import reordering:**
- Import blocks rearranged in files that have no other functional changes
- This often happens when auto-import tools run on file open

**Out-of-scope file modifications:**
- Changes to files unrelated to the current task
- Cross-reference with the plan, task description, or commit message intent if available
- If scope-guard skill is active, defer to its judgment and note alignment

**Config/lockfile churn:**
- Changes to `package-lock.json`, `poetry.lock`, `Cargo.lock`, or similar lockfiles when no dependency was intentionally added or removed
- Severity: WARN — lockfile changes can introduce unexpected dependency updates

### Category 3: Security Concerns (Severity: BLOCK)

These issues must be fixed before committing. No exceptions.

**Credentials in the diff:**
- API keys, tokens, passwords, or secrets appearing as string literals
- Pattern indicators: strings starting with `sk-`, `ghp_`, `AKIA`, `Bearer `, or matching common key formats
- Any variable named `password`, `secret`, `token`, `api_key` assigned a literal string value

**Sensitive files staged:**
- `.env`, `.env.local`, `.env.production` files in the diff
- `credentials.json`, `service-account.json`, `*.pem`, `*.key` files
- Check `.gitignore` — if these file types are not ignored, flag as BLOCK and recommend adding them

**Hardcoded credentials:**
- Database connection strings with embedded passwords
- URLs containing `user:password@` patterns
- Base64-encoded strings that decode to credentials

**New endpoints without auth:**
- Route handlers, API endpoints, or view functions added without authentication/authorization decorators or middleware
- Severity: WARN (not all endpoints need auth, but worth flagging for review)

### Category 4: Quality Issues (Severity: WARN or INFO)

Code quality concerns that are worth noting but rarely block a commit.

**Unreferenced functions or classes:**
- New function or class defined but never called or imported elsewhere in the diff
- Severity: INFO — may be called from existing code not in the diff, but worth verifying

**Dead code introduced:**
- Code after a `return`, `raise`, `break`, or `continue` statement
- Unreachable branches (e.g., `if False:`)
- Severity: WARN

**Overly large hunks:**
- Single hunks exceeding 200 added lines suggest the change should be split
- Single files with more than 500 lines of changes suggest the commit is doing too much
- Severity: INFO — recommendation, not a blocker

**Missing error handling:**
- New calls to external services (HTTP requests, database queries, file I/O) without try/except, error checking, or Result handling
- New `await` calls without error handling in async code
- Severity: WARN

**Type hint gaps (Python-specific):**
- New public functions missing return type annotations
- New function parameters without type hints when the rest of the file uses them
- Severity: INFO

---

## Output Format

Structure every diff review report as follows:

```
## Diff Review Report

**Files changed:** N files (+X lines / -Y lines)
**Scope:** [Brief description of what the changes do]

### Issues Found

#### BLOCK (must fix before commit)
- [file:line] Description of the blocking issue
- [file:line] Description of the blocking issue

#### WARN (review before committing)
- [file:line] Description of the warning
- [file:line] Description of the warning

#### INFO (noted for awareness)
- [file:line] Description of the informational note

### Verdict: CLEAN | WARN | BLOCK

[One-sentence summary explaining the verdict]
```

**Verdict rules:**
- **CLEAN** — Zero issues found across all categories. State: "No issues detected. Proceed with commit."
- **WARN** — One or more WARN-level issues found, zero BLOCK issues. State which warnings were found and recommend reviewing them. Do not prevent the commit.
- **BLOCK** — One or more BLOCK-level issues found. State what must be fixed. Do not proceed with commit until resolved.

If the verdict is BLOCK, list the specific fixes needed and offer to apply them.

If the verdict is WARN, list the warnings and ask whether to proceed or fix first.

If the verdict is CLEAN, confirm and move to commit.

---

## Integration Notes

**With other skills:**
- Run after `linter` and `test-runner` — those catch syntax and logic errors; this catches diff-level issues they miss
- Run before `code-reviewer` — code-reviewer does deep analysis; diff-review is a fast pre-flight check
- If `security-review` already ran on the same changes, still check for credentials in the diff — security-review focuses on design patterns, not literal strings in the diff
- If `scope-guard` is available, defer scope judgments to it and note alignment in the report

**Automatic triggering:**
- When asked to commit changes, run this skill first
- When asked to prepare a PR, run this skill as part of the preparation
- Skip this skill only when explicitly told to ("commit without review", "skip diff check")

## Edge Cases

- **Binary files:** Note their presence but do not attempt to scan content. Report file names and sizes only.
- **Generated files:** If a file path suggests it is generated (e.g., `*.min.js`, `dist/`, `build/`, `__pycache__/`), note it but do not flag issues inside it.
- **Migration files:** Database migration files often contain raw SQL and hardcoded values by design. Flag but classify as INFO, not WARN.
- **Test files:** Relax severity for hardcoded test values in files under `test/`, `tests/`, `*_test.*`, `test_*.*`, or `spec/`. Classify as INFO instead of WARN.
- **Large diffs:** If the diff exceeds 2000 lines, summarize by file and focus detailed scanning on non-test, non-generated files first. Report that a partial scan was performed.
