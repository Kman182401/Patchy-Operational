---
tags:
  - home
aliases:
  - Vault Guide
created: 2026-04-11
updated: 2026-04-11
---

# Vault Guide

## Overview

This vault is the human-readable home for everything about Patchy Bot — how the system is built, what work is open, what's been finished, and what conventions to follow. It's designed so that you can read it without being a programmer, while still giving Claude Code (the AI assistant that helps maintain the bot) the technical detail it needs.

### Folder layout

- **`00-Home/`** — landing pages. The [[Dashboard]] is your starting point. [[SETUP]] tells you how to get the vault working in Obsidian. This guide lives here too.
- **`01-System/`** — how the bot is built. [[System Overview]] is the map; the other notes here ([[Modules]], [[SQLite Tables]], [[Callback Routes]], [[API Clients]], [[State & Flows]]) drill into specific parts.
- **`02-Work/`** — the to-do list. [[Work Board]] shows everything open. Individual task notes live in `02-Work/Todos/` (bugs and must-do work) and `02-Work/Upgrades/` (nice-to-have improvements).
- **`03-Reference/`** — things to read before doing work. [[Preferences]] (likes and dislikes), [[Coding Conventions]], and the [[Ops Runbook]] (restart commands, log locations, troubleshooting).
- **`04-Ideas/`** — future possibilities that haven't been started. [[Ideas Index]] lists them all. Once an idea becomes a real plan, it moves into `02-Work/`.
- **`05-Changelog/`** — what's been finished, newest first. [[Changelog Index]] is the rollup; monthly notes hold the detail.
- **`_templates/`** — pre-made note shapes used by the Templater plugin (`tpl-task.md`, `tpl-idea.md`, `tpl-changelog.md`). You don't open these directly — Templater does.
- **`_config/`** — vault configuration files (do not edit by hand).

### How notes are structured

Every content note has two parts:

1. A plain-English **`## Overview`** section at the top. This is for the human reader — it explains what the note is about in normal language and avoids jargon. Acronyms get defined the first time they appear.
2. A collapsed **`> [!code]- Claude Code Reference`** callout below it. This holds the technical details — file paths, function names, table columns, callback prefixes — for Claude Code to use when actually doing work. Click the arrow to expand it; leave it collapsed if you just want the human-readable summary.

The two exceptions are this guide and [[SETUP]] — they're for you only and don't need a code callout.

### Creating a new note from a template

The vault uses the Templater plugin (installed during [[SETUP]]). To create a new note from a template:

1. Open the command palette with **Ctrl+P** (or **Cmd+P** on Mac).
2. Type "Templater: Create new note from template" and pick it.
3. Choose one of the templates:
   - **`tpl-task.md`** — for a new task in `02-Work/Todos/` or `02-Work/Upgrades/`
   - **`tpl-idea.md`** — for a new idea in `04-Ideas/`
   - **`tpl-changelog.md`** — for a new monthly changelog file in `05-Changelog/`
4. Templater will fill in the date and frontmatter for you.

You can also click the Templater ribbon icon in the left sidebar if you prefer mouse to keyboard.

### Tags (the labels that group notes together)

Notes are organized by tags rather than by folder alone, so a Dataview query can pull "all open todos" or "all changelog entries" no matter where the file lives. The tag scheme is:

- **`home`** — landing pages in `00-Home/`
- **`system/*`** — architecture notes (e.g. `system/modules`, `system/tables`, `system/callbacks`, `system/clients`, `system/state`)
- **`work/todo`** — bugs and must-do task notes
- **`work/upgrade`** — optional improvement task notes
- **`reference`** — preferences, conventions, runbook, and the index pages
- **`idea`** — future possibilities in `04-Ideas/`
- **`changelog`** — completed-work entries in `05-Changelog/`

Each task note also has frontmatter fields `status` (`open` / `in-progress` / `done`) and `priority` (`high` / `medium` / `low`) so the dashboards can sort and filter them.

### Maps of Content (MOCs)

A "Map of Content" is an index page that pulls together everything of a certain type. The vault has four:

- [[System Overview]] — every architecture note in one place
- [[Work Board]] — every open todo and upgrade
- [[Ideas Index]] — every idea
- [[Changelog Index]] — every monthly changelog

Use these as jumping-off points whenever you don't know exactly which note you want — start at the MOC and click through.
