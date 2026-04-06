---
name: incident-response
description: >
  This skill should be used when the user asks about "incident response", "outage", "postmortem", "post-mortem", "root cause analysis", "RCA", "production is down", "service degraded", "incident report", "incident communication", "blameless retrospective", or needs to write incident communications, triage severity, track a timeline, or generate a postmortem. Complements the incident-responder agent which handles active triage.
---

# Incident Response

Structured workflow for managing production incidents from detection through postmortem.

## Phase 1: Triage

Establish the basics immediately:

| Field | Determine |
|-------|-----------|
| **Severity** | P1 (service down, data loss), P2 (degraded, workaround exists), P3 (minor, low impact) |
| **Impact** | Who is affected? How many users? Which features? |
| **Start time** | When did the issue begin? (Check metrics, not when it was noticed) |
| **Status** | Investigating / Identified / Monitoring / Resolved |

If severity is unclear, default to one level higher. It's easier to downgrade than to explain why you under-triaged.

## Phase 2: Communication

Draft incident communications for each phase:

### Initial Notification
```
**[P1/P2/P3] [Service] — [Brief description]**

**Impact:** [Who/what is affected]
**Status:** Investigating
**Started:** [Time]
**Next update:** [Time — commit to a specific time]

We are actively investigating. [One sentence on what we know so far.]
```

### Status Update
```
**Update — [Service] incident**

**Status:** [Investigating / Identified / Monitoring / Resolved]
**What we know:** [Current understanding of the cause]
**What we're doing:** [Active mitigation steps]
**ETA:** [If known, or "Assessing"]
**Next update:** [Time]
```

### Resolution
```
**Resolved — [Service] incident**

**Duration:** [Start time] to [End time] ([total duration])
**Impact:** [Summary of what was affected]
**Root cause:** [One-sentence summary]
**Resolution:** [What fixed it]

A full postmortem will follow within [timeframe].
```

## Phase 3: Timeline

Build a chronological timeline of events:

```
[HH:MM UTC] — [Event or action taken]
[HH:MM UTC] — [Event or action taken]
```

Include: detection, first response, diagnosis steps, mitigation attempts (including failed ones), resolution, and verification.

## Phase 4: Postmortem

Generate a blameless postmortem:

```markdown
# Postmortem: [Incident Title]

**Date:** [Date]
**Duration:** [Total time]
**Severity:** [P1/P2/P3]
**Authors:** [Who wrote this]

## Summary
[2-3 sentences: what happened, impact, resolution]

## Timeline
[Chronological events from Phase 3]

## Root Cause
[Technical explanation of what went wrong and why]

## Contributing Factors
- [What made the situation worse or delayed resolution]
- [Process gaps, missing monitoring, unclear ownership]

## What Went Well
- [Quick detection, effective communication, good teamwork]

## Action Items
| Action | Owner | Priority | Due Date |
|--------|-------|----------|----------|
| [Specific fix] | [Name] | [P1/P2] | [Date] |

## Lessons Learned
[What should the team internalize going forward]
```

## Principles

- **Blameless.** Focus on systems and processes, not individuals.
- **Specific.** "Error rate increased to 45%" not "errors went up significantly."
- **Actionable.** Every action item has an owner and due date. "Improve monitoring" is not an action item. "Add latency P99 alert for payment service (owner: Jane, due: March 15)" is.
