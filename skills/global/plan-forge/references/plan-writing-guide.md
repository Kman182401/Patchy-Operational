# Claude Code Plan Writing — Reference Guide

*Load this file when writing the implementation plan (Deliverable 2) for additional guidance.*

-----

## The Spec-First Principle

Claude Code performs best when given a written spec before it starts coding.
The plan file IS the spec. Every ambiguity resolved here is a bug prevented later.

From official Claude Code docs:

> "For larger features, have Claude interview you first... Once the spec is complete,
> start a fresh session to execute it. The new session has clean context focused
> entirely on implementation."

The plan-forge skill implements this pattern. The plan output IS the fresh session input.

-----

## Plan Structure Best Practices (2026)

### Context Loading

Always instruct Claude Code to read specific files before starting:

```
Before beginning any implementation, read the following files in full:
- CLAUDE.md (project rules)
- [file1] (understand existing pattern)
- [file2] (understand current implementation)
Do not begin coding until you have read all listed files.
```

### Task Atomicity

Each task should be:

- **Single-file focused** where possible
- **Independently verifiable** — can you test just this task?
- **Explicitly scoped** — what exactly changes, nothing else

Bad: "Improve the scoring system"
Good: "In `quality.py`, modify `_score_codec()` to return -5 for HEVC/x265 when resolution tier is 1080p or lower, and +10 for HEVC/x265 when resolution tier is 2160p/4K. Do not change the function signature."

### Verification Specificity

Every task needs a concrete check:

- Run this command -> expect this output
- Run these tests -> expect all to pass
- Check this log -> expect this value
- Open this file -> expect this content

Vague: "Make sure it works"
Good: "Run `pytest tests/test_quality.py::test_codec_scoring -v` — expect 4 passing tests"

### The "Do Not Touch" Section

Critical for preventing scope creep:

```
## Out of Scope — Do Not Modify
- tests/test_quality.py (test file — read only, do not edit)
- config/settings.json (configuration — no changes needed)
- Any file not listed in Implementation Tasks above
```

### Pattern References

Instead of describing patterns in words, reference existing code:

```
Follow the exact same pattern as the `_score_resolution()` function
when implementing `_score_codec()`. Same return type, same guard clauses,
same error handling approach.
```

-----

## Common Anti-Patterns to Avoid in Plans

| Anti-Pattern                      | Problem                                       | Fix                                                            |
|-----------------------------------|-----------------------------------------------|----------------------------------------------------------------|
| "Fix the bug in the filter"       | Claude doesn't know which bug or which filter  | Name the file, function, line if known, exact behavior         |
| "Refactor for better readability" | Subjective, infinite scope                     | Name specific functions, define what "better" means concretely |
| "Update the tests"                | No direction on what to test                   | List exact test cases required                                 |
| "Use best practices"              | Ambiguous                                      | Reference the specific pattern in the codebase to follow       |
| "Make it faster"                  | No metric                                      | Specify expected performance target                            |
| References to "the main file"     | Claude may read wrong file                     | Always use full relative paths                                 |

-----

## Bug Fix Plan Template

When the input is a bug report, the plan must include:

```markdown
## Bug Description
**Symptom:** [What the user sees / what goes wrong]
**Expected behavior:** [What should happen instead]
**Reproduction:** [Exact steps to reproduce]
**Frequency:** [Always / sometimes / under these conditions]

## Root Cause (if identified)
[Where in the code the bug originates. If unknown, instruct Claude Code to
 investigate before implementing: "Locate the root cause by reading [files].
 Do not implement a fix until you have identified the exact source."]

## Fix
[Specific change to make]
```

-----

## Feature Plan Template Addition

When adding new functionality:

```markdown
## Integration Points
[Every existing component this feature must connect to.
 Every file that must be read to understand the connection.
 Every pattern that must be followed for consistency.]

## New Files Required
- `path/to/new_file.py` — [purpose]
[List every new file Claude Code must create]

## Modified Files
- `path/to/existing.py` — [what changes and why]
```

-----

## Verification Command Patterns

```bash
# Python projects
pytest tests/ -v                          # Run all tests
pytest tests/test_X.py -v                 # Run specific test file
pytest -k "test_name" -v                  # Run specific test
python -m py_compile src/file.py          # Syntax check

# Node.js projects
npm test                                  # Run test suite
node -c file.js                           # Syntax check

# General
git diff --stat                           # See what changed
git status                                # Confirm only expected files modified
```

-----

## CLAUDE.md Integration

If the project has a CLAUDE.md, the plan must reference it:

```markdown
## Project Rules (from CLAUDE.md)
The following rules from this project's CLAUDE.md apply to this implementation:
- [Copied relevant rules verbatim]

Claude Code will read CLAUDE.md at session start. These rules are provided
here as a reminder — do not violate them during implementation.
```

-----

## Subagent Hints (advanced)

For complex plans with clearly separable concerns, suggest subagent delegation:

```markdown
## Suggested Subagent Strategy
This plan has two independent concerns that can be parallelized:
- Task 1-3: Core logic changes (implementation agent)
- Task 4-5: Test updates (test-runner agent)

Use: "Delegate tasks 4-5 to a subagent to keep main context clean."
```
