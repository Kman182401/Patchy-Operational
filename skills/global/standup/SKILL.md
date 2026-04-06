---
name: standup
description: >
  This skill should be used when the user asks to "write my standup", "generate standup update", "standup summary", "what did I do yesterday", "daily update", "scrum update", "status update", "summarize recent work", or wants to summarize recent commits, PRs, or work into a concise team update. Also trigger when the user pastes git logs or commit messages and wants them formatted as a standup.
---

# Standup Update

Generate a clear, concise standup update from available context.

## Input Sources

Work with whatever the user provides:

- **Direct description** — "I worked on the auth refactor and fixed a caching bug"
- **Git log / commits** — Parse commit messages into meaningful summaries
- **PR descriptions** — Extract the what and why from pull request context
- **Task tracker updates** — Summarize ticket status changes

If no structured input is provided, ask: "What did you work on? Any blockers?"

## Output Format

```
**Yesterday / Since last update:**
- [Accomplishment — what was done, not what was attempted]
- [Accomplishment — group related small items]

**Today / Next:**
- [Plan — specific enough that the team knows what you're touching]
- [Plan — include PR reviews, meetings if relevant]

**Blockers:**
- [Specific blocker with what's needed to unblock]
```

Or "No blockers" if none exist.

## Writing Guidelines

**Be specific, not vague.** "Refactored auth middleware to support JWT rotation" beats "Worked on auth stuff."

**Lead with outcomes.** "Fixed caching bug that caused stale user profiles (PR #342)" not "Investigated caching issue, found the bug, wrote a fix, tested it, opened a PR."

**Group small tasks.** Don't list every commit. "Code review and small fixes across 3 PRs" is fine for minor work.

**Blockers need context.** "Blocked on API access" is less useful than "Need production API key from infra team to test payment integration — pinged @Sarah."

**Keep it scannable.** Each bullet should be one line. If two sentences are needed, that's two bullets.

## Adapting to Team Style

- **Async teams:** More detail — the update may be the only visibility into the work.
- **Daily syncs:** Keep it short — 30 seconds of speaking time per section.
- **Sprint-based:** Connect items to sprint goals or ticket numbers.

Adapt length and formality to match the user's team culture. When in doubt, err on the side of concise.
