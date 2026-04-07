---
name: impact-radar
description: >
  Downstream impact and blast radius analysis. Use after code changes to determine what other
  files, modules, tests, services, and systems are affected by what was just modified. Trigger
  phrases: "what else is affected", "impact analysis", "blast radius", "what depends on this",
  "downstream impact", "what could break from these changes", "impact radar", "dependency trace",
  "ripple analysis", "what imports this", "who uses this", "what calls this", "trace dependencies",
  "reverse dependency check". Traces import graphs, reverse dependencies, test coverage overlaps,
  config references, and API contract consumers to surface the complete set of things the changes
  could affect — not just the files that changed. Essential before merging, deploying, or claiming
  a change is isolated. Use after change-forensics provides the file list, or pass files directly
  as arguments. Feeds its Recommended Regression Targets into regression-guard.
argument-hint: "[file, directory, or comma-separated list to trace — or empty to use recent changes]"
---

# impact-radar

Traces the full downstream impact of code changes. Tells you what changed AND what that change
could ripple into — before it reaches production.

## Impact Categories

| Category | What It Measures |
|---|---|
| **Direct importers** | Files that import/require the changed module |
| **Test coverage overlap** | Tests that exercise the changed code |
| **API contract consumers** | Files calling functions whose signatures changed |
| **Config consumers** | Code reading config keys or env vars you modified |
| **Shared state** | Globals, singletons, shared objects modified |
| **Database schema impact** | Tables, columns, indexes affected by model changes |
| **External integrations** | External services, webhooks, SDKs touching changed code |

## Execution Protocol

### Step 1: Establish File List

If `$ARGUMENTS` contains specific files or paths, use those. Otherwise:
```bash
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only)
echo "Tracing impact for: $CHANGED_FILES"
```

### Step 2: Reverse Dependency Trace (language-aware)

Run the appropriate tracer for each file's language:

**Python:**
```bash
MODULE=$(basename "$FILE" .py)
PKG=$(dirname "$FILE" | tr '/' '.')
grep -rn -e "import ${MODULE}" -e "from ${PKG}" -e "from .${MODULE}" \
  --include="*.py" . | grep -v "^${FILE}:" | head -50
```

**JavaScript / TypeScript:**
```bash
BASE=$(basename "$FILE" | sed 's/\.[jt]sx\?//')
grep -rn -e "from '.*${BASE}'" -e "require('.*${BASE}')" \
  --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" . \
  | grep -v "^${FILE}:" | head -50
```

**Go:**
```bash
PKG=$(head -1 "$FILE" | grep "^package" | awk '{print $2}')
grep -rn "\".*/${PKG}\"" --include="*.go" . | head -50
```

**General — exported name grep (all languages):**
```bash
grep -oE "^(def |class |function |export (const|function|class|default) |pub fn |func )[A-Za-z_][A-Za-z0-9_]*" \
  "$FILE" | awk '{print $NF}' | sort -u | while read NAME; do
    COUNT=$(grep -rn "\b${NAME}\b" \
      --include="*.py" --include="*.ts" --include="*.js" --include="*.go" \
      . | grep -v "^${FILE}:" | wc -l)
    [ "$COUNT" -gt 0 ] && echo "${NAME}: ${COUNT} external references"
  done
```

### Step 3: Test Coverage Overlap

```bash
# Find test files referencing any changed file by basename
for FILE in $CHANGED_FILES; do
  BASE=$(basename "$FILE" | sed 's/\.[^.]*$//')
  grep -rln "$BASE" \
    --include="*test*" --include="*spec*" --include="test_*.*" . 2>/dev/null | head -20
done

# List collected test files
python -m pytest --collect-only -q 2>/dev/null | grep -E "test_" | head -30
npx jest --listTests 2>/dev/null | head -20
```

### Step 4: Config and Environment Variable Impact

```bash
# Extract env vars referenced in changed files
grep -ohE '\$\{?[A-Z_]{3,}\}?|os\.environ\[.+?\]|process\.env\.[A-Z_]+|os\.getenv\(.+?\)' \
  $CHANGED_FILES 2>/dev/null | sort -u

# For each env var found, trace consumers in codebase
# (repeat per var)
grep -rn "VAR_NAME" \
  --include="*.py" --include="*.ts" --include="*.js" \
  --include="*.env*" --include="*.yaml" --include="*.yml" . | head -20
```

### Step 5: API Contract Change Detection

```bash
# Detect signature changes in changed files
for FILE in $CHANGED_FILES; do
  git diff HEAD "$FILE" 2>/dev/null | grep "^[+-]" | \
    grep -E "(def |function |async function |export (function|const))" | head -20
done
```

For each changed signature, find all callers:
```bash
grep -rn "FUNCTION_NAME(" \
  --include="*.py" --include="*.ts" --include="*.js" . | head -30
```

### Step 6: Database Schema Impact

If migration files or ORM model files are in the changed list:
```bash
# Find queries/models referencing changed tables
grep -rn "TABLE_NAME\|ModelClass" \
  --include="*.py" --include="*.ts" --include="*.js" --include="*.sql" . | head -30

# Check for pending unapplied migrations
ls -la migrations/ db/migrate/ alembic/versions/ prisma/ 2>/dev/null | tail -10
```

## Impact Scoring

Score each impacted item on two axes:

| Axis | Levels |
|---|---|
| **Reach** | Low (<5 references), Medium (5–20), High (>20) |
| **Criticality** | Low (util/helper), Medium (business logic), High (auth/payments/data), Critical (public API/core infra) |

**Priority = Reach × Criticality weight** — surface Critical items first regardless of reach.

## Output Format

```
## Impact Radar Report

**Changed files analyzed:** N
**Total downstream references found:** N

### 🔴 Critical Impact (requires immediate attention)
| Item | Impact Type | References | Risk |
|------|-------------|-----------|------|
| auth/middleware.py | Direct Importer | 14 files | Auth bypass risk |

### 🟡 Significant Impact (review recommended)
| Item | Impact Type | References | Risk |
|------|-------------|-----------|------|

### 🟢 Low Impact (informational)
| Item | Impact Type | References | Risk |
|------|-------------|-----------|------|

### Test Coverage Assessment
- **Tests covering changed code:** N test files
- **Tests NOT covering changed code:** [critical untested paths]
- **Coverage gap risk:** LOW / MEDIUM / HIGH

### API Contract Changes
[Signature changes and their callers — or "No signature changes detected"]

### Environment Variable Impact
[Env vars added/changed and their consumers — or "None"]

### Database Impact
[Schema changes and affected queries/models — or "None"]

### Blast Radius Summary
**Total files potentially affected:** N
**Highest-risk area:** [description]
**Recommended regression targets:** [specific test files or commands]
```

## Integration

- Run after `change-forensics` — pass its raw file list as `$ARGUMENTS`
- Pass `Recommended regression targets` into `regression-guard`
- Feed `🔴 Critical Impact` items to `security-reviewer` for targeted review
- This skill runs as Stage 8 of `post-changes-audit`
