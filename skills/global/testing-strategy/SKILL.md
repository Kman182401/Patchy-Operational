---
name: testing-strategy
description: >
  This skill should be used when the user asks about "testing strategy", "what should I test", "test plan", "testing approach", "test coverage plan", "how to test this", "unit vs integration tests", "E2E testing", "test pyramid", "test architecture", "test data management", "CI test pipeline", or when building a new feature and needs guidance on which tests to write. For writing actual tests, prefer test-master or tdd-workflow skills instead.
---

# Testing Strategy

Design a practical testing strategy that catches real bugs without slowing development.

## Step 1: Understand What's Being Tested

Before recommending test types, clarify:

- **What's the system?** — API, UI, CLI, library, data pipeline, infrastructure?
- **What are the critical paths?** — The workflows where bugs cause the most damage.
- **What's the current state?** — Existing test suite, coverage, CI pipeline?
- **What's the team's testing culture?** — TDD, test-after, no tests at all?

## Step 2: The Testing Pyramid

Apply the right test type at the right level:

```
         /  E2E  \           Few — expensive, slow, brittle
        /----------\
       / Integration \       Some — test boundaries and contracts
      /----------------\
     /    Unit Tests     \   Many — fast, cheap, isolated
    /--------------------\
```

### Unit Tests
- **What:** Individual functions, methods, classes in isolation
- **When:** Pure logic, calculations, data transformations, state machines
- **Skip when:** The function is just glue code that calls other things
- **Key principle:** Test behavior, not implementation. If refactoring internals breaks tests, the tests are too coupled.

### Integration Tests
- **What:** Components working together — API + database, service + queue, auth + middleware
- **When:** Boundaries between systems, database queries, external API calls
- **Skip when:** The integration is trivial (simple CRUD with an ORM)
- **Key principle:** Use real dependencies where feasible (testcontainers, in-memory DBs). Mocks at boundaries hide real bugs.

### End-to-End Tests
- **What:** Full user workflows through the actual system
- **When:** Critical business flows — signup, checkout, payment, core feature
- **Skip when:** The workflow is already well-covered by integration tests
- **Key principle:** Keep the suite small and stable. Flaky E2E tests are worse than no E2E tests.

## Step 3: What to Test (and What Not To)

### Always test:
- Business logic and domain rules
- Error handling and edge cases
- Security-critical paths (auth, authorization, input validation)
- Data integrity (migrations, serialization/deserialization)
- Integration points with external services

### Often skip:
- Simple getters/setters with no logic
- Framework-generated boilerplate
- UI layout and styling (unless critical to the product)
- Third-party library internals

## Step 4: Test Quality Checklist

Good tests are:
- **Fast** — The full suite runs in under 5 minutes for unit tests
- **Deterministic** — No flaky tests. Same input = same result, every time.
- **Independent** — Tests don't depend on execution order or shared state
- **Readable** — Test names describe the scenario and expected outcome
- **Maintainable** — Refactoring production code doesn't require rewriting every test

## Output

Produce a testing strategy document with:
1. Recommended test types for each component/layer
2. Critical paths that need coverage first
3. Suggested test tooling (framework, assertion library, mocking)
4. Coverage targets (with reasoning — 80% is not always the right answer)
5. CI integration recommendations (when to run which tests)
