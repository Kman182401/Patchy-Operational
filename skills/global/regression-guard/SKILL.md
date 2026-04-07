---
name: regression-guard
description: >
  Regression detection and protection. Run after any code change to verify that existing
  functionality that worked before the change still works after. Trigger phrases: "check for
  regressions", "regression guard", "did anything break", "regression check", "verify nothing
  broke", "test what was working before", "regression test", "did I break anything", "make sure
  existing tests pass", "check backwards compatibility", "verify existing behavior", "test
  regression", "catch regressions", "regression scan". Goes beyond running the test suite —
  identifies which existing behaviors are most at risk from the specific changes made, targets
  those first, and produces a clear pass/fail verdict per regression class. Use after
  implementation, refactors, or any change to shared code. In the post-changes-audit chain,
  run after impact-radar identifies the blast radius and provides regression targets.
argument-hint: "[optional: specific module, function, test file, or 'all' for full suite]"
---

# regression-guard

Systematic regression detection. Finds what the changes broke before production does.

## Regression Classes

| Class | What It Checks |
|---|---|
| **Test regression** | Previously passing tests that now fail |
| **Import regression** | Imports that worked before and now throw errors |
| **Interface regression** | Function/class signatures that callers depend on |
| **Config regression** | Config keys or env vars that existed and are now gone or renamed |
| **Type regression** | Type contracts that changed incompatibly (TypeScript, mypy) |
| **Behavior regression** | Logic paths producing different outputs for same inputs |
| **Performance regression** | Hot paths now executing significantly slower |

## Execution Protocol

### Step 1: Establish Scope

If `$ARGUMENTS` contains specific files or targets, prioritize those. Otherwise:
```bash
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only)
echo "Regression scope: $CHANGED_FILES"
```

If `impact-radar` was already run this session, use its `Recommended regression targets` as the
priority list for Steps 3–5.

### Step 2: Run the Full Test Suite

Execute the test suite for the project. Try in order, stop at first match:

```bash
# Python
pytest --tb=short -x 2>&1 | tail -60

# JavaScript / TypeScript
npm test -- --passWithNoTests 2>&1 | tail -60
npx jest --passWithNoTests 2>&1 | tail -60

# Go
go test ./... 2>&1 | tail -40

# Ruby
bundle exec rspec --format progress 2>&1 | tail -40

# Rust
cargo test 2>&1 | tail -40

# Makefile fallback
make test 2>&1 | tail -40
```

Parse the output for:
- Total tests / passed / failed / skipped
- Names and file locations of any failing tests
- Whether these tests were passing before the change (check `git stash` baseline if possible)

### Step 3: Import Integrity Check

```bash
# Python — verify all changed modules import cleanly
for FILE in $CHANGED_FILES; do
  [[ "$FILE" == *.py ]] && \
    python3 -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('mod', '${FILE}')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    print('OK: ${FILE}')
except Exception as e:
    print(f'IMPORT ERROR: ${FILE} — {e}')
    sys.exit(1)
" 2>&1
done

# TypeScript — full type check
npx tsc --noEmit 2>&1 | grep "error TS" | head -30

# Python type check
python -m mypy . --ignore-missing-imports --no-error-summary 2>&1 | grep "error:" | head -30
```

### Step 4: Interface Regression Check

For each changed file, compare the current exported interface against HEAD:

```bash
for FILE in $CHANGED_FILES; do
  echo "=== Interface diff: $FILE ==="
  # Python: public function/class definitions
  git diff HEAD "$FILE" 2>/dev/null | grep "^[+-]" | \
    grep -E "^[+-](def |class |async def )[A-Za-z_]" | grep -v "^---\|^+++" | head -20

  # JS/TS: exports
  git diff HEAD "$FILE" 2>/dev/null | grep "^[+-]" | \
    grep -E "^[+-]export (function|class|const|default|interface|type)[[:space:]]" | head -20
done
```

Flag any **removed or renamed exported symbol** as HIGH regression risk. Search for callers:
```bash
grep -rn "REMOVED_SYMBOL" \
  --include="*.py" --include="*.ts" --include="*.js" --include="*.go" . | head -20
```

### Step 5: Configuration Regression Check

```bash
# Keys removed from config files
git diff HEAD -- "*.json" "*.yaml" "*.yml" "*.toml" "*.env" 2>/dev/null | \
  grep "^-" | grep -v "^---" | head -30
```

For each removed key, check if it's still referenced in the codebase:
```bash
grep -rn "REMOVED_KEY" \
  --include="*.py" --include="*.ts" --include="*.js" . | head -20
```

### Step 6: Targeted Smoke Tests

For each HIGH-risk function/class from Step 4 — construct a minimal, side-effect-free smoke test:

**Python:**
```bash
python3 -c "
from PATH.TO.MODULE import FUNCTION_NAME
result = FUNCTION_NAME(SAFE_ARGS)
assert result is not None, 'Smoke test returned None'
print(f'✅ Smoke test passed: {result}')
" 2>&1
```

**JavaScript / TypeScript:**
```bash
node -e "
const { FUNCTION_NAME } = require('./path/to/module');
const result = FUNCTION_NAME(SAFE_ARGS);
console.log('✅ Smoke test passed:', result);
" 2>&1
```

Only construct smoke tests for functions with deterministic, read-only behavior.
Never run smoke tests that trigger writes, network calls, or destructive operations.

### Step 7: Performance Regression Check (targeted)

For functions identified as hot paths (called frequently, in loops, or request handlers):

```bash
python3 -c "
import timeit, importlib
mod = importlib.import_module('MODULE_NAME')
t = timeit.timeit(lambda: mod.FUNCTION(ARGS), number=1000)
print(f'1000 calls: {t:.3f}s ({t:.3f}ms avg)')
" 2>&1
```

Flag if timing is >25% slower than the baseline type for that operation.

## Auto-Fix Protocol

Apply minimal, safe fixes automatically when regressions are clearly caused by the recent change:

**Safe to auto-fix:**
- Restore accidentally deleted/renamed exports as aliases
- Update import paths after file renames (only when the rename is confirmed intentional)

**Require human approval before fixing:**
- Logic regressions — behavior change may be intentional
- Signature changes with many callers — impact scope is too large to auto-fix
- Config key renames where the old key has external consumers

## Output Format

```
## Regression Guard Report

**Scope:** [files/modules analyzed]
**Test framework detected:** [pytest / jest / go test / rspec / none found]
**Regression targets from impact-radar:** [N prioritized targets / not available]

### Test Suite Results
- Tests run: N | ✅ Passed: N | ❌ Failed: N | ⏭️ Skipped: N
- **Verdict:** PASS / FAIL / NO TESTS FOUND
- Failing tests: [names, or "None"]

### Import Integrity
- Python imports: ✅ Clean / ❌ N errors
- TypeScript types: ✅ Clean / ❌ N errors
- **Verdict:** PASS / FAIL / N/A

### Interface Regression Analysis
| Symbol | Change Type | Callers Found | Risk Level |
|--------|-------------|---------------|-----------|
| auth.verify() | Signature changed | 8 | 🔴 HIGH |
| utils.format() | Unchanged | 3 | ✅ NONE |

### Configuration Regression
[Removed/renamed config keys and their live consumers — or "No config regressions"]

### Smoke Test Results
| Test | Result | Notes |
|------|--------|-------|
| FUNCTION(safe_args) | ✅ PASS | Returned expected value |

### Performance Check
[Timing results for hot paths — or "Not applicable"]

### Regression Summary
| Class | Status | Details |
|-------|--------|---------|
| Test regression | ✅ / ❌ / ⚠️ | |
| Import regression | ✅ / ❌ / ⚠️ | |
| Interface regression | ✅ / ❌ / ⚠️ | |
| Config regression | ✅ / ❌ / ⚠️ | |
| Type regression | ✅ / ❌ / ⚠️ | |
| Performance regression | ✅ / ❌ / ⚠️ | |

### Auto-Fixes Applied
[List — or "None / Read-only mode"]

**REGRESSION VERDICT: ✅ CLEAN | ⚠️ WARN | 🚫 REGRESSION DETECTED**
[If REGRESSION DETECTED: exact failures and recommended fixes]
```

## Integration

- Run after `impact-radar` — use its `Recommended regression targets` as priority input
- Pass failing test names to `analyze` as context for the repair pass
- Regression verdict feeds into the `post-changes-audit` Phase 3 summary
- This skill runs as Stage 9 of `post-changes-audit`
