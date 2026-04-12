# Plain-English Summary Writing Guide

*Load this when writing Deliverable 1 (the inline summary) for additional guidance.*

-----

## Purpose

The plain-English summary exists so the user can fully understand what Claude Code
is about to do before it does it. It is not a technical document. It is a clear,
honest explanation written for someone who knows their project deeply but wants
to see the plan from the outside.

-----

## Writing Principles

**1. Lead with the outcome, not the process**
Start with what will be different after this plan runs. Not "we will modify the
scoring function" — but "torrent quality scoring will now penalize HEVC files
at 1080p instead of rewarding them."

**2. Before/After is the most powerful tool**
For every significant change, show exactly what it looks like now vs. after.
Use concrete examples with real values where possible.

Bad: "The codec scoring will be adjusted."
Good: "Right now, an x265/HEVC file at 1080p gets a +10 score bonus. After this
change, it gets a -5 penalty. An x265 file at 4K still gets the +10 bonus."

**3. Plain language, no jargon unless unavoidable**
If a technical term must be used, explain it in the same sentence.

Bad: "We will refactor the TTL-based eviction logic."
Good: "We will change how the system decides when to remove old entries from the
cache — currently it removes them after 60 seconds, after this change it will
remove them when the cache is full."

**4. Ripple effects matter**
Users often focus on the direct change but miss what else it affects. Explicitly
call out every downstream consequence.

Example: "This change will affect how the Telegram bot reports torrent selection —
you'll now see 'penalized: HEVC at 1080p' in the selection log where before you
saw nothing."

**5. Success criteria must be verifiable by the user**
Don't write "the bug will be fixed." Write "you'll know it worked when you
download an HEVC 1080p torrent and the bot selects the H.264 version instead."

-----

## Summary Sections

### What This Plan Achieves

1-3 sentences. What is the point of all of this? What problem goes away?

### What Will Change

Bullet list. For each item:

- **[Component/File]:** Before -> After
- Include a concrete example for any scoring, logic, or behavior change

### How This Affects the System

Paragraph or bullets. Describe observable effects:

- What will users / bots / scripts see differently?
- What will stop happening?
- What will start happening?
- Any side effects to be aware of?

### How to Know It Worked

2-5 concrete, checkable items. Each should be something the user can verify
themselves without running tests: an output they'll see, a behavior they'll
observe, a log entry they'll find.

### Things to Be Aware Of

Honest risk section. Not scary — just honest:

- "This changes the scoring for all torrents, not just new ones"
- "If the tests fail during implementation, do not proceed to the next task"
- "Back up the file before Claude Code runs if you want a safety net"

-----

## Tone

- Direct and confident
- No hedging ("it might," "should probably," "I think")
- No filler ("In order to," "It is worth noting that")
- Short paragraphs — 3-4 sentences max
- Use examples liberally
- Treat the reader as intelligent and capable
