---
name: tech-debt
description: >
  This skill should be used when the user asks about "tech debt", "technical debt", "technical debt audit", "what should we refactor", "code health", "refactoring priorities", "maintenance backlog", "code quality audit", "what to clean up", "code rot", "long-term maintainability", or wants to identify, categorize, and prioritize what needs fixing in a codebase.
---

# Tech Debt Management

Systematically identify, categorize, and prioritize technical debt.

## Categories

| Type | Examples | Risk |
|------|----------|------|
| **Code debt** | Duplicated logic, poor abstractions, magic numbers | Bugs, slow development |
| **Architecture debt** | Monolith that should be split, wrong data store | Scaling limits |
| **Test debt** | Low coverage, flaky tests, missing integration tests | Regressions ship |
| **Dependency debt** | Outdated libraries, unmaintained dependencies | Security vulns |
| **Documentation debt** | Missing runbooks, outdated READMEs, tribal knowledge | Onboarding pain |
| **Infrastructure debt** | Manual deploys, no monitoring, no IaC | Incidents, slow recovery |

## Prioritization Framework

Score each item on:

- **Impact**: How much does it slow the team down? (1-5)
- **Risk**: What happens if we don't fix it? (1-5)
- **Effort**: How hard is the fix? (1-5, inverted — lower effort = higher priority)

**Priority = (Impact + Risk) x (6 - Effort)**

Higher score = higher priority. This naturally surfaces high-impact, low-effort wins.

## Output

Produce a prioritized list with:

1. **Item description** — What the debt is, concretely
2. **Category** — Which type from the table above
3. **Priority score** — Calculated using the framework
4. **Estimated effort** — T-shirt size (S/M/L/XL) with rough time estimate
5. **Business justification** — Why this matters beyond "clean code" (developer velocity, incident risk, security exposure, onboarding time)
6. **Phased remediation plan** — How to tackle it alongside feature work, not as a separate "tech debt sprint"

## Guidelines

- Focus on debt that has real consequences, not cosmetic preferences.
- Connect every item to a business impact: slower shipping, more incidents, harder onboarding, security risk.
- Suggest a phased plan — all-or-nothing refactors rarely get approved. Show how to make incremental progress.
- Distinguish between debt that's actively hurting the team and debt that's stable and can wait.
