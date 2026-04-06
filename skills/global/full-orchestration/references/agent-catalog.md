# Agent Catalog — Full Reference

Complete reference for all 14 installed subagents. Use this when the quick reference table in SKILL.md is insufficient for selection.

## Implementation Agents (Blue)

### python-pro
- **Color:** Blue | **Model:** opus | **Max turns:** 20
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** Writing, reviewing, refactoring, debugging, or optimizing any `.py` file
- **Do NOT use for:** FastAPI-specific work (use `fastapi-developer` instead)
- **Trigger signals:** Python imports, .py file edits, pytest, type hints, async/await in Python

### fastapi-developer
- **Color:** Blue | **Model:** opus | **Max turns:** 20
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** FastAPI endpoints, Pydantic models, ASGI apps, async Python APIs
- **Do NOT use for:** General Python scripts, non-API Python code
- **Trigger signals:** FastAPI imports, Pydantic models, OpenAPI specs, dependency injection, ASGI

### cli-developer
- **Color:** Blue | **Model:** opus | **Max turns:** 20
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** CLI tools, argument parsers, terminal UIs, shell scripts needing structured design
- **Trigger signals:** Click, Rich, argparse, shell completions, terminal output formatting

## Infrastructure Agents (Cyan)

### docker-expert
- **Color:** Cyan | **Model:** opus | **Max turns:** 20
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** Dockerfiles, docker-compose, container images, orchestration, CI/CD container pipelines
- **Trigger signals:** Dockerfile, docker-compose.yml, container builds, image hardening, multi-stage builds

## Security Agents

### security-engineer (Red — Implementation)
- **Color:** Red | **Model:** opus | **Max turns:** 20
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** BUILDING auth systems, hardening infrastructure, managing secrets, CI/CD security integration
- **Do NOT use for:** Reviewing existing code (use auditor) or exploitation (use pentester)
- **Trigger signals:** Auth implementation, secret rotation, TLS config, firewall rules, zero-trust

### security-auditor (Red — Audit)
- **Color:** Red | **Model:** sonnet | **Max turns:** 10
- **Tools:** Read, Grep, Glob (read-only)
- **Use for:** REVIEWING code for vulnerabilities after implementation, compliance checks, OWASP Top 10
- **Do NOT use for:** Implementing security controls or offensive testing
- **Trigger signals:** Post-implementation review, vulnerability scan, secrets detection, compliance audit
- **Note:** Always run AFTER domain agents finish. Read-only — never modifies code.
- **Write/Edit restriction:** Allow Write/Edit only for the agent's own memory directory. Never use Write or Edit on project code, configs, or any file outside the memory path.

### penetration-tester (Orange — Offensive)
- **Color:** Orange | **Model:** opus | **Max turns:** 10
- **Tools:** Read, Grep, Glob, Bash
- **Use for:** OFFENSIVE security testing — exploitation, attack surface mapping, hands-on security validation
- **Do NOT use for:** Implementing defenses or passive code review
- **Trigger signals:** Pentest engagement, CTF, exploit development, attack simulation, red team

### Security Agent Disambiguation
| Need | Agent |
|------|-------|
| Build/write security controls | `security-engineer` |
| Review/audit existing code | `security-auditor` |
| Exploit/test vulnerabilities | `penetration-tester` |
| Unclear | Default to `security-auditor` (least destructive) |

## Debugging Agents (Orange)

### error-detective
- **Color:** Orange | **Model:** opus | **Max turns:** 15
- **Tools:** Read, Grep, Glob, Bash
- **Use for:** Diagnosing root causes of errors, stack traces, test failures through log analysis and hypothesis testing
- **Note:** Analyzes but never fixes — returns diagnosis to main session
- **Trigger signals:** Error messages, stack traces, test failures, unexpected behavior, crashes

## Performance Agents (Yellow)

### performance-engineer
- **Color:** Yellow | **Model:** opus | **Max turns:** 15
- **Tools:** Read, Bash, Grep, Glob
- **Use for:** Investigating slow performance, high resource usage, bottlenecks, scalability issues
- **Note:** Analyzes and benchmarks but does not modify project code
- **Trigger signals:** Slow response times, high CPU/memory, profiling, load testing, database optimization

## Analysis/Finance Agents (Purple)

### quant-analyst
- **Color:** Purple | **Model:** opus | **Max turns:** 15
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** Quantitative trading, financial modeling, backtesting, derivatives pricing, portfolio optimization
- **Trigger signals:** Trading strategies, risk analytics, alpha generation, market microstructure, statistical arbitrage

## Maintenance Agents (Green)

### dependency-manager
- **Color:** Green | **Model:** sonnet | **Max turns:** 15
- **Tools:** Read, Grep, Glob, Bash
- **Use for:** Dependency audits, CVE scanning, version conflict resolution, license compliance, update strategies
- **Note:** Does not modify project files — recommends only
- **Trigger signals:** requirements.txt changes, package.json updates, CVE alerts, version conflicts, license issues

## Critical Response Agents (Red)

### incident-responder
- **Color:** Red | **Model:** sonnet | **Max turns:** 25
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** Active incidents: security breaches, service outages, data corruption, operational emergencies
- **Trigger signals:** Production down, breach detected, data loss, service degraded, emergency

## Meta/Tooling Agents (Magenta)

### skill-builder
- **Color:** Magenta | **Model:** opus | **Max turns:** 25
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** Creating, editing, validating, or improving Claude Code skills (SKILL.md files)
- **Do NOT use for:** Agent creation (use `subagent-builder`)
- **Trigger signals:** New skill, edit SKILL.md, skill validation, trigger phrase improvement

### subagent-builder
- **Color:** Magenta | **Model:** opus | **Max turns:** 25
- **Tools:** Read, Write, Edit, Bash, Glob, Grep
- **Use for:** Creating, editing, validating, or improving subagent definitions in ~/.claude/agents/
- **Do NOT use for:** Skill creation (use `skill-builder`)
- **Trigger signals:** New agent, edit agent .md, frontmatter design, color assignment, tool selection

## Common Multi-Agent Workflows

### Standard Code Change
1. Domain agent implements (python-pro, fastapi-developer, etc.)
2. `security-auditor` reviews afterward
3. `error-detective` if failures occur

### Debugging Workflow
1. `error-detective` diagnoses
2. Domain agent fixes
3. `security-auditor` reviews fix
4. `performance-engineer` if performance-related

### Infrastructure Change
1. `docker-expert` implements
2. `security-auditor` reviews
3. `dependency-manager` if packages changed

### New Feature (Full)
1. Domain agent implements
2. `security-auditor` reviews
3. `performance-engineer` if scale matters
4. `dependency-manager` if new deps added
