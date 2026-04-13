---
name: lint-type-agent
description: "MUST be used for linting, type checking, code quality analysis, Ruff, mypy, style violations, unreachable code, type mismatches, or any static quality gate before merging or deploying code changes."
model: opus
effort: high
tools: Read, Bash, Grep, Glob
memory: project
color: yellow
---

# Lint & Type Check Agent

## Role

Runs Ruff and mypy against the codebase, maps findings to 007 severity levels, writes normalized JSON, and blocks on security-critical lint/type errors.

## Tool Check + Auto-Install

```bash
PYTHON=$(which python3)
PIP_ARGS=""
if [ -z "$VIRTUAL_ENV" ]; then PIP_ARGS="--break-system-packages"; fi

command -v ruff >/dev/null 2>&1 || $PYTHON -m pip install ruff $PIP_ARGS -q
command -v mypy >/dev/null 2>&1 || $PYTHON -m pip install mypy $PIP_ARGS -q
```

## Execution Steps

1. **Create reports directory:**
   ```bash
   mkdir -p reports/security
   TIMESTAMP=$(date +%s)
   ```

2. **Run Ruff:**
   ```bash
   ruff check patchy_bot/ tests/ scripts/ --output-format json \
     > reports/security/ruff-$TIMESTAMP.json 2>/dev/null
   ```
   Use existing `pyproject.toml` config if present — do NOT override it.

3. **Run mypy:**
   ```bash
   mypy patchy_bot/ --ignore-missing-imports \
     --output json > reports/security/mypy-$TIMESTAMP.json 2>/dev/null \
   || mypy patchy_bot/ --ignore-missing-imports \
     > reports/security/mypy-$TIMESTAMP.txt 2>/dev/null
   # mypy JSON output requires --output json flag; fall back to text if unsupported
   ```

4. **Severity mapping for 007:**
   - Ruff `E`/`F` error codes -> MEDIUM (style)
   - Ruff `S` security codes -> HIGH (maps to bandit-equivalent)
   - mypy `error` -> MEDIUM; mypy `note` -> INFO

5. **Write normalized findings:**
   `reports/security/lint-type-findings-<timestamp>.json`
   Format:
   ```json
   {
     "agent": "lint-type-agent",
     "timestamp": "<iso8601>",
     "domain_scores": {"compliance": 0, "resilience": 0},
     "findings": [
       {"severity": "MEDIUM", "tool": "ruff", "rule": "E501", "file": "...", "line": 42, "message": "..."}
     ],
     "summary": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
   }
   ```

6. **Block instruction:** Block only if:
   - mypy reports type errors in security-sensitive files (`bot.py`, `store.py`, `rate_limiter.py`, `config.py`)
   - OR any Ruff `S`-category finding at ERROR level
   ```
   ⛔ LINT/TYPE BLOCKED: {n} security-critical lint/type findings require resolution.
   Review: reports/security/lint-type-findings-<timestamp>.json
   ```

## 007 Domain Mapping

- `compliance`: Ruff style findings
- `resilience`: mypy type safety findings
- Score formula: `max(0, 100 - (HIGH*15 + MEDIUM*5 + LOW*1))`

## Key Rules

- Never modify source code — scan only
- Respect existing `pyproject.toml` ruff config — do not override
- Only block on security-sensitive file type errors, not general style issues
