#!/usr/bin/env bash
#
# gather-context.sh — Scans the current working directory and outputs a
# structured markdown context report for use by a Claude.ai Project builder skill.
#
# Usage: ./gather-context.sh
# Output: Markdown to stdout
#
# Safety: NEVER reads .env, private keys, credentials, or secrets files.

set -uo pipefail

BASE="$PWD"
DATE="$(date +%Y-%m-%d)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Check if a command exists
has_cmd() { command -v "$1" >/dev/null 2>&1; }

# Safe timeout wrapper — skips timeout if not available
safe_timeout() {
  if has_cmd timeout; then
    timeout "$@"
  else
    # Drop the timeout arg and run directly
    shift
    "$@"
  fi
}

# Print first N lines of a file, with a code block
print_file_head() {
  local file="$1"
  local lines="${2:-50}"
  if [ -f "$file" ]; then
    echo "\`\`\`"
    head -n "$lines" "$file"
    echo "\`\`\`"
  fi
}

# Prune directories excluded from all find calls (inline in each call below)

# Count files matching a glob pattern (excluding common junk dirs)
# Uses maxdepth 6 to avoid crawling massive trees
count_files() {
  local ext="$1"
  if has_cmd find; then
    safe_timeout 2 find "$BASE" -maxdepth 6 \
      -path '*/node_modules' -prune -o \
      -path '*/.git' -prune -o \
      -path '*/__pycache__' -prune -o \
      -path '*/venv' -prune -o \
      -path '*/.venv' -prune -o \
      -path '*/dist' -prune -o \
      -path '*/build' -prune -o \
      -path '*/.next' -prune -o \
      -path '*/target' -prune -o \
      -path '*/.tox' -prune -o \
      -name "*.$ext" -type f -print 2>/dev/null | wc -l | tr -d ' '
  else
    echo "0"
  fi
}

# Search a file for a pattern (case-insensitive), return 0 if found
file_contains() {
  local file="$1"
  local pattern="$2"
  grep -qi "$pattern" "$file" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

echo "# Project Context Report"
echo "Generated: $DATE"
echo ""

# ---------------------------------------------------------------------------
# Project Identity
# ---------------------------------------------------------------------------

echo "## Project Identity"
echo ""

# --- Project name ---
proj_name=""
if [ -f "$BASE/package.json" ] && has_cmd grep && has_cmd sed; then
  proj_name="$(grep '"name"' "$BASE/package.json" 2>/dev/null | head -1 | sed 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
fi
if [ -z "$proj_name" ] && [ -f "$BASE/pyproject.toml" ]; then
  proj_name="$(grep -A1 '^\[project\]' "$BASE/pyproject.toml" 2>/dev/null | grep '^name' | head -1 | sed 's/.*=[[:space:]]*"\([^"]*\)".*/\1/')"
  if [ -z "$proj_name" ]; then
    proj_name="$(grep -A1 '^\[tool\.poetry\]' "$BASE/pyproject.toml" 2>/dev/null | grep '^name' | head -1 | sed 's/.*=[[:space:]]*"\([^"]*\)".*/\1/')"
  fi
fi
if [ -z "$proj_name" ] && [ -f "$BASE/Cargo.toml" ]; then
  proj_name="$(grep -A5 '^\[package\]' "$BASE/Cargo.toml" 2>/dev/null | grep '^name' | head -1 | sed 's/.*=[[:space:]]*"\([^"]*\)".*/\1/')"
fi
if [ -z "$proj_name" ] && [ -f "$BASE/go.mod" ]; then
  proj_name="$(head -1 "$BASE/go.mod" 2>/dev/null | sed 's/^module[[:space:]]*//')"
fi
if [ -z "$proj_name" ]; then
  proj_name="$(basename "$BASE")"
fi
echo "- **Name:** $proj_name"

# --- Project description ---
proj_desc=""
if [ -f "$BASE/package.json" ]; then
  proj_desc="$(grep '"description"' "$BASE/package.json" 2>/dev/null | head -1 | sed 's/.*"description"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')"
fi
if [ -z "$proj_desc" ] && [ -f "$BASE/pyproject.toml" ]; then
  proj_desc="$(grep '^description' "$BASE/pyproject.toml" 2>/dev/null | head -1 | sed 's/.*=[[:space:]]*"\([^"]*\)".*/\1/')"
fi
if [ -z "$proj_desc" ] && [ -f "$BASE/Cargo.toml" ]; then
  proj_desc="$(grep -A10 '^\[package\]' "$BASE/Cargo.toml" 2>/dev/null | grep '^description' | head -1 | sed 's/.*=[[:space:]]*"\([^"]*\)".*/\1/')"
fi
if [ -z "$proj_desc" ] && [ -f "$BASE/README.md" ]; then
  # Grab first non-empty, non-heading paragraph
  proj_desc="$(sed -n '/^[^#[:space:]]/{ p; q; }' "$BASE/README.md" 2>/dev/null)"
fi
if [ -n "$proj_desc" ]; then
  echo "- **Description:** $proj_desc"
else
  echo "- **Description:** _(none found)_"
fi

# --- Git info ---
if has_cmd git && [ -d "$BASE/.git" ]; then
  remote_url="$(safe_timeout 3 git -C "$BASE" remote get-url origin 2>/dev/null || echo "_(no remote)_")"
  current_branch="$(safe_timeout 3 git -C "$BASE" branch --show-current 2>/dev/null || echo "_(detached)_")"
  echo "- **Git remote:** $remote_url"
  echo "- **Branch:** $current_branch"
  echo ""
  echo "### Recent Commits"
  echo ""
  echo "\`\`\`"
  safe_timeout 3 git -C "$BASE" log --oneline -5 2>/dev/null || echo "_(no commits)_"
  echo "\`\`\`"
else
  echo "- **Git:** not a git repository"
fi
echo ""

# ---------------------------------------------------------------------------
# Tech Stack Detection
# ---------------------------------------------------------------------------

echo "## Tech Stack"
echo ""

# --- Languages by file count (single find pass) ---
echo "### Languages"
echo ""

if has_cmd find; then
  lang_output="$(safe_timeout 3 find "$BASE" -maxdepth 6 \
    -path '*/node_modules' -prune -o \
    -path '*/.git' -prune -o \
    -path '*/__pycache__' -prune -o \
    -path '*/venv' -prune -o \
    -path '*/.venv' -prune -o \
    -path '*/dist' -prune -o \
    -path '*/build' -prune -o \
    -path '*/.next' -prune -o \
    -path '*/target' -prune -o \
    -path '*/.tox' -prune -o \
    -type f \( \
      -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.go' -o \
      -name '*.rs' -o -name '*.java' -o -name '*.rb' -o -name '*.php' -o \
      -name '*.c' -o -name '*.cpp' -o -name '*.cs' -o -name '*.swift' \
    \) -print 2>/dev/null | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -5)"

  if [ -n "$lang_output" ]; then
    echo "$lang_output" | while read -r cnt ext; do
      case "$ext" in
        py) name="Python" ;; js) name="JavaScript" ;; ts) name="TypeScript" ;;
        go) name="Go" ;; rs) name="Rust" ;; java) name="Java" ;;
        rb) name="Ruby" ;; php) name="PHP" ;; c) name="C" ;;
        cpp) name="C++" ;; cs) name="C#" ;; swift) name="Swift" ;;
        *) name="$ext" ;;
      esac
      echo "- **$name:** $cnt files"
    done
  else
    echo "- _(no recognized source files found)_"
  fi
else
  echo "- _(find not available)_"
fi
echo ""

# --- Frameworks ---
echo "### Frameworks"
echo ""

found_framework=false

# Python frameworks
for reqfile in "$BASE/requirements.txt" "$BASE/requirements-dev.txt" "$BASE/requirements_dev.txt" "$BASE/pyproject.toml"; do
  if [ -f "$reqfile" ]; then
    for fw in fastapi flask django celery sqlalchemy; do
      if file_contains "$reqfile" "$fw"; then
        echo "- **$fw** (Python, detected in $(basename "$reqfile"))"
        found_framework=true
      fi
    done
  fi
done

# JS/TS frameworks
if [ -f "$BASE/package.json" ]; then
  for fw in react next express vue angular svelte; do
    if file_contains "$BASE/package.json" "\"$fw\""; then
      echo "- **$fw** (JS/TS, detected in package.json)"
      found_framework=true
    fi
  done
fi

# Ruby
if [ -f "$BASE/Gemfile" ]; then
  if file_contains "$BASE/Gemfile" "rails"; then
    echo "- **rails** (Ruby, detected in Gemfile)"
    found_framework=true
  fi
fi

# Rust
if [ -f "$BASE/Cargo.toml" ]; then
  for fw in actix rocket tokio; do
    if file_contains "$BASE/Cargo.toml" "$fw"; then
      echo "- **$fw** (Rust, detected in Cargo.toml)"
      found_framework=true
    fi
  done
fi

# Go
if [ -f "$BASE/go.mod" ]; then
  for fw in gin echo fiber; do
    if file_contains "$BASE/go.mod" "$fw"; then
      echo "- **$fw** (Go, detected in go.mod)"
      found_framework=true
    fi
  done
fi

if [ "$found_framework" = false ]; then
  echo "- _(no recognized frameworks detected)_"
fi
echo ""

# --- Databases ---
echo "### Databases"
echo ""

found_db=false

if [ -d "$BASE/migrations" ] || [ -d "$BASE/alembic" ]; then
  echo "- Database migrations directory found"
  found_db=true
fi

# Search config files (NOT .env) for DB references
config_files=""
for cf in "$BASE/pyproject.toml" "$BASE/package.json" "$BASE/docker-compose.yml" "$BASE/docker-compose.yaml" "$BASE/config.toml" "$BASE/config.yaml" "$BASE/config.json" "$BASE/settings.py" "$BASE/alembic.ini"; do
  if [ -f "$cf" ]; then
    config_files="$config_files $cf"
  fi
done

if [ -n "$config_files" ]; then
  for db in sqlite postgres postgresql mysql redis mongo mongodb; do
    for cf in $config_files; do
      if file_contains "$cf" "$db"; then
        echo "- **$db** reference found in $(basename "$cf")"
        found_db=true
        break
      fi
    done
  done
fi

if [ "$found_db" = false ]; then
  echo "- _(no database references detected)_"
fi
echo ""

# --- Infrastructure ---
echo "### Infrastructure"
echo ""

found_infra=false

[ -f "$BASE/Dockerfile" ] && echo "- Dockerfile present" && found_infra=true
[ -f "$BASE/docker-compose.yml" ] && echo "- docker-compose.yml present" && found_infra=true
[ -f "$BASE/docker-compose.yaml" ] && echo "- docker-compose.yaml present" && found_infra=true
[ -d "$BASE/terraform" ] && echo "- Terraform directory present" && found_infra=true
[ -d "$BASE/k8s" ] && echo "- Kubernetes (k8s/) directory present" && found_infra=true
[ -d "$BASE/kubernetes" ] && echo "- Kubernetes directory present" && found_infra=true

# systemd service files
if has_cmd find; then
  svc_count="$(safe_timeout 2 find "$BASE" -maxdepth 2 -name '*.service' -type f 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$svc_count" -gt 0 ]; then
    echo "- systemd .service files found ($svc_count)"
    found_infra=true
  fi
fi

# Tailscale references
for cf in "$BASE/docker-compose.yml" "$BASE/docker-compose.yaml" "$BASE/Makefile"; do
  if [ -f "$cf" ] && file_contains "$cf" "tailscale"; then
    echo "- Tailscale reference in $(basename "$cf")"
    found_infra=true
    break
  fi
done

if [ "$found_infra" = false ]; then
  echo "- _(no infrastructure configs detected)_"
fi
echo ""

# --- CI/CD ---
echo "### CI/CD"
echo ""

found_ci=false

[ -d "$BASE/.github/workflows" ] && echo "- GitHub Actions (.github/workflows/)" && found_ci=true
[ -f "$BASE/.gitlab-ci.yml" ] && echo "- GitLab CI (.gitlab-ci.yml)" && found_ci=true
[ -f "$BASE/Jenkinsfile" ] && echo "- Jenkins (Jenkinsfile)" && found_ci=true
[ -d "$BASE/.circleci" ] && echo "- CircleCI (.circleci/)" && found_ci=true

if [ "$found_ci" = false ]; then
  echo "- _(no CI/CD configs detected)_"
fi
echo ""

# ---------------------------------------------------------------------------
# Project Configuration
# ---------------------------------------------------------------------------

echo "## Project Configuration"
echo ""

# --- CLAUDE.md ---
if [ -f "$BASE/CLAUDE.md" ]; then
  echo "### CLAUDE.md"
  echo ""
  echo "\`\`\`markdown"
  cat "$BASE/CLAUDE.md"
  echo "\`\`\`"
  echo ""
fi

# --- .claude/agents/ ---
if [ -d "$BASE/.claude/agents" ]; then
  echo "### Claude Agents"
  echo ""
  for agent_file in "$BASE/.claude/agents"/*.yml "$BASE/.claude/agents"/*.yaml "$BASE/.claude/agents"/*.md; do
    if [ -f "$agent_file" ]; then
      agent_basename="$(basename "$agent_file")"
      # Extract name and description from YAML frontmatter
      agent_name="$(sed -n '/^---$/,/^---$/{/^name:/{ s/^name:[[:space:]]*//; p; q; }}' "$agent_file" 2>/dev/null)"
      agent_desc="$(sed -n '/^---$/,/^---$/{/^description:/{ s/^description:[[:space:]]*//; p; q; }}' "$agent_file" 2>/dev/null)"
      if [ -n "$agent_name" ]; then
        echo "- **$agent_name** ($agent_basename): $agent_desc"
      else
        echo "- $agent_basename"
      fi
    fi
  done
  echo ""
fi

# --- .claude/settings.json (filtered) ---
if [ -f "$BASE/.claude/settings.json" ]; then
  echo "### .claude/settings.json"
  echo ""
  echo "\`\`\`json"
  # Filter out lines containing sensitive field names
  grep -vi -E '"(key|token|secret|password)"' "$BASE/.claude/settings.json" 2>/dev/null || cat "$BASE/.claude/settings.json"
  echo "\`\`\`"
  echo ""
fi

# --- .env.example / .env.template ---
for envfile in "$BASE/.env.example" "$BASE/.env.template"; do
  if [ -f "$envfile" ]; then
    echo "### $(basename "$envfile")"
    echo ""
    echo "\`\`\`"
    cat "$envfile"
    echo "\`\`\`"
    echo ""
  fi
done

# --- Key config files (first 50 lines) ---
for cfgfile in pyproject.toml package.json tsconfig.json Makefile Dockerfile; do
  if [ -f "$BASE/$cfgfile" ]; then
    echo "### $cfgfile"
    echo ""
    print_file_head "$BASE/$cfgfile" 50
    echo ""
  fi
done

# ---------------------------------------------------------------------------
# Codebase Structure
# ---------------------------------------------------------------------------

echo "## Codebase Structure"
echo ""

# --- Directory tree (2 levels) ---
echo "### Directory Tree"
echo ""

if has_cmd find; then
  echo "\`\`\`"
  # Use find to build a simple 2-level tree
  safe_timeout 2 find "$BASE" -maxdepth 2 -type d \
    -not -path '*/node_modules*' \
    -not -path '*/.git*' \
    -not -path '*/__pycache__*' \
    -not -path '*/venv*' \
    -not -path '*/.venv*' \
    -not -path '*/dist*' \
    -not -path '*/build*' \
    -not -path '*/.next*' \
    -not -path '*/target*' \
    -not -path '*/.tox*' \
    2>/dev/null | sort | while read -r dir; do
    # Make path relative to BASE
    rel="${dir#"$BASE"}"
    if [ -z "$rel" ]; then
      echo "./"
    else
      echo ".${rel}/"
    fi
  done
  echo "\`\`\`"
else
  echo "_(find not available)_"
fi
echo ""

# --- Source file count per top-level directory ---
echo "### Files Per Top-Level Directory"
echo ""

if has_cmd find; then
  # Single find pass, extract top-level directory, count per directory
  safe_timeout 3 find "$BASE" -maxdepth 4 \
    -path '*/node_modules' -prune -o \
    -path '*/.git' -prune -o \
    -path '*/__pycache__' -prune -o \
    -path '*/venv' -prune -o \
    -path '*/.venv' -prune -o \
    -path '*/dist' -prune -o \
    -path '*/build' -prune -o \
    -path '*/.next' -prune -o \
    -path '*/target' -prune -o \
    -path '*/.tox' -prune -o \
    -type f -print 2>/dev/null \
    | sed "s|^${BASE}/||" \
    | cut -d/ -f1 \
    | sort \
    | uniq -c \
    | sort -rn \
    | while read -r cnt dirname; do
        # Skip files in the root (no slash = root-level file, dirname = filename)
        if [ -d "$BASE/$dirname" ]; then
          echo "- **$dirname/**: $cnt files"
        fi
      done
else
  echo "_(find not available)_"
fi
echo ""

# --- Test directories ---
echo "### Tests"
echo ""

if has_cmd find; then
  test_dirs="$(safe_timeout 2 find "$BASE" -maxdepth 3 -type d \( -name 'tests' -o -name 'test' -o -name '__tests__' -o -name 'spec' \) \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/venv/*' \
    -not -path '*/.venv/*' \
    2>/dev/null)"
  if [ -n "$test_dirs" ]; then
    echo "$test_dirs" | while read -r td; do
      rel="${td#"$BASE"}"
      tc="$(safe_timeout 2 find "$td" -type f \( -name 'test_*' -o -name '*_test.*' -o -name '*.test.*' -o -name '*.spec.*' -o -name '*Test.*' \) 2>/dev/null | wc -l | tr -d ' ')"
      echo "- **.${rel}/**: $tc test files"
    done
  else
    echo "- _(no test directories found)_"
  fi
else
  echo "_(find not available)_"
fi
echo ""

# --- Entry points ---
echo "### Entry Points"
echo ""

found_entry=false
for ep in main.py index.ts index.js app.py manage.py main.go src/main.rs Program.cs; do
  if [ -f "$BASE/$ep" ]; then
    echo "- \`$ep\`"
    found_entry=true
  fi
done

if [ "$found_entry" = false ]; then
  echo "- _(no standard entry points found)_"
fi
echo ""

# ---------------------------------------------------------------------------
# Security Posture
# ---------------------------------------------------------------------------

echo "## Security Posture"
echo ""

found_security=false

# --- Linter configs ---
[ -f "$BASE/.ruff.toml" ] && echo "- Ruff config: .ruff.toml" && found_security=true
[ -f "$BASE/ruff.toml" ] && echo "- Ruff config: ruff.toml" && found_security=true
if [ -f "$BASE/pyproject.toml" ] && file_contains "$BASE/pyproject.toml" '\[tool\.ruff\]'; then
  echo "- Ruff config in pyproject.toml"
  found_security=true
fi
[ -f "$BASE/.bandit" ] && echo "- Bandit config: .bandit" && found_security=true
[ -f "$BASE/.semgrep.yml" ] && echo "- Semgrep config: .semgrep.yml" && found_security=true

# ESLint (various config names)
for eslint in "$BASE/.eslintrc" "$BASE/.eslintrc.js" "$BASE/.eslintrc.json" "$BASE/.eslintrc.yml" "$BASE/.eslintrc.yaml" "$BASE/eslint.config.js" "$BASE/eslint.config.mjs"; do
  if [ -f "$eslint" ]; then
    echo "- ESLint config: $(basename "$eslint")"
    found_security=true
    break
  fi
done

# --- Pre-commit ---
if [ -f "$BASE/.pre-commit-config.yaml" ]; then
  echo "- Pre-commit hooks configured (.pre-commit-config.yaml)"
  found_security=true
fi

# --- Claude Code security hooks ---
if [ -f "$HOME/.claude/settings.json" ]; then
  if grep -qiE '(security|semgrep|bandit)' "$HOME/.claude/settings.json" 2>/dev/null; then
    echo "- Claude Code security hooks detected in ~/.claude/settings.json"
    found_security=true
  fi
fi

if [ "$found_security" = false ]; then
  echo "- _(no security tooling detected)_"
fi
echo ""

echo "---"
echo "_Report generated by gather-context.sh_"
