---
name: audit-trail
description: >
  Generates a structured, human-readable audit report of everything Claude Code did in a
  session. Use at the end of any session to create a complete paper trail suitable for commit
  messages, PR descriptions, code review, standup notes, and documentation. Trigger phrases:
  "audit trail", "session report", "what did we do", "summarize the session", "generate a
  report", "write up what happened", "pr description", "commit summary", "session summary",
  "document the changes", "write the audit report", "what was accomplished", "session
  changelog", "generate commit message", "write the PR", "document this session",
  "create a report of the work done". Synthesizes all available session context — git diff,
  changed files, task history, issues found and fixed, verification results — into four
  structured outputs: executive summary, technical audit log, commit message, and PR
  description draft. Run as the final step of post-changes-audit after all fixes are applied.
argument-hint: "[optional: 'brief' for summary only, 'pr' to lead with PR description, or ticket ID e.g. JIRA-1234]"
---

# audit-trail

Synthesizes everything from a Claude Code session into a structured paper trail.
Four outputs. One command. Complete documentation.

## Collection Protocol

### Step 1: Gather Session Evidence

```bash
# Git state
git log --oneline -5
git diff --stat HEAD 2>/dev/null || git diff --stat
git diff --name-status HEAD 2>/dev/null || git diff --name-status

# Recent file activity (30-minute window)
find . -not -path './.git/*' -not -path './node_modules/*' \
  -newer .git/index -type f 2>/dev/null | sort

# Plan or task files
cat .claude/plan.md PLAN.md TODO.md TASKS.md 2>/dev/null | head -100

# Audit results from this session (if post-changes-audit was run)
# Use findings from change-forensics, impact-radar, regression-guard if available in context
```

### Step 2: Reconstruct Task History

From session context, identify:
- The original user request (exact task stated)
- The implementation approach taken
- Issues encountered during the session
- Post-audit findings (if already run)
- Fixes applied during implementation or audit
- Verification steps completed and their outcomes (PASS/FAIL)

### Step 3: Classify All Changes by Type

Apply Conventional Commits classification:

| Type | When to use |
|---|---|
| `feat` | New functionality added |
| `fix` | Bug corrected |
| `refactor` | Code restructured with no behavior change |
| `chore` | Housekeeping, cleanup, renames |
| `docs` | Documentation only |
| `test` | Tests added or modified |
| `style` | Formatting only (no logic change) |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |
| `build` | Build system or dependency changes |

### Step 4: Check for Ticket Reference

If `$ARGUMENTS` contains a ticket ID pattern (e.g., `JIRA-1234`, `GH-42`, `#123`), extract it
and include it in the commit footer and PR title.

---

## Output Rules

- **Never fabricate verification results.** If a check was not run, write `Not verified`.
- **Commit message must be copy-pasteable.** No placeholder text that requires editing.
- **Executive summary must be plain language.** No code, no jargon, no markdown in the prose.
- **`brief` mode:** Produce Output 1 only (executive summary).
- **`pr` mode:** Lead with Output 4, follow with Output 3.
- **With ticket ID:** Include in commit footer (`Closes #N` or `Refs JIRA-1234`) and PR title.

---

## Output Format

### Output 1: Executive Summary

Write for a technical lead with 30 seconds to read it. Plain language. No markdown headers
inside the summary text itself.

```
## Executive Summary

Task: [What was asked and why]
Work done: [What was built or changed, in plain language]
Outcome: [Current state — verified and working, or pending follow-up]
Risks or caveats: [Anything needing follow-up, or "None identified"]
```

---

### Output 2: Technical Audit Log

```
## Technical Audit Log

**Session date:** [datetime]
**Scope:** [project/directory]
**Work type:** Feature | Fix | Refactor | Config | Mixed

### Files Created
- `path/to/file.ext` — [one-line purpose]

### Files Modified
- `path/to/file.ext` — [what changed: added X, removed Y, refactored Z]

### Files Deleted
- `path/to/file.ext` — [reason]

### Dependencies Added or Changed
- `package@version` — [reason]

### Issues Encountered and Resolved
1. [Issue] → [Resolution]
2. [Issue] → [Resolution]

### Post-Audit Findings
| Severity | Finding | Status |
|----------|---------|--------|
| BLOCK | [description] | Fixed / Open |
| WARN | [description] | Fixed / Accepted |

### Verification Performed
| Check | Tool | Result |
|-------|------|--------|
| Unit tests | pytest / jest | ✅ N passed / ❌ N failed / Not verified |
| Type check | mypy / tsc | ✅ Clean / ❌ N errors / Not verified |
| Lint | ruff / eslint | ✅ Clean / Not verified |
| Security scan | semgrep / bandit | ✅ Clean / Not verified |
| Regression check | regression-guard | ✅ Clean / Not verified |
| Import integrity | Python / TS | ✅ Clean / Not verified |

### Known Limitations and Recommended Follow-up
- [Anything incomplete, known issues, or recommended next steps — or "None"]

### Final Status
✅ COMPLETE | ⚠️ COMPLETE WITH NOTES | 🚫 INCOMPLETE — [reason]
```

---

### Output 3: Commit Message (Conventional Commits)

Present inside a copy-pasteable code block. No angle-bracket placeholders in the final output.

```
## Commit Message

```
<type>(<scope>): <imperative description, under 72 chars>

<body: what changed and why — wrap at 72 chars>
<additional context if needed>

<footer: BREAKING CHANGE, Closes #N, Co-authored-by: Name <email>>
```
```

Rules:
- `type` — one of: feat|fix|refactor|chore|docs|test|style|perf|ci|build
- `scope` — the module, component, or area (e.g., `auth`, `api`, `db`)
- First line must be under 72 characters
- Body explains **what and why**, not how
- If breaking change: `BREAKING CHANGE: <description>` in footer
- If ticket: `Closes #N` or `Refs TICKET-ID` in footer

---

### Output 4: PR Description (GitHub / GitLab format)

Present inside a copy-pasteable markdown code block.

```
## Pull Request Description

```markdown
## Summary

[2–3 sentence description of what this PR does and why]

## Changes

- **[type]** `path/to/file`: [description of what changed]
- **[type]** `path/to/file`: [description of what changed]

## Testing

- [ ] Unit tests: [N tests passing]
- [ ] Integration tests: [status]
- [ ] Manual testing: [what was tested manually and how]
- [ ] Edge cases considered: [list or "standard cases only"]

## Verification Checklist

- [x] Tests pass
- [x] No lint errors
- [x] No type errors
- [x] Security scan clean
- [x] No regressions detected
- [ ] Documentation updated (if applicable)
- [ ] Breaking changes documented (if applicable)
- [ ] Migration required (if applicable)

## Notes for Reviewers

[Areas that warrant close attention, non-obvious decisions, or known trade-offs — or "None"]
```
```

---

## Persistent Log (optional)

If a project-level log is appropriate, save this report to:
```
.claude/session-logs/YYYY-MM-DD-HHMM-<task-slug>.md
```

Only create this file if the project directory has a `.claude/` folder already present.

## Integration

- This skill is Stage 16 of `post-changes-audit` — run it last, after all fixes are applied
- The report becomes the definitive record of what the session produced
- Pass the commit message directly to `git commit -m` after review
- Pass the PR description to the PR creation workflow
