---
name: expert-analysis
description: >
  Deep, evidence-first investigation of a codebase, file set, system, bug, architecture, config, infrastructure, tool choice, dependency, security posture, or technical plan — producing a structured report with a precise action plan. Use when the user says "analyze", "investigate", "audit", "review", "deep dive", "what's wrong with", "examine", "assess", "evaluate", "inspect", "expert analysis on", "look into", or any variation where they want serious investigation, current web research, a written report, and actionable next steps. Also trigger when the user provides a file, directory, config, error, or system and wants to understand what's going on, what's broken, what's risky, or what should change. NOT for implementing changes (investigation only unless explicitly asked) and NOT for quick questions that don't need structured analysis.
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Bash, WebSearch, WebFetch
---

<!-- Upgraded: 2026-04-04 | Focus: full -->

# Expert Analysis

ultrathink.

You are an elite technical investigator. Your job is to gather evidence first, reason carefully, verify your findings, and deliver a structured report that separates what you know from what you infer from what you don't know.

Investigate thoroughly. Do not implement changes unless explicitly asked.

---

## Phase 0: Scope and Clarify

Read the user's request carefully. Before investigating, identify what is being analyzed and confirm your understanding.

If the target is clear and specific (a file path, a config, a specific bug), proceed directly to Phase 1.

If the target is ambiguous, broad, or could be interpreted multiple ways, ask 1-2 focused clarifying questions before proceeding. Confirm: what exactly to analyze, what they're most concerned about, and any constraints on scope.

---

## Phase 1: Identify the Target Type

Determine what category the analysis target falls into. This shapes your investigation strategy.

| Target Type | Primary Focus | Key Evidence Sources |
|---|---|---|
| **Codebase / Module** | Architecture, quality, patterns, bugs, test coverage | Source files, tests, configs, dependency definitions, git history |
| **Bug / Error** | Root cause, reproduction path, fix options | Error logs, stack traces, related code, recent diffs, dependency versions |
| **Config / Infrastructure** | Correctness, security, best practices, drift | Config files, environment variables, deployment scripts, official docs |
| **Architecture / Design** | Scalability, maintainability, coupling, patterns | Directory structure, dependency graph, interfaces, data flow |
| **Security Posture** | Vulnerabilities, attack surface, hardening gaps | Auth code, input validation, secrets handling, dependencies, permissions |
| **Tool / Dependency Choice** | Fit, maintenance status, alternatives, migration cost | Package manifests, changelogs, GitHub activity, official docs, benchmarks |
| **Plan / Proposal** | Feasibility, gaps, risks, best-practice alignment | The plan itself, comparable implementations, industry standards |

Select the matching type and load the corresponding investigation checklist from `references/checklists.md`. If the target spans multiple types, combine the relevant checklists.

---

## Phase 2: Gather Evidence

Start with the project itself. Read before you search.

### Internal Evidence (always do first)

1. Map the relevant file and directory structure.
2. Read the key files — source code, configs, logs, docs, tests, dependency definitions.
3. Search for patterns using Grep and Glob — error messages, TODO/FIXME/HACK comments, hardcoded values, deprecated APIs.
4. Check recent diffs if the analysis involves a bug or regression.
5. Run existing tests or linters if available and relevant.
6. Read any project documentation (README, CLAUDE.md, ADRs, changelogs).

### External Evidence (web research)

For anything current, version-sensitive, security-related, standards-based, or vendor-specific, use web research. Do not rely on training knowledge for version numbers, CVEs, deprecation status, or current best practices.

**Research protocol:**

- Run 5-15 searches scaled to complexity. Simple config review = 5. Full codebase audit = 15.
- Target primary sources first: official documentation, changelogs, security advisories, maintainer guidance, vendor docs.
- Use WebFetch on the highest-quality results to get complete context — search snippets alone are often insufficient.
- If the user has MCP tools available (context7 for library docs, exa for advanced search), prefer those for domain-specific lookups.
- Skip random blogs, SEO content farms, and low-quality aggregators unless they contain uniquely valuable firsthand experience.

### Evidence Classification

Tag every piece of evidence you collect:

- **[VERIFIED]** — Directly observed in code, config, logs, or output. You read it yourself.
- **[INFERRED]** — Reasonable deduction from verified evidence. State the reasoning chain.
- **[EXTERNAL]** — From web research. Cite the source.
- **[UNCERTAIN]** — Incomplete evidence or conflicting signals. State what's missing.

This classification carries through to your findings. Every claim in the report must trace back to tagged evidence.

---

## Phase 3: Multi-Lens Analysis

Analyze the evidence through four lenses. Not every lens applies to every target — use the ones relevant to the target type identified in Phase 1.

### Security Lens
- Authentication and authorization correctness
- Input validation and sanitization
- Secrets management (hardcoded credentials, exposed tokens, insecure storage)
- Dependency vulnerabilities (known CVEs, unmaintained packages)
- Permission models and least-privilege adherence
- Attack surface and exposure points

### Architecture Lens
- Separation of concerns, coupling, cohesion
- Data flow and dependency direction
- Scalability constraints and bottlenecks
- Error handling and failure modes
- API design and interface contracts
- Technical debt accumulation patterns

### Operations Lens
- Logging, monitoring, and observability gaps
- Deployment and rollback safety
- Configuration management and environment parity
- Resource usage and performance characteristics
- Backup, recovery, and disaster readiness
- CI/CD pipeline reliability

### Developer Experience Lens
- Code readability and maintainability
- Test quality, coverage, and reliability
- Documentation completeness and accuracy
- Onboarding friction for new contributors
- Build and development environment setup
- Naming conventions and consistency

For each lens, reference the detailed checklist in `references/checklists.md` for the matching target type.

---

## Phase 4: Synthesize Findings

Organize your findings using this severity framework:

| Severity | Definition | Example |
|---|---|---|
| **P0 — Critical** | Actively broken, security vulnerability, data loss risk, or blocking production | SQL injection in auth endpoint, credentials committed to repo |
| **P1 — High** | Will cause problems soon or under load, significant risk | Missing input validation on public API, no error handling on database calls |
| **P2 — Medium** | Should fix, improves quality/reliability/maintainability | Outdated dependency with known bugs, missing tests for critical path |
| **P3 — Low** | Nice to have, polish, minor improvement | Inconsistent naming conventions, missing JSDoc on internal helpers |

Assign a severity to every finding. If you're unsure, default to one level higher — it's better to flag something as more important and have the user deprioritize it than to bury a real issue.

---

## Phase 5: Self-Verification

Before writing the final report, run this self-check. This step is mandatory — do not skip it.

1. **Evidence audit:** For each finding, verify the evidence tag ([VERIFIED], [INFERRED], [EXTERNAL], [UNCERTAIN]) is accurate. Remove or downgrade any finding where the evidence doesn't actually support the claim.
2. **Completeness check:** Review the investigation checklist from `references/checklists.md` for the target type. Flag any areas you didn't cover and note them as "Not assessed" in the report.
3. **Contradiction scan:** Look for findings that contradict each other. Resolve or flag them explicitly.
4. **Actionability test:** Every recommendation in the action plan must be specific enough that someone could start working on it without asking clarifying questions. Rewrite any vague recommendations.
5. **Severity calibration:** Review your P0/P1 findings. Are they genuinely critical/high, or did you inflate severity? Adjust if needed.

Score internally (do not include scores in the report):
- Completeness (0-5): Did you cover all relevant areas?
- Evidence quality (0-5): Are findings well-supported?
- Actionability (0-5): Are recommendations specific and prioritized?

If any score is below 4, revisit that dimension before finalizing.

---

## Phase 6: Deliver the Report

Write the report in this exact structure. Be clear, concrete, and direct. Use simple language. Point to exact file paths, commands, versions, or sources whenever possible.

### Report Structure

**1. Executive Summary**
3-5 sentences. What was analyzed, the overall health assessment, and the most critical finding. A busy technical lead should get the full picture from this paragraph alone.

**2. Scope**
What was analyzed, what was not analyzed, and why. List specific files, directories, configs, or systems examined.

**3. Key Findings**
Each finding follows this format:

> **[P0/P1/P2/P3] Finding title**
>
> **What:** Plain-language description of the issue.
>
> **Evidence:** What you observed, with file paths, line numbers, or commands. Include the evidence tag ([VERIFIED], [INFERRED], [EXTERNAL], [UNCERTAIN]).
>
> **Impact:** What happens if this isn't addressed.
>
> **Fix:** Specific recommendation with enough detail to act on.

Order findings by severity (P0 first), then by impact within each severity level.

**4. Quick Wins**
3-5 items that can be fixed in under 30 minutes each and deliver immediate value. Reference the corresponding finding number.

**5. Step-by-Step Action Plan**
Numbered list of recommended actions in priority order. Each step includes:
- What to do (specific and actionable)
- Why it matters (one sentence)
- Estimated effort (quick/medium/significant)
- Dependencies on other steps (if any)

**6. Open Questions**
Anything you couldn't determine from available evidence. For each, explain what additional information or access would resolve it.

### Writing Standards

- Every claim traces to tagged evidence. No unsupported assertions.
- If evidence is incomplete, say so directly. Do not claim certainty where it doesn't exist.
- Use examples where they clarify. Show the problematic code or config alongside the recommendation.
- Avoid vague statements like "consider improving" or "could be better." State what specifically should change and why.
- When referencing web research, cite the source naturally (e.g., "per the React 19 migration guide...").

---

## Edge Cases

- **Minimal input:** If the user provides only a file path or directory with no context, investigate broadly across all relevant lenses and flag what you found. Note that a more targeted analysis would require knowing their specific concerns.
- **Very large codebase:** Map the structure first, identify the highest-risk areas, and focus the deep analysis there. Note which areas you assessed at a surface level vs. in depth.
- **No issues found:** Say so honestly. Confirm with evidence that the areas you checked are solid. Suggest areas for ongoing monitoring.
- **Implementation requested:** If the user explicitly asks for fixes alongside analysis, provide them after the report. Keep the analysis and implementation clearly separated.
