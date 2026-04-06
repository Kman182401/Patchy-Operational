# Example Orchestration Trace: FastAPI Rate Limiter

Task: "Build a rate limiter for the `/api/trades` FastAPI endpoint"

## Phase 1: Intake — Classify and Tag

**Domain tags identified:** Python, FastAPI, Security, Performance

| Check | Result |
|-------|--------|
| Creative/new feature? | Yes — invoke `brainstorming` skill |
| Bug/error? | No |
| External research? | Yes — invoke `context7` MCP for FastAPI middleware docs |

**Agents queued:** `fastapi-developer` (primary), `security-engineer` (rate limiting is a security control)

## Phase 2: Planning — Design the Approach

**Skills invoked:**
1. `plan-builder` — produce implementation plan with milestones
2. `feature-forge` — clarify requirements (token bucket vs sliding window, per-IP vs per-user)
3. `fastapi-expert` domain skill — FastAPI middleware and dependency injection patterns
4. `system-design` — evaluate where rate state lives (in-memory vs Redis)

**Plan output:** 4 milestones — middleware scaffold, rate algorithm, Redis backend, integration tests

## Phase 3: Execution — Delegate to Agents

### Sequential dispatch (shared state between steps)

**Step 3a — Implement core middleware**
- Spawn `fastapi-developer` (blue, opus, 20 turns)
- Task: Create `app/middleware/rate_limiter.py` with sliding window algorithm
- Also create Pydantic config model in `app/schemas/rate_limit.py`

**Step 3b — Implement Redis backend**
- Spawn `fastapi-developer` continues (same shared state)
- Task: Add Redis connection pool and rate state storage
- Invoke `tdd-workflow` skill — write tests before implementation

**Step 3c — Security hardening**
- Spawn `security-engineer` (red, opus, 20 turns)
- Task: Review rate limiter for bypass vectors (header spoofing, distributed attacks)
- Add IP validation and configurable block duration

**Execution skills active throughout:**
- `tdd-workflow` — test-first for each component
- `linter` — auto-lint after every file edit
- `secure-code-guardian` — validate no timing side-channels in rate check

## Phase 4: Verification — Validate Everything

**Mandatory post-implementation chain:**

| Order | Action | Tool/Skill |
|-------|--------|------------|
| 1 | Run all tests | `test-runner` skill |
| 2 | Lint edited files | `linter` skill |
| 3 | Security review | `security-auditor` agent (read-only) |
| 4 | Performance check | `performance-engineer` agent — benchmark under load |
| 5 | Deep analysis | `analyze` skill |
| 6 | Final confirmation | `verification-before-completion` skill |

**Parallel where possible:** Steps 2 and 3 run in parallel (independent checks on final code).

---

## Phase 5: Completion — Close Out

**Skills invoked:**
1. `code-reviewer` — generate review summary for the feature
2. `finishing-a-development-branch` — prepare branch for merge
3. `documentation` — update API docs with rate limit headers and error codes

**Handoff:** Report rate limiter configuration options, test results, and benchmark numbers. Prompt next step: "Deploy to staging and run integration tests against live Redis."
