---
name: gh-issues
description: "Fetch GitHub issues from Patchy-Operational, route each to the appropriate domain agent for a fix, then open PRs for review. Use when the user says 'fix issues', 'gh-issues', 'auto-fix', 'process issues', or wants to automatically resolve open GitHub issues."
user_invocable: true
---

# GitHub Issues Auto-Fixer

Fetch open issues from the Patchy-Operational repo, route each to the correct domain agent based on labels/keywords, implement fixes on isolated branches, and open PRs for human review.

**Git policy override:** Invoking this skill is explicit permission to run git-write commands (branch, add, commit, push) in `~/Patchy_Bot` for the duration of this skill's execution. All changes go on isolated `fix/issue-<number>` branches — never on `main`.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Route each issue to the matching domain agent per the Agent Routing Table below (sequential — one issue at a time to avoid file conflicts).
- **Review:** After each fix, delegate test verification to the `test-agent`.
- **Security issues:** The `security-agent` is read-only — it produces analysis only. Delegate implementation of its recommendations to a general-purpose agent.
- **On failure:** If an agent's fix breaks tests, give it ONE retry with the error output before abandoning the issue.

## Usage

```
/gh-issues                          # Process all open issues (default)
/gh-issues --label bug              # Only issues with "bug" label
/gh-issues --limit 3                # Process at most 3 issues
/gh-issues --dry-run                # Preview issues without fixing
/gh-issues --reviews-only           # Skip issues, address PR review comments only
/gh-issues --assignee @me           # Only issues assigned to me
```

## Agent Routing Table

Map issue labels to domain agents. First matching label wins. If no label matches, fall back to keyword scanning of the issue title/body.

| Label | Agent | Notes |
|-------|-------|-------|
| `schedule`, `episode`, `tvmaze` | schedule-agent | Episode tracking, metadata, auto-download |
| `security`, `auth`, `rate-limit` | security-agent | **Read-only** — produces analysis only, then a general agent implements the fix |
| `remove`, `delete`, `cleanup` | remove-agent | Deletion flows, path safety, Plex cleanup |
| `search`, `download`, `torrent` | search-download-agent | Torrent search, download tracking |
| `plex`, `media`, `library` | plex-agent | Plex inventory, media organization |
| `config`, `infra`, `service` | config-infra-agent | Config, env vars, systemd, startup |
| `database`, `db`, `store`, `sqlite` | database-agent | Schema, migrations, CRUD methods |
| `ui`, `ux`, `keyboard`, `button` | ui-agent | Telegram UI, keyboards, callbacks |
| `test`, `testing`, `pytest` | test-agent | Tests, mocking, coverage |

**Keyword fallback** (scans title + body if no label matched):
- `schedule`, `episode`, `track` → schedule-agent
- `delete`, `remove`, `cleanup` → remove-agent
- `search`, `download`, `torrent` → search-download-agent
- `plex`, `media`, `library` → plex-agent
- `config`, `env`, `service`, `systemd` → config-infra-agent
- `database`, `db`, `store`, `migration` → database-agent
- `button`, `keyboard`, `menu`, `callback` → ui-agent
- `test`, `pytest`, `coverage` → test-agent
- `security`, `auth`, `password`, `rate limit` → security-agent
- No match → use a general-purpose Agent (no subagent_type)

---

## Phase 1: Parse Arguments

1. Parse the `/gh-issues` invocation for flags:
   - `--label <label>` — filter by GitHub label
   - `--limit <n>` — max issues to process (default: 10)
   - `--dry-run` — preview only, no fixes
   - `--reviews-only` — skip to Phase 6
   - `--assignee <user>` — filter by assignee
   - `--milestone <name>` — filter by milestone
2. Set `REPO="Kman182401/Patchy-Operational"`
3. Set `PROJECT_DIR="$HOME/Patchy_Bot"`
4. If `--reviews-only` is set, skip directly to Phase 6.

## Phase 2: Fetch Issues

Run via `gh` CLI (already authenticated):

```bash
gh issue list --repo Kman182401/Patchy-Operational --state open --limit <LIMIT> [--label <LABEL>] [--assignee <ASSIGNEE>] --json number,title,body,labels,assignees,milestone,url
```

- If zero issues found, report "No open issues match your filters" and stop.
- Display a summary table of fetched issues:

```
| #  | Title                        | Labels         | Agent Route    |
|----|------------------------------|----------------|----------------|
| 3  | Schedule runner crashes on…  | schedule, bug  | schedule-agent |
| 7  | Add rate limit to /start     | security       | security-agent |
```

- If `--dry-run`, display the table and stop here.

## Phase 3: Deduplication & Claiming

For each issue, check if work already exists:

1. **Check for existing PR:**
   ```bash
   gh pr list --repo Kman182401/Patchy-Operational --search "fixes #<NUMBER>" --json number,title,state
   ```
   If an open PR exists for this issue, skip it with a note.

2. **Check for existing branch:**
   ```bash
   git -C ~/Patchy_Bot branch --list "fix/issue-<NUMBER>-*"
   ```
   If a branch already exists, skip it with a note.

3. **Check for remote branch:**
   ```bash
   git -C ~/Patchy_Bot ls-remote --heads origin "fix/issue-<NUMBER>-*"
   ```
   If a remote branch exists, skip it with a note.

Issues that pass all three checks proceed to Phase 4.

## Phase 4: Route & Fix

Process issues **sequentially** (critical — `bot.py` is monolithic, parallel edits would conflict).

For each issue:

### Step 4.1: Create an isolated branch

```bash
cd ~/Patchy_Bot
git checkout main
git pull origin main
git checkout -b fix/issue-<NUMBER>-<slug>
```

Where `<slug>` is a short kebab-case version of the issue title (max 40 chars, alphanumeric + hyphens only).

### Step 4.2: Determine the target agent

Apply the routing table from above:
1. Check issue labels first (exact match against label column)
2. If no label match, scan title + body for keywords
3. If no keyword match, use a general-purpose agent

### Step 4.3: Dispatch to the agent

**For non-security agents:**

Spawn the matched agent using the Agent tool with:
- `subagent_type`: the matched agent name (e.g., `schedule-agent`)
- `prompt`: Include:
  - The full issue title, body, and number
  - "Fix this issue. Make minimal, targeted changes."
  - "Work in `/home/karson/Patchy_Bot/telegram-qbt/`"
  - "Do NOT commit — just edit the files."
  - "After editing, run: `cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest -q`"
  - "Report what you changed and whether tests pass."

**For security-agent (read-only — no Write/Edit tools):**

Two-step process:
1. Spawn `security-agent` with:
   - "Analyze this issue and produce a detailed fix specification: which files to change, what to change, and why. Do NOT attempt to edit files."
2. Take the security-agent's analysis and spawn a general-purpose Agent with:
   - The security-agent's analysis as context
   - "Implement these security fixes exactly as specified."
   - "Work in `/home/karson/Patchy_Bot/telegram-qbt/`"
   - "Do NOT commit — just edit the files."
   - "After editing, run: `cd /home/karson/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest -q`"

### Step 4.4: Verify the fix

After the agent completes:

1. Run the full test suite:
   ```bash
   cd ~/Patchy_Bot/telegram-qbt && .venv/bin/python -m pytest -q
   ```

2. Run ruff lint check:
   ```bash
   cd ~/Patchy_Bot/telegram-qbt && .venv/bin/python -m ruff check .
   ```

3. If tests or lint fail:
   - Give the agent ONE retry with the error output
   - If it fails again, abandon this issue's branch and report the failure

### Step 4.5: Stage and commit

Only if verification passed:

```bash
cd ~/Patchy_Bot
git add -A
git diff --cached --name-only | grep -iE '\.env$|\.env\.|state\.sqlite3|settings\.local\.json'
```

If the safety check finds secrets, abort this issue. Otherwise:

```bash
git commit -m "fix: resolve #<NUMBER> — <issue title summary>"
```

### Step 4.6: Push the branch

```bash
git push -u origin fix/issue-<NUMBER>-<slug>
```

Then return to `main` before processing the next issue:

```bash
git checkout main
```

## Phase 5: Open Pull Requests

For each successfully pushed branch, create a PR:

```bash
gh pr create \
  --repo Kman182401/Patchy-Operational \
  --head "fix/issue-<NUMBER>-<slug>" \
  --base main \
  --title "fix: resolve #<NUMBER> — <short title>" \
  --body "$(cat <<'EOF'
## Summary

Fixes #<NUMBER>

<1-3 bullet points describing the changes>

## Agent

Routed to: `<agent-name>`

## Verification

- [x] pytest passed
- [x] ruff lint passed

---
*Auto-generated by gh-issues-auto-fixer*
EOF
)"
```

## Phase 6: Address Review Comments

If `--reviews-only` was set, or as a final cleanup pass:

1. Find open PRs created by this skill:
   ```bash
   gh pr list --repo Kman182401/Patchy-Operational --search "Auto-generated by gh-issues-auto-fixer" --json number,title,url,reviewDecision,reviews
   ```

2. For each PR with requested changes or unresolved comments:
   - Fetch the review comments:
     ```bash
     gh api repos/Kman182401/Patchy-Operational/pulls/<PR_NUMBER>/comments --jq '.[].body'
     ```
   - Check out the PR branch:
     ```bash
     git checkout fix/issue-<NUMBER>-<slug>
     git pull origin fix/issue-<NUMBER>-<slug>
     ```
   - Route to the same agent that created the original fix
   - Agent receives: the review comments + the current diff + "address this feedback"
   - Re-run verification (Step 4.4)
   - Commit and push the updates
   - Return to `main`

3. Report which PRs were updated and which still need human attention.

---

## Final Report

After all phases complete, display a summary:

```
## gh-issues-auto-fixer — Run Complete

| Issue | Title                     | Agent            | Branch                        | PR     | Status |
|-------|---------------------------|------------------|-------------------------------|--------|--------|
| #3    | Schedule runner crash     | schedule-agent   | fix/issue-3-schedule-crash    | #10    | PR open |
| #7    | Add rate limit to /start  | security-agent   | fix/issue-7-rate-limit-start  | #11    | PR open |
| #12   | Fix typo in help text     | ui-agent         | —                             | —      | Skipped (PR exists) |
| #15   | DB migration failure      | database-agent   | fix/issue-15-db-migration     | —      | Tests failed |

Processed: 4 | PRs opened: 2 | Skipped: 1 | Failed: 1
```

## Safety Rules

- NEVER edit `main` directly — all work happens on `fix/issue-*` branches
- NEVER force-push
- NEVER auto-merge PRs — they are always left open for human review
- NEVER read `.env` or secrets files
- Always run the secrets safety check before committing (Step 4.5)
- Always return to `main` after processing each issue
- If anything unexpected happens, stop and report rather than continuing
