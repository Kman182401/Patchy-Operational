# Patchy Bot — Project Instructions

## Guardrails

- Do not run raw git write commands (`git commit`, `git push`, branch/reset) in `/home/karson/Patchy_Bot`. The `push` shell alias is the only sanctioned commit+push path (see Push Rule).
- Prefer code over docs when they disagree.
- Keep changes targeted. Do not rewrite unrelated flows or move files without a clear reason.
- Do not break [`telegram-qbt/qbt_telegram_bot.py`](/home/karson/Patchy_Bot/telegram-qbt/qbt_telegram_bot.py); it is a back-compat shim unless the user explicitly wants it changed.
- Use the `patchy-bot` skill for the architecture map, module ownership, callback namespaces, DB ownership, and restart/test commands.

## Core Invariants

- Most runtime code lives in [`telegram-qbt/patchy_bot/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot).
- State that must survive restarts belongs in SQLite via [`telegram-qbt/patchy_bot/store.py`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/store.py). Transient chat/UI flow state can stay in memory.
- Search, add-flow, and Telegram UI behavior should stay aligned across movie and TV paths unless the user explicitly wants divergence.
- Dynamic values inserted into Telegram HTML messages must be escaped with `_h()`.
- If a download/progress change touches both the immediate path and the deferred-hash pending path, update both paths.

## Restart Rule

- After changes under [`telegram-qbt/patchy_bot/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot) or related runtime config/service files, restart [`telegram-qbt/telegram-qbt-bot.service`](/home/karson/Patchy_Bot/telegram-qbt/telegram-qbt-bot.service) so the running bot picks up the change.

## Push Rule

- After completing any task that modifies files under `/home/karson/Patchy_Bot/` (runtime code, config, skills, vault, docs, memory), run the `push` shell alias in Bash. It auto-commits and pushes to `origin/main` of the Patchy-Operational repo.
- The `push` alias is the ONLY sanctioned git path — never run raw `git commit`/`git push`/branch commands manually.
- End-of-task order: post-changes-audit → code-simplifier agent on touched code → restart the service (if runtime code changed) → run `push` → `/revise-claude-md`. All five must happen before reporting "done".

## CLAUDE.md / Memory Refresh Rule

- At the end of any productive session (one that made code, config, skill, memory, or vault changes), invoke the `/revise-claude-md` slash command provided by the `claude-md-management@claude-plugins-official` plugin. This command reflects on the session, drafts concise additions to the relevant CLAUDE.md / `.claude.local.md` files, and asks for approval before applying them.
- The purpose is to keep CLAUDE.md, `.claude/memory/` entries, and the Obsidian vault's `Preferences.md` continuously synchronized with what was actually learned — so future sessions always start with an accurate picture of completed work, in-flight work, and open items.
- If `/revise-claude-md` proposes no changes, that is a valid outcome — do not fabricate insights to justify an edit. Simply report "no new learnings captured" and move on.
- This step runs AFTER `push` so any CLAUDE.md updates from this step land in the NEXT commit, not the current one (preventing the command from racing with the push alias).

## File Ownership

- Runtime code: [`telegram-qbt/patchy_bot/`](/home/karson/Patchy_Bot/telegram-qbt/patchy_bot)
- Repo-local Claude behavior: [`.claude/`](/home/karson/Patchy_Bot/.claude), [`skills/`](/home/karson/Patchy_Bot/skills), [`.claude-plugin/`](/home/karson/Patchy_Bot/.claude-plugin)

## High-Value Conventions

- Run `pytest -q` in [`telegram-qbt/`](/home/karson/Patchy_Bot/telegram-qbt) for touched Python areas when tests exist.
- Prefer the curated project-local skills; do not restore a mirrored global skill library to this repo.
- Keep instructions that are workflow-specific, command-specific, or operationally detailed out of this file.
- Preserve path safety and media-type validation when moving or deleting files.

## Memory Systems

Patchy_Bot has one live memory store and one frozen archive.

1. **Auto-memory (canonical, live)** — `~/.claude/projects/-home-karson-Patchy-Bot/memory/`
   Managed by the Claude Code auto-memory system. Trigger-based entries typed as `user`, `feedback`, `project`, `reference`. `MEMORY.md` is the index — one line per entry, ~150 chars, no narrative. **This is the single source of truth for preferences, rules, and cross-session learnings.** All new learnings go here.

2. **Legacy archive (frozen, read-only)** — `~/Patchy_Bot/.claude/memory/`
   Contains `decisions.md`, `bugs.md`, `patterns.md` (plus an archive `MEMORY.md`). Preserves detailed forensics from the 2026-04-03 → 2026-04-08 sprint — bug-by-bug root causes, full decision rationale, worked pattern examples. **Frozen as of 2026-04-08; do not append to it.** Consult only when a 2026-04-07 bug symptom recurs and the one-line auto-memory summary isn't enough, or when you need the original rationale behind a decision. `sessions.md` was removed on 2026-04-13 (empty auto-hook stubs only).

**End-of-session sync:** `/revise-claude-md` updates CLAUDE.md files. The auto-memory system updates itself as you save entries during the session. The legacy archive receives no updates ever.

## Obsidian Project Vault

An Obsidian vault lives at `Patchy Ops/` (vault name: "Patchy Ops", synced via Obsidian Sync) containing project architecture documentation, task tracking, user preferences, and a changelog.

**Layout (numbered-folder structure):**
- `00-Home/Dashboard.md` — system overview, status counts, priority queue, current focus
- `01-System/` — architecture docs: `Modules.md`, `API Clients.md`, `Callback Routes.md`, `SQLite Tables.md`, `State & Flows.md`, `System Overview.md`
- `02-Work/Work Board.md` + `02-Work/Todos/` + `02-Work/Upgrades/` — active work items
- `03-Reference/Preferences.md` — user likes/dislikes/conventions (READ before every task, UPDATE when you learn new preferences)
- `04-Ideas/` — future possibilities, indexed by `Ideas Index.md` (read-only unless asked)
- `05-Changelog/` — completed work log, indexed by `Changelog Index.md`; month files like `2026-04-completed.md`
- `_templates/tpl-task.md`, `tpl-idea.md`, `tpl-changelog.md` — frontmatter templates for new notes

**Rules:**
- Before starting any task, check `03-Reference/Preferences.md` for relevant conventions
- After completing a task that was tracked in the vault, update its status to `done` and append a Changelog entry to the current month file
- After completing a task that changes architecture (new modules, tables, callbacks), update the relevant `01-System/` doc
- When you learn something the user prefers or dislikes, add it to `03-Reference/Preferences.md` under "Learned Preferences"
- After any vault modifications, refresh `00-Home/Dashboard.md` counts and priority queue
- Use the `vault-manager` subagent for complex vault operations
- New task notes must use the template frontmatter format from `_templates/tpl-task.md`; new ideas use `tpl-idea.md`; new changelog entries use `tpl-changelog.md`
