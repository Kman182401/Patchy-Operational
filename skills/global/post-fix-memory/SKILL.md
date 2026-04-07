---
name: post-fix-memory
description: >
  Run immediately after a bug or issue has been confirmed fixed. Extracts all
  information about the issue — symptoms, root cause, the fix, files changed,
  and patterns to avoid — then writes structured entries to the project's
  persistent memory (MEMORY.md and/or topic files) and optionally promotes
  generalizable rules to CLAUDE.md. Ensures the same mistake is never made
  again in future sessions. Trigger on: "save this fix", "remember this bug",
  "log this issue", "post-fix memory", "commit this to memory", "don't let
  this happen again", "/post-fix-memory", "remember what went wrong", or any
  variation after a successful fix where the user wants it retained. NOT for
  planning fixes or debugging active issues — use systematic-debugging for that.
context: fork
agent: general-purpose
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Post-Fix Memory

You have just fixed a bug or resolved an issue. Your job now is to extract every
relevant detail and write it to the right memory locations — so this mistake is
never repeated in a future session.

**Core principle:** A fix that isn't remembered is a fix that will be needed again.

---

## Phase 1: Extract the Fix Details

Before writing anything, gather the complete picture. Pull from the current
conversation context first. If anything is unclear or missing, ask the user —
but keep it to one focused question at a time.

Collect these fields:

**What broke (symptoms)**
- What did the user observe? Error message, unexpected behavior, test failure?
- Was it intermittent or consistent?
- Was there a stack trace or log output?

**Root cause**
- What was the actual underlying problem, not just the symptom?
- What false leads or wrong diagnoses were tried first (if any)?
- What made this hard to find?

**The fix**
- What change was made? Be specific: file path, function/class, what changed.
- Why does the fix work? (What invariant was restored?)

**Scope**
- Which files were modified?
- Were any tests added or updated?

**Pattern to avoid**
- What is the generalizable anti-pattern this represents?
- State it as a rule: "Never do X because Y" or "Always do Z when W."

**Detection**
- How would someone discover this issue again in the future?
- Is there a grep pattern, test, or log signal that would surface it?

---

## Phase 2: Classify and Route

Decide where each piece of information belongs.

### MEMORY.md (always write here)
The full structured bug entry goes here. This is Claude's working journal — it
gets auto-loaded at every session start. Write the entry using the template in
`references/entry-template.md`.

**Locate the file:**
```bash
# Find the project's memory directory
ls ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null | head -5

# If running inside a project, the hash is based on the working directory.
# Try:
python3 -c "import hashlib, os; print(hashlib.md5(os.getcwd().encode()).hexdigest())"
# Then check: ~/.claude/projects/<hash>/memory/MEMORY.md
```

If MEMORY.md does not exist yet, create it at the correct path. Start it with
a `# Project Memory` heading and a brief description line.

**Size check:** If MEMORY.md is approaching 200 lines, write to a topic file
instead (see below) and add a one-line summary + reference to MEMORY.md.

### Topic file (use when a category file exists or is warranted)
If `debugging.md`, `patterns.md`, `bugs.md`, or a similar topic file exists
alongside MEMORY.md, append the entry there instead of MEMORY.md. Add a
one-liner + link in MEMORY.md:

```
- [Bug: <title>] → see debugging.md (added <date>)
```

If no topic file exists and this is the 3rd+ bug entry, create `bugs.md` and
migrate prior bug entries there.

### CLAUDE.md (only if universally applicable)
Promote the pattern to CLAUDE.md **only when all three are true:**
1. The rule applies to all future work in this project, not just this bug
2. The rule is short, specific, and verifiable (not vague advice)
3. CLAUDE.md is under 180 lines after adding it

If CLAUDE.md qualifies, add the rule to the most relevant existing section.
Do not create a new top-level section for a single rule. If no section fits,
add it under a `## Known Pitfalls` section (create it if missing).

**Never add to CLAUDE.md:**
- Debugging notes or context-specific observations
- Rules that only apply to a single edge case
- Anything over two sentences
- Redundant rules that are already implied

---

## Phase 3: Write the Entries

### MEMORY.md entry format

Use the template from `references/entry-template.md`. Append to the end of the
file (or to the topic file). Do not overwrite existing entries.

After appending, confirm the file was written and show the final entry to the
user.

### CLAUDE.md update (if applicable)

Show the user the proposed rule before writing it. Get explicit confirmation:
> "I'd like to add this rule to CLAUDE.md: [rule]. Shall I add it?"

Only write after confirmation. Show the before/after diff of the relevant
section.

---

## Phase 4: Verify and Report

After writing all entries, report back with:

```
## Memory Written

**Locations updated:**
- ~/.claude/projects/<hash>/memory/MEMORY.md ✅
- ~/.claude/projects/<hash>/memory/bugs.md ✅  (if used)
- CLAUDE.md ✅  (if applicable)

**Entry title:** <title>

**Rule extracted:** <one-line rule, if any>

**How to find it:** grep "<keyword>" ~/.claude/projects/<hash>/memory/

This issue is now part of persistent project memory and will be loaded
at the start of every future session.
```

---

## Edge Cases

**Can't find the memory directory:**
Run `claude --version` and confirm Claude Code is active. The project hash is
derived from the working directory. Try `find ~/.claude/projects -name MEMORY.md`
to locate any existing files.

**No context in conversation (user just typed the command):**
Ask the user to describe the issue that was just fixed. One question:
> "What was the issue that was just resolved? Describe the symptom and the fix
> and I'll lock it into memory."

**Issue was trivial (typo, copy-paste error):**
Still write the entry — trivial bugs repeat too. Keep it short. Skip the
CLAUDE.md promotion step.

**Multiple issues fixed in one session:**
Write one entry per distinct root cause. Do not combine unrelated bugs into
a single entry.
