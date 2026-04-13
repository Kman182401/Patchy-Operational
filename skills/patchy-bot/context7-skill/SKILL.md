---
name: Context7
description: Up-to-date library documentation and code examples from Context7 via the context7 MCP plugin. USE WHEN looking up API docs, function signatures, configuration options, version-specific behavior, framework guides, or skill libraries (anthropics/skills, julianobarbosa/claude-code-skills, etc.). Prevents hallucinated APIs. Prefer this over WebSearch for any library reference lookup. The user holds a Context7 Pro subscription, so call freely.
---

# Context7

Query up-to-date, version-specific documentation and code examples directly from source libraries via Context7's documentation aggregation platform. In this project, Context7 is reached **only through the context7 MCP plugin** — never through the `bun` CLI bundled by the upstream skill.

## Why Context7

| Benefit | Description |
|---------|-------------|
| **Current APIs** | No hallucinated or outdated patterns — documentation comes from actual sources |
| **Version-Specific** | Gets docs for exact library versions you're using |
| **Code Examples** | Real, working code extracted from actual documentation |
| **Broad Coverage** | 1000+ libraries plus Claude Code skill libraries |
| **Pro tier active** | The user has Context7 Pro — there is no rate-limit reason to ration calls |

## How to call it (this project)

There are two MCP tools exposed by the `plugin:context7:context7` server:

| Tool | Purpose |
|------|---------|
| `mcp__plugin_context7_context7__resolve-library-id` | Find the Context7 library ID for a given package/product name |
| `mcp__plugin_context7_context7__query-docs` | Query documentation for a known library ID |

### Step 1 — Resolve the library ID (skip if known)

Call `resolve-library-id` with:
- `libraryName`: the official package name (e.g., `python-telegram-bot`, `qbittorrent-api`, `plexapi`, `Next.js`, `Three.js`)
- `query`: a short description of what you're trying to do — used for ranking

Returns a list of candidates with: Library ID (e.g. `/python-telegram-bot/python-telegram-bot`), source reputation (High/Medium/Low/Unknown), benchmark score (0–100), code-snippet count, and available versions.

Pick the result with the best name match, then highest reputation + benchmark score + snippet count.

### Step 2 — Query docs

Call `query-docs` with:
- `libraryId`: from Step 1, in the format `/org/project` or `/org/project/version`
- `query`: a specific question with relevant detail

**Good queries:** `"How to set up async polling with python-telegram-bot 21.x"`, `"qBittorrent Web API torrents/info filter parameters"`, `"plexapi PlexServer.library.search filters"`.

**Bad queries:** `"telegram"`, `"qbt"`, `"plex"`.

### Shortcut — when the user provides an ID directly

If the user types `/org/project` or `/org/project/version` in their message, skip `resolve-library-id` and call `query-docs` immediately.

## Hard rules in this project

- **Max 3 MCP calls per question.** This is a per-question budget the tool itself enforces; Pro tier removes the account cap, not the per-call best-practice limit. If you can't find the answer in 3 calls, fall back to the best information you have (project memory, code, prior knowledge).
- **Never run `bun src/cli/...`.** The upstream skill ships a TypeScript CLI in `Tools/`; we deliberately do not install it because the MCP plugin is the sanctioned path.
- **Combine with project patterns first.** Before making a context7 call, check `.claude/memory/patterns.md` and the auto-memory store — project conventions override generic library advice on conflict.
- **Don't include secrets** (API keys, passwords, internal URLs, credentials) in any `query` field.

## Mandatory follow-up: scan for related skills

**Every time you query Context7 for a library, framework, tool, or topic, you MUST also check whether Context7 indexes any Claude Code skills related to that same library/topic.** This is non-negotiable in this project.

Procedure after every successful `query-docs` call:

1. Make one additional `resolve-library-id` call with `libraryName` set to the same library name **plus** the word `skills` (e.g. `"python-telegram-bot skills"`, `"plexapi skills"`, `"qbittorrent-api skills"`). Look for any indexed Claude Code skill libraries in the result.
2. Also search the four canonical skill libraries directly for that topic by querying:
   - `/anthropics/skills` — `query-docs` with the topic name
   - `/julianobarbosa/claude-code-skills` — same
   - `/rshankras/claude-code-apple-skills` — same (only if the topic is Apple-related)
   - `/schwepps/skills` — same
3. If you find a relevant skill that is **not already installed** in `/home/karson/Patchy_Bot/.claude/skills/`, surface it to the user with:
   - The skill's name and source repo
   - One-line description of what it does
   - Why it's relevant to the current task
   - Whether it would be valuable as a one-time reference for *this* task only, or worth installing permanently for future work
4. If the skill is genuinely useful for the current task only, you may read its SKILL.md inline via `gh api` and apply its guidance without installing.
5. If the skill is worth installing permanently, propose installation and wait for user approval before copying it into `.claude/skills/`. Do NOT install without approval.
6. Track this scan in your end-of-task summary so the user can see what was considered.

This rule exists so that every Context7 lookup doubles as a passive skill-discovery pass, continuously expanding Patchy Bot's relevant skill set without manual searching.

## When to call Context7 in Patchy Bot work

Trigger automatically when:

- Writing or modifying code that touches `python-telegram-bot`, `qbittorrent-api`, `plexapi`, `httpx`, `aiohttp`, `aiosqlite`, `pyrogram`, `telethon`, or any new dependency you're not 100% sure about.
- Hitting an error from one of those libraries — query the exact error string + library name first.
- Investigating breaking changes between library versions during dependency upgrades.
- Looking up Claude Code skill libraries for new skills to install (the libraries are indexed too — query `/anthropics/skills`, `/julianobarbosa/claude-code-skills`, `/rshankras/claude-code-apple-skills`, `/schwepps/skills`).

Do NOT call Context7 for:
- Trivial Python stdlib lookups you already know.
- Reading or editing files in this repo (use Read/Grep).
- Generic programming concepts unrelated to a specific library.
- Refactoring or formatting tasks.

## Common library IDs (shortcut cache)

| Library | Context7 ID |
|---------|-------------|
| python-telegram-bot | `/python-telegram-bot/python-telegram-bot` |
| qbittorrent-api | `/rmartin16/qbittorrent-api` |
| plexapi | `/pkkid/python-plexapi` |
| anthropics/skills | `/anthropics/skills` |
| julianobarbosa/claude-code-skills | `/julianobarbosa/claude-code-skills` |
| Claude Code itself | `/anthropics/claude-code` |
| Python stdlib | `/python/cpython` |
| httpx | `/encode/httpx` |
| SQLite | `/sqlite/sqlite` |

These are starting guesses — always verify via `resolve-library-id` if the call fails.

## Workflow routing

| Workflow | Trigger | File |
|----------|---------|------|
| **ResolveLibrary** | "find library ID", "resolve library" | `Workflows/ResolveLibrary.md` |
| **QueryDocs** | "lookup docs", "get documentation", "code examples" | `Workflows/QueryDocs.md` |
| **FullLookup** | "help me with [library]", "how do I use [feature]" | `Workflows/FullLookup.md` |

(The Workflows files reference upstream `bun` commands — translate them mentally to the MCP tool calls described above.)

## Tips

- **Be specific** in queries — include version hints when relevant (`"python-telegram-bot 21.x"`).
- **One library per query.** If you need docs for two libraries, make two separate `query-docs` calls.
- **Cache results in your head for the session** — don't re-query the same docs twice.
- **Verify before recommending.** A Context7 result is current as of the index — but a library may have shipped a newer version since. Check the version field returned by `resolve-library-id`.
