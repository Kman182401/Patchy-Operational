---
name: reuse-check
description: This skill should be used when the user asks to "check if this exists", "reuse check", "don't reinvent the wheel", "find existing solution", "is there already a", or before implementing any new function, utility, class, component, or wrapper. Systematically scans the codebase and installed packages for existing solutions that could be reused, extended, or wrapped instead of built from scratch.
---

# Reuse Check

## Purpose

Avoid duplicate code and wasted effort by finding existing solutions before building new ones. This is a prefix skill -- run it before writing any new function, utility, class, or component. The goal is to surface what already exists so the implementation decision is informed, not blind.

$ARGUMENTS

## When to Trigger

- Before writing any new function, utility, helper, or class
- Before adding a new dependency to the project
- Before creating a new wrapper around an external service (HTTP client, database client, logger, etc.)
- When the user explicitly asks to check for existing solutions
- When the implementation task feels like something that "probably exists already"

## Workflow

### Step 1 -- Define What the New Code Needs to Do

Before searching, clearly state the specification of the planned implementation:

- **Input:** What data or arguments does it accept?
- **Output:** What does it return or produce?
- **Side effects:** Does it write to disk, make network calls, mutate state?
- **Behavior:** What transformation, validation, or logic does it perform?

This specification becomes the search target. Without it, the search will be unfocused and miss relevant matches.

### Step 2 -- Search the Codebase

Run these searches in parallel where possible:

#### 2a. Name-based search

Grep for function names, class names, and variable names related to the planned functionality. Think about what a previous developer might have named it:

- Synonyms: `format_date`, `parse_date`, `convert_date`, `date_to_string`
- Abbreviations: `fmt_date`, `dt_format`, `date_fmt`
- Common prefixes: `get_`, `create_`, `build_`, `make_`, `parse_`, `format_`, `validate_`, `ensure_`

Search for the core noun (e.g., `date`, `user`, `config`, `request`) across the codebase to find all related code.

#### 2b. Directory-based search

Glob for files in directories where shared utilities typically live:

- `**/utils/**`, `**/helpers/**`, `**/lib/**`, `**/common/**`, `**/shared/**`
- `**/core/**`, `**/base/**`, `**/internal/**`, `**/pkg/**`
- `**/middleware/**`, `**/decorators/**`, `**/mixins/**`

Read the files found in these directories. Utilities are often undiscoverable by name alone because they use generic names like `helpers.py` or `utils.ts`.

#### 2c. Import-based search

Check imports in files related to the current task. Follow the import chain:

- Read the file being modified or its neighbors
- Grep for `import` or `from` statements referencing utility modules
- Trace those imports back to their source files and read them

This often reveals utility modules that are well-used but not obviously named.

#### 2d. Package manifest search

Read the project's dependency files to check for installed libraries that might already handle the need:

- Python: `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt`, `Pipfile`
- JavaScript/TypeScript: `package.json`
- Rust: `Cargo.toml`
- Go: `go.mod`
- Ruby: `Gemfile`

For each dependency found, consider whether it provides the needed functionality as a built-in feature. Many libraries include utility functions beyond their primary purpose.

### Step 3 -- Search Installed Packages and Standard Library

#### 3a. Standard library check

Before reaching for third-party code, check if the language's standard library handles this:

- Python: `pathlib`, `itertools`, `functools`, `collections`, `dataclasses`, `datetime`, `json`, `re`, `shutil`, `textwrap`, `urllib.parse`
- JavaScript: `Array` methods, `Object` methods, `URL`, `crypto`, `path`, `fs`
- Identify the standard library module that covers this domain and check its API

#### 3b. Installed dependency check

For dependencies already in the project, check their docs or source for the needed capability:

- Run `pip show <package>` or check the package's module contents
- Search node_modules for relevant exports
- Check if an existing dependency has a sub-module or utility function that covers the need

Do not add a new dependency if an existing one already handles it.

### Step 4 -- Evaluate Findings

Classify each finding into one of three categories:

#### Exact match
An existing function, class, or library method does exactly what is needed. Action: use it directly. Provide the import path and usage example.

#### Partial match
Something exists that handles part of the need, or handles a similar but different case. Action: evaluate whether to extend the existing code or wrap it. Extending is preferred when:
- The existing code is in the same project and has clear ownership
- The extension is a natural addition (e.g., adding a parameter, handling a new format)
- The existing code has tests that can be extended too

Building new is preferred when:
- The existing code is in a third-party package and cannot be modified
- The "extension" would require changing the existing function's contract
- The overlap is superficial and the implementations would diverge

#### No match
Nothing relevant was found. Action: proceed with the new implementation, but document in the output what was searched so the decision is traceable.

### Step 5 -- Report

Produce a brief report with this structure:

```
## Reuse Check: [what was being built]

**Searched for:** [one-line description of the capability]

**Codebase findings:**
- [file path] -- [what it does, relevance level]
- [file path] -- [what it does, relevance level]
- (or "No relevant code found in codebase")

**Package findings:**
- [package name] -- [relevant capability]
- (or "No relevant installed packages found")

**Standard library:**
- [module.function] -- [relevant capability]
- (or "No standard library match")

**Recommendation:** Reuse [path/package] | Extend [path] | Build new
**Reason:** [one sentence]
```

If the recommendation is "reuse" or "extend," include the import statement and a brief usage example so the implementing agent can proceed immediately.

## Anti-Patterns This Skill Prevents

- Writing a new date/time formatter when `datetime.strftime`, `dateutil`, or an existing `format_date()` utility already exists
- Creating a new HTTP client wrapper when one is already configured with auth, retries, and base URL
- Reimplementing validation logic (email, URL, phone) that exists in an installed library or shared validator
- Adding `requests` when `httpx` is already installed and configured
- Writing a new config loader when the project already has one in `core/config.py`
- Building a new logger setup when the project has a configured logging module
- Creating a new retry decorator when `tenacity` is already a dependency
- Writing custom path manipulation when `pathlib` handles it natively

## Edge Cases

- **Multiple partial matches:** Report all of them. Let the implementing agent or user choose which to extend.
- **Match exists but is poorly written:** Still report it. Refactoring existing code is often better than creating a parallel implementation that will confuse future developers.
- **Match exists in a test file only:** Note it as a test-only utility. It may be worth promoting to a shared module.
- **Match exists but is deprecated or marked for removal:** Note the deprecation. Do not reuse deprecated code -- proceed with new implementation but flag the old code for cleanup.
