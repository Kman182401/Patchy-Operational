# Claude.ai Project Patterns Reference

## XML-Structured Project Instruction Template

Use this template structure for all Claude.ai Project custom instructions. Adapt sections to the domain — not all sections are needed for every project.

```xml
<role>
Define who Claude is in this project. Be specific about expertise, perspective, and communication style.
Keep to 2-3 sentences. Focus on what makes this role different from default Claude.
Example: "Senior Python backend engineer working on a FastAPI microservice. Prioritize performance and type safety. Explain trade-offs when multiple valid approaches exist."
</role>

<context>
Project background and environment. Include:
- Tech stack (languages, frameworks, databases, infrastructure)
- Project structure (key directories, entry points, config locations)
- Team conventions (naming, formatting, testing patterns)
- Current state (active features, known issues, migration status)

Source this from gather-context.sh output when available. Keep factual — no aspirational statements.
</context>

<rules>
Behavioral constraints specific to THIS project. Each rule should be:
- Actionable (can be followed or violated)
- Specific (not "write good code")
- Non-obvious (don't duplicate Claude's defaults)

Format as a numbered list. Group by category if over 10 rules.

Example rules:
1. Use snake_case for all Python identifiers; camelCase for TypeScript
2. Every API endpoint must have a corresponding test in tests/api/
3. Database migrations use Alembic — never modify models without a migration
4. If a requirement is ambiguous, ask before implementing
5. Never import from internal modules using relative paths
</rules>

<workflow>
Step-by-step procedures for the project's most common tasks.
Include 2-4 workflows maximum. Each should be concrete enough to follow without additional context.

Example:
### Adding a New API Endpoint
1. Define the Pydantic model in app/schemas/
2. Create the route handler in app/routes/
3. Add the database query in app/crud/
4. Write tests in tests/api/test_{resource}.py
5. Run `pytest tests/api/` to verify
6. Update the OpenAPI description if the endpoint is public
</workflow>

<output_format>
How Claude should structure responses in this project.
- Code style preferences (comments, docstrings, type annotations)
- Response length expectations
- When to show full files vs. diffs
- When to explain vs. just do

Example: "Show only changed code with 3 lines of context. Add type annotations to all function signatures. Skip docstrings unless the function is public API."
</output_format>
```

## Domain-Specific Instruction Patterns

### Coding Projects

Focus on: tech stack, conventions, testing, deployment pipeline.

Key rules to include:
- Language/framework version constraints
- Import organization and module boundaries
- Error handling patterns (custom exceptions, error codes)
- Testing requirements (coverage threshold, test location, fixture patterns)
- Git workflow (branch naming, commit message format, PR requirements)

Knowledge files to upload:
- Database schema or ERD
- API specification (OpenAPI/Swagger)
- Architecture decision records (ADRs)
- Style guide excerpts (only project-specific deviations from standard)

### Security Projects

Focus on: threat model, compliance requirements, tooling, audit patterns.

Key rules to include:
- Classification levels for findings (critical/high/medium/low criteria)
- Required evidence for each finding (PoC, screenshot, log excerpt)
- Scope boundaries (what's in/out of scope)
- Disclosure and communication protocols
- Tool preferences and configuration

Knowledge files to upload:
- Threat model document
- Compliance checklist (SOC2, HIPAA, PCI-DSS requirements)
- Previous audit findings for context
- Network diagram or architecture overview

### Research Projects

Focus on: methodology, source evaluation, output format, uncertainty handling.

Key rules to include:
- Source hierarchy (primary sources over secondary, peer-reviewed over blogs)
- Citation format requirements
- Confidence level labeling (verified, likely, uncertain, unknown)
- Scope boundaries (what topics to include/exclude)
- Bias awareness checks

Knowledge files to upload:
- Literature review or bibliography
- Methodology documentation
- Domain glossary
- Previous research outputs for style reference

### Writing Projects

Focus on: voice, audience, structure, editorial standards.

Key rules to include:
- Tone and formality level
- Target audience description and reading level
- Structural templates (blog post, report, documentation)
- Word count targets per section
- Terminology consistency rules (glossary terms)

Knowledge files to upload:
- Style guide
- Brand voice documentation
- Example outputs (best-in-class samples)
- Terminology glossary

### DevOps Projects

Focus on: infrastructure state, deployment pipeline, monitoring, incident response.

Key rules to include:
- Infrastructure-as-code standards (Terraform module structure, naming)
- Deployment checklist (pre/post deployment verification)
- Rollback procedures
- Alert threshold definitions
- Change management process

Knowledge files to upload:
- Infrastructure diagram
- Runbook collection
- Monitoring dashboard definitions
- Incident response playbook

### Data/ML Projects

Focus on: data pipeline, model lifecycle, evaluation metrics, reproducibility.

Key rules to include:
- Data schema definitions and validation rules
- Feature engineering conventions
- Model evaluation criteria (metrics, thresholds, baselines)
- Experiment tracking requirements
- Data privacy and PII handling rules

Knowledge files to upload:
- Data dictionary
- Model card template
- Evaluation results from baseline models
- Pipeline DAG documentation

---

## Common Mistakes Checklist

Audit instructions against these before finalizing:

### Instruction Bloat
- **Symptom:** Instructions exceed 1500 words
- **Fix:** Move detailed procedures to knowledge files. Instructions set policy; knowledge files provide detail.
- **Test:** Can each instruction be understood without reading other instructions?

### Duplicating Profile Preferences
- **Symptom:** Rules like "be concise" or "use markdown formatting" that match the user's Claude profile
- **Fix:** Remove anything that matches default Claude behavior or the user's profile settings. Project instructions add to profiles, not replace them.
- **Test:** Would removing this rule change Claude's behavior in this project?

### Generic Rules
- **Symptom:** "Write clean code" or "Follow best practices"
- **Fix:** Replace with specific, testable rules. "Functions under 30 lines. No nested callbacks deeper than 2 levels."
- **Test:** Could this rule apply to literally any project? If yes, it's too generic.

### Missing Uncertainty Handling
- **Symptom:** No guidance on what to do when requirements are unclear
- **Fix:** Add explicit rules: "If a requirement has multiple valid interpretations, list them and ask which to implement."
- **Test:** What happens when Claude encounters an ambiguous request?

### Over-Constraining Output
- **Symptom:** Rigid output templates for every response type
- **Fix:** Define output format for the 2-3 most common response types. Let Claude adapt for edge cases.
- **Test:** Does the output format work for the project's 5 most common queries?

### Ignoring Project State
- **Symptom:** Instructions written for a greenfield project when the codebase already exists
- **Fix:** Reference actual project structure, existing patterns, current limitations.
- **Test:** Do instructions reference real directories, files, and conventions?

### Knowledge File Duplication
- **Symptom:** Same information in instructions AND knowledge files
- **Fix:** Instructions reference knowledge files by name. "See api-schema.md for endpoint definitions."
- **Test:** Is any paragraph of instructions also present in a knowledge file?

---

## Token Budget Guidance

### Custom Instructions: Target 800-1200 words (max 1500)

**Why this limit matters:** Instructions are injected into every conversation turn. Bloated instructions waste tokens on every message and dilute the most important rules.

**Budget allocation:**
- Role: 50-75 words
- Context: 150-250 words
- Rules: 200-400 words (10-20 rules)
- Workflow: 200-350 words (2-4 procedures)
- Output format: 50-100 words

**Overflow strategy:** When instructions exceed budget:
1. Move detailed workflows to a knowledge file named `workflows.md`
2. Move context details to a knowledge file named `project-context.md`
3. Keep rules in instructions (they must be always-present)
4. Reference knowledge files: "Follow the deployment workflow in `workflows.md`"

### Knowledge Files: Target 5-15 files, each 500-3000 words

Larger files (over 3000 words) reduce retrieval precision. Split by topic.

---

## Knowledge File Selection Criteria

### Upload When:
- The information is **stable** (doesn't change weekly)
- Claude needs it to **produce correct output** (schemas, specs, conventions)
- The information is **project-specific** (not general programming knowledge)
- It would take **multiple messages** to communicate inline
- **Retrieval will work** (clear headings, self-contained sections)

### Skip When:
- The content **changes frequently** (it will go stale)
- It's **general knowledge** Claude already has (React docs, Python stdlib)
- It's a **large codebase dump** (Claude can't effectively retrieve from code blobs)
- It contains **secrets or credentials**
- It's **auto-generated** (lock files, build output, coverage reports)

### File Naming Convention
Use descriptive, kebab-case names that indicate content:
- `api-schema.md` (not `schema.md`)
- `database-migrations-guide.md` (not `db.md`)
- `team-coding-conventions.md` (not `rules.md`)

---

## RAG-Awareness Notes

Claude.ai Projects use retrieval-augmented generation to pull relevant sections from knowledge files. Structure files to optimize retrieval:

### Heading Strategy
- Use descriptive H2 headers as retrieval anchors: `## Authentication Flow` not `## Section 3`
- Include keywords in headings that match how users ask questions
- Avoid generic headings: `## Overview`, `## Introduction`, `## Misc`

### Section Self-Containment
- Each section should make sense without reading preceding sections
- Include enough context in each section for it to stand alone
- Cross-reference other sections by heading name, not "see above"

### One Topic Per File
- `auth-flow.md` + `data-model.md` + `api-endpoints.md` retrieves better than `everything.md`
- If a file covers multiple topics, retrieval may pull irrelevant sections
- Exception: closely related topics that are always needed together

### Front-Load Key Information
- Put the most important content in the first paragraph of each section
- Lead with definitions, then examples, then edge cases
- Retrieval may truncate — put critical info early

### Concrete Examples
- Place examples immediately after the concept they illustrate
- Use realistic data, not placeholder values
- Label examples clearly: "Example: Creating a new user endpoint"

### Avoid These Anti-Patterns
- **Wall of text:** Break into sections with headers every 200-300 words
- **Table of contents only:** ToC pages retrieve poorly — content pages retrieve well
- **Nested bullet lists 4+ levels deep:** Flatten or convert to prose
- **Code-only files:** Add prose context explaining what the code does and when to use it
