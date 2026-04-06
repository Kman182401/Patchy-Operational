---
name: project-builder
description: This skill should be used when the user asks to "create a Claude.ai project", "set up a project", "build project instructions", "generate project config", "make a Claude project", "write project system prompt", or needs to create structured Claude.ai Projects with custom instructions, knowledge files, and optimized workflows.
---

# Project Builder

Generate complete Claude.ai Project configurations — custom instructions, knowledge file selections, and starter prompts — tailored to a specific domain, codebase, or workflow.

## When to Use

- Creating a new Claude.ai Project from scratch
- Converting an existing codebase or workflow into a Claude.ai Project
- Optimizing an underperforming project's instructions or knowledge files
- Generating domain-specific project templates (coding, security, research, writing, devops, data/ML)

## Workflow Overview

This skill follows a phased approach: gather context, draft instructions, select knowledge files, generate starter prompts, and output the final configuration.

---

## Phase 1: Define the Project

Establish the project's purpose and constraints before writing anything.

1. **Identify the domain**: coding, security, research, writing, devops, data/ML, or hybrid
2. **Clarify the audience**: Who will use this project? What's their expertise level?
3. **Define success criteria**: What does a good output from this project look like?
4. **Scope boundaries**: What should the project handle vs. what's out of scope?
5. **Gather key context**: Tech stack, tools, conventions, team preferences

Ask the user only the minimum questions needed to resolve ambiguity. If context is available from files or environment, use that instead of asking.

---

## Phase 1.5: Auto-Gather Context (Claude Code Only)

**This phase runs only inside Claude Code. Skip if operating in Claude.ai directly.**

When invoked from Claude Code with access to a filesystem:

1. Run the context gathering script from the current working directory:
   ```bash
   bash /home/karson/.claude/skills/project-builder/scripts/gather-context.sh
   ```
2. Parse the structured markdown output into these categories:
   - **Project Identity** — name, description, git remote, recent commits
   - **Tech Stack** — languages, frameworks, databases, infrastructure, CI/CD
   - **Configuration** — CLAUDE.md contents, agent listings, settings, env templates
   - **Codebase Structure** — directory tree, file counts, test locations, entry points
   - **Security Posture** — linter configs, pre-commit hooks, security tooling
3. Read `references/project-patterns.md` for the instruction template and domain-specific patterns
4. Pre-populate the project's context section with gathered data
5. Skip asking the user questions that the scan already answered (tech stack, project structure, tools in use, conventions documented in CLAUDE.md)
6. Present a summary of what was auto-detected and ask the user to confirm or correct before proceeding

If the script is unavailable or fails, fall back to Phase 1's manual questioning.

---

## Phase 2: Draft Project Instructions

Build the custom instructions using the XML-structured template from `references/project-patterns.md`.

### Instruction Structure

Organize instructions into these sections:

1. **Role** — Define who Claude is in this project (2-3 sentences max)
2. **Context** — Project background, tech stack, conventions (from Phase 1/1.5)
3. **Rules** — Behavioral constraints specific to this project
4. **Workflow** — Step-by-step procedures for common tasks
5. **Output Format** — How responses should be structured

### Quality Guidelines

- Keep total instructions under 1500 words — offload detail to knowledge files
- Write in imperative form ("Use snake_case" not "You should use snake_case")
- Be specific ("Use pytest with fixtures" not "Write tests")
- Avoid duplicating Claude's default behaviors or profile-level preferences
- Include uncertainty handling ("If the schema is ambiguous, ask before generating migrations")
- Reference knowledge files by name when relevant ("See `api-schema.md` for endpoint specs")

---

## Phase 3: Select Knowledge Files

Determine what to upload as project knowledge vs. what to leave out.

### Include

- API schemas, database schemas, type definitions
- Style guides, coding conventions, team agreements
- Architecture decision records (ADRs)
- Example inputs/outputs for common tasks
- Domain glossaries or terminology references
- Workflow documentation not captured in instructions

### Exclude

- Large codebases (use instructions to describe structure instead)
- Frequently changing files (they go stale in knowledge)
- Secrets, credentials, .env files
- Auto-generated files (lock files, build output)
- Content already well-known to Claude (standard library docs, common framework basics)

### RAG Optimization

Structure knowledge files for effective retrieval:
- Use clear, descriptive headings (retrieval keys off section titles)
- Keep sections self-contained — don't rely on context from other sections
- One topic per file when possible (prefer 3 focused files over 1 merged file)
- Front-load the most important information in each section
- Include concrete examples near the concepts they illustrate

---

## Phase 4: Generate Starter Prompts

Create 3-5 starter prompts that demonstrate the project's most common use cases.

Each starter prompt should:
- Be specific enough to produce a useful response immediately
- Exercise different capabilities of the project
- Serve as onboarding examples for new users

---

## Phase 5: Output the Final Configuration

Present the complete project configuration:

1. **Project Name** and one-line description
2. **Custom Instructions** (formatted, ready to paste)
3. **Knowledge Files** — list with brief rationale for each
4. **Starter Prompts** — numbered list with descriptions
5. **Setup Notes** — any manual steps needed (API keys, integrations, etc.)

Format the custom instructions as a single copyable block. If the instructions exceed 1500 words, flag it and suggest what to move to knowledge files.

---

## Additional Resources

### Reference Files

- **`references/project-patterns.md`** — XML instruction template, domain-specific patterns, common mistakes checklist, token budget guidance, knowledge file criteria, and RAG optimization notes

### Scripts

- **`scripts/gather-context.sh`** — Auto-collects project context from the current working directory (Claude Code only). Detects tech stack, reads config files, maps codebase structure. Never reads .env or secrets.
