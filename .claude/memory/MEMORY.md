# Patchy Bot — Legacy Memory Archive

> **Status: FROZEN ARCHIVE (as of 2026-04-08). Do not write new entries here.**
>
> This directory is read-only forensic reference. It preserves the detailed
> bug forensics, decision rationale, and pattern examples captured during
> the 2026-04-03 → 2026-04-08 development sprint.
>
> **The canonical live memory store is the auto-memory system at**
> `~/.claude/projects/-home-karson-Patchy-Bot/memory/` **— all new learnings,
> preferences, and rules go there.** See that directory's `MEMORY.md` index.
>
> The session-narrative file (`sessions.md`) was removed on 2026-04-13
> because its 11 entries were empty auto-hook stubs with no real content.

---

## What's in this archive

- [decisions.md](decisions.md) — 7 architectural decisions (2026-04-04 → 2026-04-07) with full context, rationale, files affected, and impact. Covers: CAM/TS penalty model, malware scanning gate, season nav redesign, no-git-in-Patchy_Bot rule, qBT interface-binding removal, Plex autoEmptyTrash fix, monolith→package restructure.
- [bugs.md](bugs.md) — 14 bug forensics entries (all 2026-04-07) with Symptom / Root cause / Fix / Files changed / Verification steps. Covers the 17-bug batch fix that the auto-memory store summarizes as a single line.
- [patterns.md](patterns.md) — 18 patterns/conventions/gotchas/anti-patterns (2026-04-03 → 2026-04-07) with worked examples and impact-if-ignored notes. The auto-memory store has the rules; this file has the *why* and *how*.

## When to consult this archive

- A 2026-04-07 bug symptom recurs and you want the full forensic trail, not just the one-line summary.
- You need the original rationale behind a decision to judge whether it still applies in a new context.
- You want a worked example of a pattern the auto-memory entry only states abstractly.

For anything else, read the live auto-memory index first.
