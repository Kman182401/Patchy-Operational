---
name: context-preflight
description: >
  Pre-flight context analyzer for plans and prompts being handed off to another AI.
  Reads a plan, prompt, task description, or implementation spec and identifies the
  project or system being referenced, then enumerates every file needed for full context.
  Produces a structured Context Manifest — a ranked, categorized list of files with
  justifications — so the receiving AI has everything it needs to execute correctly.
  Use when the user says "context-preflight", "what files does this need", "gather
  context for this prompt", "what context should I attach", "prep context for Claude",
  "what files go with this plan", "context check", "run preflight on this", or any
  variation where a plan or prompt exists and the user wants to know which files to
  include alongside it. NOT for writing plans (use plan-to-prompt), NOT for analyzing
  plan quality (use plan-analyzer), NOT for running the plan itself.
context: fork
allowed-tools: Read, Write, Bash, Glob, LS
---

<!-- Created: 2026-04-06 | Platform: Claude Code -->

# Context Preflight

Analyze a plan, prompt, or task description and produce a **Context Manifest** — a structured, prioritized list of every file the receiving AI needs to execute it correctly.

The core problem this solves: AI models fail or hallucinate when they lack context. A plan that says "refactor the scoring logic" means nothing without the scorer file, the tests, the config it reads, and the CLAUDE.md that defines the project's rules. This skill finds all of that.

---

## Phase 1: Parse the Plan

Read the plan/prompt/task the user has provided. Extract every signal that identifies the project, system, or codebase being targeted.

**Identity signals to extract:**

- **Explicit names:** Project names, repo names, service names, bot names, class/module names (`Patchy_Bot`, `openclaw-kraken`, `FuzzyAI`, `File-Window`, etc.)
- **Path mentions:** Any file paths, directories, or filenames referenced directly
- **Technology markers:** Languages, frameworks, libraries, tools mentioned (`qBittorrent`, `IBKR`, `Telegram`, `pytest`, `Docker`, etc.)
- **Domain vocabulary:** Domain-specific terms that uniquely identify a system (e.g., "torrent quality scoring", "options expiry", "CTF binary analysis")
- **Task verbs + nouns:** What is being modified and where (e.g., "refactor the codec filter", "fix the scoring logic", "add a new agent to")
- **Implied context:** References to "the existing tests", "the current config", "our CLAUDE.md", "the hook" — any definite article pointing to something that must already exist

Build a **Signal Summary** before proceeding:
```
Project/System: <identified name>
Root directory: <likely path>
Tech stack: <languages, frameworks>
Explicit file refs: <any files named directly>
Domain markers: <key terms>
Ambiguities: <anything unclear>
```

If the project cannot be identified from the plan alone, check `~/CLAUDE.md` and `~/.claude/CLAUDE.md` for project listings before asking the user.

---

## Phase 2: Locate the Project Root

Once the project is identified, find its root on the filesystem.

```bash
# Check common locations first
ls ~/                          # Home directory projects
ls ~/.claude/agents/           # Claude Code agents
ls ~/.claude/skills/           # User-level skills
find ~ -maxdepth 3 -name "CLAUDE.md" 2>/dev/null   # CLAUDE.md anchors
find ~ -maxdepth 3 -name "package.json" -o -name "pyproject.toml" -o -name "Cargo.toml" 2>/dev/null
```

Confirm the root before proceeding. If multiple candidates exist, pick the most specific match and note the others.

---

## Phase 3: Gather Context Files

Work through four tiers systematically. For each file found, record its **path** and **reason it's needed**.

### Tier 1 — Always Include (Project Identity)

These files define what the project is and how it must be worked on. Always include if they exist.

| File | Why |
|------|-----|
| `CLAUDE.md` (project-level) | Rules, architecture decisions, anti-patterns, agent routing for this project |
| `~/CLAUDE.md` | Global rules that apply across all projects |
| `~/.claude/CLAUDE.md` | Claude Code global config |
| `README.md` / `README` | Project overview, setup, architecture summary |
| `pyproject.toml` / `setup.py` / `requirements.txt` | Python dependency context |
| `package.json` / `package-lock.json` | Node.js dependency and script context |
| `Cargo.toml` | Rust project manifest |
| `docker-compose.yml` / `Dockerfile` | Container topology |
| `.env.example` / `config.example.*` | Config structure (never real `.env`) |

### Tier 2 — Task-Specific (Direct Task Files)

Files directly referenced in the plan or that contain the code/data being changed.

Search strategy:
```bash
# Find files matching names mentioned in the plan
grep -r "<component_name>" <project_root> --include="*.py" -l
grep -r "<function_name>" <project_root> --include="*.py" -l
find <project_root> -name "<filename_pattern>"

# Find the module containing the class/function being modified
grep -r "class <ClassName>" <project_root> -l
grep -r "def <function_name>" <project_root> -l
```

Include:
- The specific source file(s) being modified
- Any file imported by or importing those source files (1 level deep)
- The config file read by the affected module
- Test files that cover the affected code

### Tier 3 — Supporting Context (Structural Understanding)

Files that help the AI understand the system's overall structure and constraints.

```bash
# Project structure snapshot
find <project_root> -maxdepth 3 -type f \( -name "*.py" -o -name "*.ts" -o -name "*.js" \) \
  | grep -v __pycache__ | grep -v node_modules | grep -v ".git"
```

Include selectively:
- Main entry point (`main.py`, `index.ts`, `bot.py`, `app.py`, etc.)
- Core data models / schemas / types
- Agent `.md` files if the plan involves Claude Code agents
- Hook scripts if hooks are referenced
- The test runner config (`pytest.ini`, `jest.config.js`, etc.)
- CI config (`.github/workflows/`) if the plan touches CI

### Tier 4 — Reference Only (Lookup Files)

Files too large to read fully but useful for the AI to know exist and be able to query.

- Large data files, trained models, full test suites
- Note these by path only with a recommendation: "Include if the AI needs to run tests" or "Reference only — include if full context is required."

---

## Phase 4: Produce the Context Manifest

Output a clean, structured manifest in this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT PREFLIGHT REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT IDENTIFIED
  Name:      <project name>
  Root:      <absolute path>
  Stack:     <tech stack>
  Task type: <what the plan is doing>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXT MANIFEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[ TIER 1 — ALWAYS INCLUDE ]
  ~/Patchy_Bot/CLAUDE.md
    → Project rules, anti-patterns, agent routing
  ~/CLAUDE.md
    → Global rules (applies to all projects)
  ~/Patchy_Bot/README.md
    → Architecture overview and setup

[ TIER 2 — TASK-SPECIFIC ]
  ~/Patchy_Bot/patchy_bot/quality_filter.py
    → Contains the scoring logic being modified
  ~/Patchy_Bot/patchy_bot/config.py
    → Config read by quality_filter; defines codec lists
  ~/Patchy_Bot/tests/test_quality_filter.py
    → Tests covering the affected code

[ TIER 3 — SUPPORTING CONTEXT ]
  ~/Patchy_Bot/patchy_bot/bot.py
    → Main entry point; shows how filter is invoked
  ~/Patchy_Bot/pyproject.toml
    → Dependency context (RTN version, etc.)

[ TIER 4 — REFERENCE ONLY ]
  ~/Patchy_Bot/tests/  (full suite, 162 tests)
    → Include only if running the full test suite

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAPS & WARNINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠  <any missing files, ambiguities, or risks>
  ⚠  <e.g., "Plan references 'the hook' but no hook file found">
  ⚠  <e.g., "Config file contains secrets — use .env.example instead">

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDED ATTACHMENT ORDER
  1. CLAUDE.md files (rules first)
  2. README / architecture docs
  3. Direct task files
  4. Supporting files
  5. Config / manifests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Phase 5: Gap Analysis

After producing the manifest, check for gaps — things the plan implies exist but that couldn't be found.

Common gaps:
- Plan references a function/class that doesn't exist yet (new feature work — note this explicitly)
- Plan mentions a config key that isn't in any found config file
- Plan references "the tests" but no test files exist
- Plan involves an agent or hook whose file is missing
- Plan modifies a shared utility used by other modules not included in the manifest

Flag every gap in the **GAPS & WARNINGS** section. Do not silently omit them.

---

## Behavioral Rules

**Read broadly, report precisely.** Scan more files than needed during analysis, but only surface files that genuinely contribute context. Don't pad the manifest.

**Secrets rule.** Never include `.env`, `secrets.*`, `credentials.*`, or any file likely to contain API keys or passwords. Substitute `.env.example` or equivalent sanitized versions. Call this out explicitly if the plan requires knowing config values.

**Ambiguous project → ask once.** If two or more projects could match the plan's signals, list both candidates and ask the user to confirm before proceeding. Don't guess.

**Large files.** If a relevant file exceeds ~500 lines, include it but note: "Large file — AI should read selectively or focus on [section]."

**Absolute paths only.** All manifest entries use absolute paths (e.g., `/home/karson/Patchy_Bot/...`). No relative paths.

---

## Output Format

Produce the Context Manifest directly in the chat — no file creation unless the user asks for a saved manifest. The report should be readable at a glance so the user can immediately copy file paths into their tool of choice.
