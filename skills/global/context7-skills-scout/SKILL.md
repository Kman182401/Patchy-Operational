---
name: context7-skills-scout
description: >
  Automatically discover, evaluate, and manage Context7 registry skills for external
  libraries and frameworks. Activates when working with any external library, API,
  or framework — including python-telegram-bot, TMDB, qBittorrent, Plex, asyncio,
  SQLite, pytest, aiohttp, and any other dependency. Handles skill discovery via
  ctx7 CLI, scan log caching, inline one-off usage, and permanent install promotion.
  Triggers on: any library API call, import statement for external package, framework
  configuration, dependency interaction, test setup with external mocks, or any task
  where library documentation is relevant. Also triggers on "search skills", "find
  skills", "context7 skills", "check for skills", or "skill scout".
context: fork
allowed-tools: Bash, Read, Write
---

# Context7 Skills Scout

Discover, evaluate, and manage Context7 registry skills for libraries used in the current task. This skill runs automatically alongside Context7 documentation lookups.

## Prerequisites
- `ctx7` CLI installed globally (`npm install -g ctx7`)
- Context7 API key configured (`ctx7 setup --cli --claude` completed)
- Reference file exists: `~/.claude/references/context7-skill-scan-log.md`

## Workflow

### Phase 1: Library Detection
When a task begins, identify all external libraries/frameworks/APIs involved:
- Read the files being modified — check import statements
- Check the task description for library mentions
- Include transitive dependencies if relevant (e.g., task uses `handlers/search.py` which imports `tmdbsimple`)

### Phase 2: Scan Log Check
For each identified library, check `~/.claude/references/context7-skill-scan-log.md`:

1. **Read the scan log** — find the entry for this library
2. **If entry exists**, check the `last_scanned` date:
   - **Fast-moving libraries** (React, Next.js, major frameworks with frequent releases): re-scan if older than ~7 days
   - **Moderate libraries** (python-telegram-bot, TMDB wrappers, pytest plugins): re-scan if older than ~14 days
   - **Stable libraries** (SQLite, asyncio, standard lib, mature tools): re-scan if older than ~30 days
   - Use your judgment — if a library had a major version release recently, re-scan regardless
3. **If no entry exists** or entry is stale → proceed to Phase 3
4. **If entry is fresh** → use cached results, skip to Phase 4

### Phase 3: Skill Discovery
Run the Context7 skills search for the library:

```bash
# Search for available skills
ctx7 skills search <library-name>

# Example:
ctx7 skills search python-telegram-bot
ctx7 skills search tmdb
ctx7 skills search asyncio
```

After getting results:

1. **Evaluate each skill** found:
   - Read the skill's description — is it relevant to this project's use of the library?
   - Check quality signals — description clarity, specificity, author reputation if visible
   - Discard skills that are clearly for different use cases (e.g., a React skill when we use the lib for Python)
2. **Update the scan log** with results:
   - Library name, Context7 library ID, scan date
   - Skills found (name, ID, brief description, relevance assessment)
   - Skills skipped and why

### Phase 4: Skill Usage Decision

For each relevant skill found:

**Evaluate for permanent install if ALL of these are true:**
- The library is a core dependency of the project (appears in requirements/pyproject.toml)
- The skill covers patterns that will be used repeatedly (not a one-off edge case)
- The skill's scope matches how this project uses the library
- No existing installed skill already covers this library adequately

**If permanent install is warranted:**
```bash
ctx7 skills install <skill-id> --claude --global
```
- Update scan log: status = "installed", install_date = today
- Inform the user what was installed and why

**If one-off inline usage is better:**
- Fetch the skill's content and read it into current context
- Apply the skill's guidance for this task only
- Update scan log: usage_count++ for this skill
- Do NOT install the skill file

### Phase 5: Promotion Check (Ongoing)

After using a skill inline, check the scan log for promotion signals:

**Promote to permanent install when:**
- The skill has been used inline 3+ times across different sessions
- The library is core to the project stack
- The skill consistently improved output quality or caught patterns that would have been missed
- The skill covers broad use cases, not just one narrow scenario

**Keep as one-off when:**
- The skill was only relevant to a specific, uncommon task
- The library is a transitive or rarely-touched dependency
- An existing installed skill already covers most of the same ground

When promoting: run `ctx7 skills install <skill-id> --claude --global`, update scan log, inform the user.

## Scan Log Format

The scan log at `~/.claude/references/context7-skill-scan-log.md` uses this structure:

```markdown
## <Library Name>
- **Context7 ID:** /org/repo
- **Last Scanned:** YYYY-MM-DD
- **Staleness Tier:** fast | moderate | stable
- **Skills Found:**
  - `skill-name` (skill-id) — Relevant: yes/no — Status: installed | inline | skipped
    - Reason: [why this decision was made]
    - Usage Count: N (for inline skills)
    - Install Date: YYYY-MM-DD (for installed skills)
- **Notes:** [any context about this library's skill landscape]
```

## Important Rules

- NEVER install a skill without evaluating it first — community skills vary in quality
- ALWAYS update the scan log after any discovery or usage action
- If `ctx7 skills search` returns no results, log that too (prevents re-scanning for libraries with no skills)
- If a skill seems low quality or suspicious, skip it and note why in the log
- When in doubt about install vs inline, default to inline — it's reversible
