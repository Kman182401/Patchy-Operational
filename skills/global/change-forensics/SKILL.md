---
name: change-forensics
description: >
  Forensic-grade change analysis. Use after any Claude Code session to build a complete,
  precise inventory of every file created, modified, or deleted — with intent-vs-reality
  comparison and unexpected change detection. Trigger phrases: "what exactly changed",
  "change forensics", "show me everything that was touched", "full change inventory",
  "what files were affected", "trace the changes", "what did the session modify",
  "forensic analysis", "change map", "what got changed and why", "list all changes",
  "show me the diff breakdown". Goes deeper than git diff — traces the complete blast path
  of changes including hidden side effects, auto-generated files, config mutations, and lock
  file churn. Use before post-changes-audit, diff-review, or any time you need a precise
  accounting of a session's work. Feeds its file list and UNEXPECTED items directly into
  impact-radar, scope-guard, and regression-guard.
argument-hint: "[optional: path scope, git ref, or time window e.g. '30min' or 'HEAD~3']"
---

# change-forensics

Forensic-grade inventory of every change made in a session. Answers three questions precisely:
**What changed? What was expected to change? What was NOT expected to change?**

## Forensic Collection Protocol

Execute every step. Do not skip steps because you think results will be empty — absence of
findings is itself a valid finding.

### Step 1: Git State Capture

```bash
# Full working tree status
git status --porcelain=v2 --branch

# Staged diff with stats
git diff --cached --stat
git diff --cached

# Unstaged diff
git diff --stat
git diff

# Recent commit history (last 10)
git log --oneline -10

# Stash state
git stash list
```

### Step 2: Filesystem Timeline Scan

```bash
# Files modified in last 30 minutes (captures what git may not show)
find . \
  -not -path './.git/*' \
  -not -path './node_modules/*' \
  -not -path './__pycache__/*' \
  -not -path './dist/*' \
  -not -path './build/*' \
  -newer .git/index \
  -type f \
  -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -50

# New untracked files
git ls-files --others --exclude-standard

# Recently deleted files
git diff --name-status --diff-filter=D HEAD 2>/dev/null
```

### Step 3: Classify Every Changed File

For each file found in Steps 1–2, assign exactly one classification:

| Class | Meaning |
|---|---|
| `PRIMARY` | Direct target of the stated task |
| `COLLATERAL` | Changed as a known side effect of primary work |
| `LOCKFILE` | Package lock / dependency manifest updated |
| `GENERATED` | Auto-generated (migrations, compiled output, snapshots, mocks) |
| `CONFIG` | Config, environment, or settings file |
| `TEST` | Test or spec file |
| `UNEXPECTED` | Changed with no clear link to the stated task — flag for scope review |

### Step 4: Per-File Change Breakdown

For each `PRIMARY` and `UNEXPECTED` file, extract:

```bash
# Line counts
git diff --numstat HEAD -- "$FILE" 2>/dev/null

# Function/class diffs (added or removed definitions)
git diff HEAD -- "$FILE" 2>/dev/null | grep "^[+-]" | \
  grep -E "^[+-](def |async def |class |function |async function |export (function|class|const|default)|pub fn |func )[A-Za-z]"

# Import changes
git diff HEAD -- "$FILE" 2>/dev/null | grep "^[+-]" | \
  grep -E "^[+-](import |from |require\(|#include)"

# Config key changes (for .json, .yaml, .toml, .env)
git diff HEAD -- "$FILE" 2>/dev/null | grep "^[+-]" | \
  grep -vE "^[+-]{3}" | head -20
```

### Step 5: Intent vs. Reality Comparison

Extract the stated task intent from these sources (priority order):
1. Most recent user message in session context
2. Any plan file: `.claude/plan.md`, `PLAN.md`, `TODO.md`
3. Recent commit message: `git log -1 --format=%B`

Compare:
- Files the task description implies should change
- Files that actually changed
- **Gap:** files expected but missing + files changed but unexplained

### Step 6: Side Effect Detection

```bash
# Lock file changes without explicit dependency update in context
git diff --name-only | grep -E "(package-lock\.json|yarn\.lock|poetry\.lock|Cargo\.lock|go\.sum|pnpm-lock\.yaml)"

# Secrets or sensitive files touched
git diff --name-only | grep -iE "(\.env|\.pem$|\.key$|credentials|secret|token)"

# Config files outside stated scope
git diff --name-only | grep -E "\.(json|yaml|yml|toml|ini|conf)$"

# Binary files modified (cannot scan content)
git diff --name-only | xargs file 2>/dev/null | grep -iv "text" | head -10
```

## Output Format

```
## Change Forensics Report

**Session scope (inferred):** [task description]
**Collection window:** git diff + filesystem last 30min
**Total changed:** N files (+X added / -Y removed / Z modified)

### Primary Changes (expected, task-related)
| File | Class | +/- Lines | Summary |
|------|-------|-----------|---------|
| path/to/file.py | PRIMARY | +42 / -8 | Added validation fn, updated error handling |

### Collateral Changes (side effects)
| File | Class | +/- Lines | Summary |
|------|-------|-----------|---------|

### Infrastructure Changes (lock files, generated, config)
| File | Class | +/- Lines | Summary |
|------|-------|-----------|---------|

### Tests Changed
| File | Class | +/- Lines | Summary |
|------|-------|-----------|---------|

### ⚠️ UNEXPECTED Changes (not explained by stated task)
| File | Class | +/- Lines | Why Flagged |
|------|-------|-----------|-------------|

### Intent vs. Reality
- **Expected but NOT changed:** [files implied by task but untouched]
- **Changed but NOT explained:** [files changed with no clear task link]
- **Gap assessment:** ALIGNED | MINOR DRIFT | SIGNIFICANT DRIFT

### Side Effects Detected
[List with severity, or "None detected"]

### Raw File List (pipe to other tools)
[newline-separated list of all changed files]
```

## Integration

Feed the output of this skill into:
- `impact-radar` — pass the raw file list as the trace target
- `scope-guard` — pass the UNEXPECTED items for scope review
- `regression-guard` — pass the PRIMARY files as regression targets
- `post-changes-audit` — this skill runs as Stage 1 of the full audit chain
