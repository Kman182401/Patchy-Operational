# Claude Code Ecosystem Inventory
Generated: 2026-04-05

**Claude Code:** v2.1.92 | **Node:** v22.22.1 | **Binary:** `/home/karson/.local/bin/claude` (wrapped via zsh function)
**Model:** Claude Opus 4.6 (1M context) | **Advisor Model:** claude-opus-4-6

---

## User-Level Subagents (12)

Path: `~/.claude/agents/`

| Agent | Model | Purpose | Tools | maxTurns | Memory | R/W | Color |
|-------|-------|---------|-------|----------|--------|-----|-------|
| cli-developer | sonnet | Build CLI tools, argument parsers, terminal UIs, shell scripts; expert in Click, Rich, argparse | Read, Write, Edit, Bash, Glob, Grep | 20 | user | R/W | blue |
| dependency-manager | haiku | Dependency audits, CVE scanning, version conflicts, license compliance, update strategies; read-only analysis | Read, Grep, Glob, Bash | 15 | user | Read-only | green |
| docker-expert | sonnet | Dockerfiles, docker-compose, container images, orchestration; multi-stage builds, image hardening, CI/CD | Read, Write, Edit, Bash, Glob, Grep | 20 | user | R/W | cyan |
| error-detective | sonnet | Diagnose errors, stack traces, test failures via log analysis and hypothesis testing; returns diagnosis only | Read, Grep, Glob, Bash | 15 | user | Read-only | orange |
| fastapi-developer | sonnet | FastAPI endpoints, Pydantic models, ASGI apps, async Python APIs; FastAPI 0.100+, dependency injection | Read, Write, Edit, Bash, Glob, Grep | 20 | user | R/W | blue |
| incident-responder | sonnet | Active incidents: security breaches, outages, data corruption; rapid triage, evidence preservation, recovery | Read, Write, Edit, Bash, Glob, Grep | 20 | user | R/W | red |
| penetration-tester | opus | Offensive security testing: vulnerability exploitation, attack surface mapping, OWASP methodology | Read, Grep, Glob, Bash | 10 | user | Read-only | orange |
| performance-engineer | sonnet | Investigate slow performance, bottlenecks, scalability; profiling, load testing, DB optimization; read-only | Read, Bash, Grep, Glob | 15 | user | Read-only | yellow |
| python-pro | sonnet | All Python code: writing, reviewing, refactoring, debugging .py files; Python 3.11+, async, type hints, pytest | Read, Write, Edit, Bash, Glob, Grep | 20 | user | R/W | blue |
| quant-analyst | opus | Quantitative trading, financial modeling, backtesting, derivatives pricing, portfolio optimization | Read, Write, Edit, Bash, Glob, Grep | 15 | user | R/W | purple |
| security-auditor | opus | Post-implementation security review: OWASP Top 10, secrets detection, compliance; never modifies code | Read, Grep, Glob | 10 | user | Read-only | red |
| security-engineer | sonnet | Implement security controls: auth systems, infrastructure hardening, secrets management, DevSecOps | Read, Write, Edit, Bash, Glob, Grep | 20 | user | R/W | red |

### Routing Summary
- **Python code** → python-pro (sonnet)
- **FastAPI / async APIs** → fastapi-developer (sonnet)
- **CLI tools / terminal** → cli-developer (sonnet)
- **Docker / containers** → docker-expert (sonnet)
- **Trading / finance** → quant-analyst (opus)
- **Security implementation** → security-engineer (sonnet)
- **Security review (post-code)** → security-auditor (opus, read-only)
- **Offensive security testing** → penetration-tester (opus, read-only)
- **Error diagnosis** → error-detective (sonnet, read-only)
- **Performance profiling** → performance-engineer (sonnet, read-only)
- **Active incidents** → incident-responder (sonnet)
- **Dependency audits** → dependency-manager (haiku, read-only)

---

## Patchy Bot Project Agents (9)

Path: `~/Patchy_Bot/.claude/agents/`

| Agent | Model | Purpose | Tools | Memory | R/W | Color |
|-------|-------|---------|-------|--------|-----|-------|
| config-infra-agent | opus | Config system, env vars, startup sequence, systemd service, logging, .env structure, VPN config | Read, Write, Edit, Bash, Grep, Glob | project | R/W | yellow |
| database-agent | opus | SQLite Store class, 11 tables, CRUD methods, migrations, backup operations, data integrity | Read, Write, Edit, Bash, Grep, Glob | project | R/W | blue |
| plex-agent | opus | Plex Media Server integration, PlexInventoryClient, media file organization, library scanning | Read, Write, Edit, Bash, Grep, Glob | project | R/W | pink |
| remove-agent | opus | Media deletion flows, path safety validation, Plex cleanup, remove background runner, browse-library UI | Read, Write, Edit, Bash, Grep, Glob | project | R/W | pink |
| schedule-agent | opus | TV episode tracking, schedule system, TVMaze/TMDB metadata, auto-download, schedule runner | Read, Write, Edit, Bash, Grep, Glob | project | R/W | pink |
| search-download-agent | opus | Torrent searching, download initiation, progress tracking, completion poller, QBClient operations | Read, Write, Edit, Bash, Grep, Glob | project | R/W | pink |
| security-agent | opus | Auth system review, rate limiting, path safety, input validation, secrets management; READ-ONLY | Read, Grep, Glob, Bash | project | Read-only | red |
| test-agent | opus | Writing/running tests, debugging failures, coverage improvement, test infrastructure | Read, Write, Edit, Bash, Grep, Glob | project | R/W | green |
| ui-agent | opus | Telegram UI rendering, inline keyboards, message formatting, callback routing, flow UI state machines | Read, Write, Edit, Bash, Grep, Glob | project | R/W | cyan |

### Patchy Bot Agent Routing
- **Config / env / startup / systemd** → config-infra-agent
- **Database / Store / SQLite** → database-agent
- **Plex / media organization** → plex-agent
- **Deletion / remove / path safety** → remove-agent
- **TV schedule / episodes / tracking** → schedule-agent
- **Search / download / progress / qBT** → search-download-agent
- **Security review** → security-agent (read-only)
- **Tests / coverage** → test-agent
- **Telegram UI / keyboards / callbacks** → ui-agent

---

## User Skills (89)

Path: `~/.claude/skills/*/SKILL.md`

| Skill | Purpose | Context | Agent |
|-------|---------|---------|-------|
| analyze | Deep post-completion review; finds missed issues after code changes | fork | general-purpose |
| angular-architect | Angular 17+ standalone components, NgRx, RxJS, routing, bundle optimization | default | — |
| api-designer | REST/GraphQL API design, OpenAPI specs, resource modeling, versioning | default | — |
| architecture-designer | High-level system architecture, ADRs, tech trade-offs, scalability planning | default | — |
| atlassian-mcp | Jira/Confluence integration via MCP; JQL, CQL, sprints, backlogs | default | — |
| audit | Deep read-only audit of repo/system/config; structured findings report | fork | Plan |
| chaos-engineer | Chaos experiments, failure injection, game day exercises, resilience testing | default | — |
| cli-developer | CLI tools, argument parsing, shell completions, progress bars (Click, typer, cobra) | default | — |
| cloud-architect | Cloud architectures across AWS/Azure/GCP; migration, cost optimization, DR | default | — |
| code-documenter | Docstrings, OpenAPI specs, JSDoc, doc portals, user guides | default | — |
| code-reviewer | Code diffs analysis: bugs, security vulns, code smells, N+1 queries; structured review report | default | — |
| cpp-pro | Modern C++20/23, template metaprogramming, SIMD, memory management, CMake | default | — |
| csharp-developer | C# .NET 8+, ASP.NET Core, Blazor, Entity Framework Core, CQRS/MediatR | default | — |
| database-optimizer | SQL query optimization, execution plans, index design, partitioning (PostgreSQL/MySQL) | default | — |
| debugger | Systematic debugging: reproduce-isolate-identify-fix-verify methodology | fork | general-purpose |
| debugging-wizard | Error parsing, stack trace analysis, log correlation, hypothesis-driven root cause analysis | default | — |
| devops-engineer | Dockerfiles, CI/CD pipelines, K8s manifests, Terraform/Pulumi, GitOps, platform engineering | default | — |
| django-expert | Django 5.0, DRF, ORM optimization, JWT auth, serializers, viewsets | default | — |
| dotnet-core-expert | .NET 8 minimal APIs, clean architecture, EF Core, CQRS, AOT compilation | default | — |
| embedded-systems | Firmware for STM32/ESP32, FreeRTOS, bare-metal, power optimization, DMA, interrupts | default | — |
| eval-harness | Eval-driven development (EDD) framework for AI-assisted workflow evaluation | default | — |
| exa-ai | AI-powered neural/semantic web search via Composio Rube MCP | default | — |
| expert-analysis | Deep evidence-first investigation; structured report with action plan | fork | general-purpose |
| extracta-ai | AI document parsing: PDFs, invoices, receipts via Composio Rube MCP | default | — |
| fastapi-expert | FastAPI + Pydantic V2, async SQLAlchemy, JWT auth, WebSocket endpoints, OpenAPI | default | — |
| feature-forge | Requirements workshops: feature specs, user stories, EARS-format requirements, acceptance criteria | default | — |
| fine-tuning-expert | LLM fine-tuning: LoRA/QLoRA, PEFT, RLHF, DPO, dataset prep, hyperparameter tuning | default | — |
| flutter-expert | Flutter 3+ / Dart, Riverpod/Bloc, GoRouter, cross-platform mobile apps | default | — |
| fullstack-guardian | Security-focused full-stack web apps: frontend + backend + security at every layer | default | — |
| game-developer | Unity/Unreal, ECS, physics, multiplayer networking, shader programming, game AI | default | — |
| golang-pro | Go 1.21+, goroutines/channels, gRPC, microservices, generics, interfaces | default | — |
| graphql-architect | GraphQL schema design, Apollo Federation 2.5+, DataLoader, subscriptions | default | — |
| java-architect | Spring Boot 3.x, WebFlux, JPA, Spring Security, OAuth2/JWT, microservices | default | — |
| javascript-pro | ES2023+, async/await, ESM, Node.js APIs, Web Workers, browser performance | default | — |
| kotlin-specialist | Kotlin 1.9+, coroutines, Flow, KMP, Compose, Ktor, DSL design | default | — |
| kubernetes-specialist | K8s manifests, Helm, RBAC, NetworkPolicies, Operators, service mesh, multi-cluster | default | — |
| laravel-specialist | Laravel 10+, Eloquent, Sanctum auth, Horizon queues, Livewire, Pest/PHPUnit | default | — |
| legacy-modernizer | Incremental migration: strangler fig, branch by abstraction, monolith decomposition | default | — |
| linter | Auto-lint after edits: ruff (Python), shellcheck (Bash), prettier (JS/HTML/CSS) | fork | general-purpose |
| mcp-developer | Build/debug MCP servers and clients; tool handlers, resource providers, transport layers | default | — |
| microservices-architect | Distributed systems: service boundaries, DDD, sagas, event sourcing, CQRS, service mesh | default | — |
| ml-pipeline | ML pipeline infrastructure: MLflow, Kubeflow, Airflow, feature stores, model registries | default | — |
| monitoring-expert | Prometheus/Grafana, structured logging, alerting, distributed tracing, load testing, profiling | default | — |
| nestjs-expert | NestJS modules, controllers, services, DTOs, guards, interceptors; TypeORM/Prisma | default | — |
| nextjs-developer | Next.js 14+ App Router, server components, server actions, streaming SSR, Vercel deploy | default | — |
| ocr-web-service | OCR on images/PDFs/screenshots via Composio Rube MCP | default | — |
| pandas-pro | Pandas DataFrame operations: cleaning, aggregation, merging, time series | default | — |
| php-pro | PHP 8.3+, Laravel, Symfony, PHPStan level 9, Swoole async, PSR standards | default | — |
| plan-builder | Research-first implementation planner; produces durable ExecPlan-style spec before code changes | fork | general-purpose |
| plan-implementation | Execute an already approved plan end-to-end; post-planning execution with verification | default | — |
| playwright-expert | Playwright E2E tests, page objects, fixtures, reporters, CI integration, visual regression | default | — |
| postgres-pro | PostgreSQL optimization: EXPLAIN, JSONB, replication, VACUUM, extensions, pgvector | default | — |
| prompt-engineer | LLM prompt design, optimization, evaluation; chain-of-thought, few-shot, structured outputs | default | — |
| python-pro | Python 3.11+ type safety, async, pytest, mypy strict, dataclasses, structured error handling | default | — |
| rag-architect | RAG systems: chunking, embeddings, vector stores, hybrid search, reranking, retrieval evaluation | default | — |
| rails-expert | Rails 7+, Hotwire/Turbo, Action Cable, Sidekiq, Active Record optimization, RSpec | default | — |
| react-expert | React 18+/19, Server Components, Suspense, hooks, TanStack Query, Redux/Zustand | default | — |
| react-native-expert | React Native / Expo, navigation, native modules, FlatList optimization, platform-specific code | default | — |
| regex-vs-llm | Decision framework for regex vs LLM text parsing; hybrid pipeline pattern | default | — |
| researcher | Pre-implementation research: current best practices, library versions, security advisories | fork | general-purpose |
| rust-engineer | Idiomatic Rust, ownership/lifetimes, traits, async tokio, error handling, zero-cost abstractions | default | — |
| salesforce-developer | Apex, Lightning Web Components, SOQL, triggers, batch jobs, platform events, DX CI/CD | default | — |
| scrape-do | Proxy-based web scraping with geo-targeting via Composio Rube MCP | default | — |
| scrapingbee | Headless browser scraping, JS rendering, anti-bot bypass via Composio Rube MCP | default | — |
| secure-code-guardian | OWASP Top 10 prevention: auth, input validation, encryption, JWT, parameterized queries | default | — |
| security-review | Security checklist for auth, user input, secrets, API endpoints, payment features | default | — |
| security-reviewer | Proactive post-edit security scan: semgrep, bandit, manual pattern checks; flags HIGH/CRITICAL | fork | general-purpose |
| security-reviewer-fds | Security audit reports with severity ratings; SAST, DevSecOps, compliance, secrets scanning | default | — |
| security-scan | Scan .claude/ config for vulnerabilities using AgentShield; checks CLAUDE.md, settings, MCP, hooks | default | — |
| shopify-expert | Shopify themes (.liquid), custom apps, Storefront API, Hydrogen, checkout extensions, Polaris | default | — |
| spark-engineer | Apache Spark: PySpark, Spark SQL, DataFrame API, structured streaming, cluster tuning | default | — |
| spec-miner | Reverse-engineer specs from existing codebases; dependency mapping, API doc generation | default | — |
| spring-boot-engineer | Spring Boot 3.x, Spring Security 6, Spring Data JPA, WebFlux, Spring Cloud | default | — |
| sql-pro | SQL optimization, schema design, window functions, CTEs, indexing, EXPLAIN analysis | default | — |
| sre-engineer | SLOs/SLIs, error budgets, incident management, chaos engineering, toil reduction, capacity planning | default | — |
| stormglass-io | Marine/weather/environmental data via Composio Rube MCP | default | — |
| swift-expert | iOS/macOS Swift 5.9+, SwiftUI, async/await, actors, Combine, Vapor | default | — |
| tdd-workflow | Test-driven development enforcement with 80%+ coverage | default | — |
| terraform-engineer | Terraform IaC across AWS/Azure/GCP; modules, state management, multi-environment workflows | default | — |
| test-master | Test generation, mocking strategies, coverage analysis, test architecture across all testing types | default | — |
| test-runner | Proactive test execution after code changes; pytest/unittest/bash; reports pass/fail summary | fork | general-purpose |
| the-fool | Devil's advocate / pre-mortem / red team; structured critical reasoning against plans/decisions | default | — |
| typescript-pro | Advanced TypeScript: generics, conditional/mapped types, branded types, tRPC, type guards | default | — |
| undo | Rollback most recent Claude session work; targeted restore of pre-task state | default | — |
| verification-loop | Post-completion verification system; quality gates before PR/merge | default | — |
| vue-expert | Vue 3 Composition API, Nuxt 3, Pinia, Quasar/Capacitor, PWA, Vite optimization | default | — |
| vue-expert-js | Vue 3 with JavaScript only (no TS); JSDoc-typed, vanilla JS composables | default | — |
| websocket-engineer | WebSocket / Socket.IO real-time systems; Redis scaling, presence tracking, room management | default | — |
| wordpress-pro | WordPress themes/plugins, Gutenberg blocks, WooCommerce, REST API, security hardening | default | — |

---

## Plugin Skills (75+)

Enabled plugins provide additional skills. Grouped by plugin source.

### superpowers (16 active + 3 deprecated)
| Skill | Purpose |
|-------|---------|
| superpowers:using-superpowers | Session start: establishes skill discovery and invocation rules |
| superpowers:brainstorming | Pre-creative-work exploration of intent, requirements, and design |
| superpowers:writing-plans | Multi-step task planning before touching code |
| superpowers:executing-plans | Execute written implementation plans with review checkpoints |
| superpowers:test-driven-development | TDD enforcement before writing implementation code |
| superpowers:systematic-debugging | Structured debugging before proposing fixes |
| superpowers:dispatching-parallel-agents | Parallel independent task execution via subagents |
| superpowers:subagent-driven-development | Execute plans with independent tasks in current session |
| superpowers:requesting-code-review | Post-implementation verification against requirements |
| superpowers:receiving-code-review | Technical rigor when processing code review feedback |
| superpowers:verification-before-completion | Run verification commands before claiming success |
| superpowers:finishing-a-development-branch | Structured options for merge, PR, or cleanup after implementation |
| superpowers:using-git-worktrees | Isolated git worktrees for feature work |
| superpowers:writing-skills | Creating/editing/verifying skills |
| update-config | Configure Claude Code settings.json |
| keybindings-help | Customize keyboard shortcuts in ~/.claude/keybindings.json |

### code-review
| Skill | Purpose |
|-------|---------|
| code-review:code-review | Code review a pull request |

### code-simplifier
| Skill | Purpose |
|-------|---------|
| simplify | Review changed code for reuse, quality, efficiency |

### feature-dev
| Skill | Purpose |
|-------|---------|
| feature-dev:feature-dev | Guided feature development with codebase understanding |

### claude-md-management
| Skill | Purpose |
|-------|---------|
| claude-md-management:revise-claude-md | Update CLAUDE.md with session learnings |
| claude-md-management:claude-md-improver | Audit and improve CLAUDE.md files |

### agent-sdk-dev
| Skill | Purpose |
|-------|---------|
| claude-api | Build apps with Claude API / Anthropic SDK |
| agent-sdk-dev:new-sdk-app | Create new Claude Agent SDK application |

### plugin-dev (8)
| Skill | Purpose |
|-------|---------|
| plugin-dev:create-plugin | End-to-end plugin creation workflow |
| plugin-dev:skill-development | Skill creation, progressive disclosure, skill structure |
| plugin-dev:plugin-structure | Plugin scaffolding, plugin.json, component organization |
| plugin-dev:hook-development | PreToolUse/PostToolUse/Stop hooks, prompt-based hooks |
| plugin-dev:command-development | Slash command creation, frontmatter, file references |
| plugin-dev:agent-development | Subagent creation, frontmatter, tools, colors |
| plugin-dev:mcp-integration | Add MCP server to plugin, .mcp.json config |
| plugin-dev:plugin-settings | Plugin configuration, .local.md, YAML frontmatter |

### hookify (4)
| Skill | Purpose |
|-------|---------|
| hookify:hookify | Create hooks to prevent unwanted behaviors |
| hookify:configure | Enable/disable hookify rules |
| hookify:list | List configured hookify rules |
| hookify:writing-rules | Hookify rule syntax and patterns |

### semgrep (2)
| Skill | Purpose |
|-------|---------|
| semgrep-plugin:setup-semgrep-plugin | Set up Semgrep plugin |
| semgrep-plugin:setup_semgrep_plugin | Alternate setup entry point |

### chrome-devtools-mcp (4)
| Skill | Purpose |
|-------|---------|
| chrome-devtools-mcp:chrome-devtools | Browser debugging and automation via DevTools MCP |
| chrome-devtools-mcp:debug-optimize-lcp | Debug Largest Contentful Paint performance |
| chrome-devtools-mcp:troubleshooting | Troubleshoot DevTools MCP connection issues |
| chrome-devtools-mcp:a11y-debugging | Accessibility debugging and auditing |

### microsoft-docs (3)
| Skill | Purpose |
|-------|---------|
| microsoft-docs:microsoft-docs | Query official Microsoft documentation |
| microsoft-docs:microsoft-code-reference | Find working code samples from Microsoft docs |
| microsoft-docs:microsoft-skill-creator | Create skills for Microsoft technologies |

### mcp-server-dev (3)
| Skill | Purpose |
|-------|---------|
| mcp-server-dev:build-mcp-server | Build MCP server (Node/Python) |
| mcp-server-dev:build-mcpb | Package/bundle MCP server as .mcpb |
| mcp-server-dev:build-mcp-app | Build MCP app with interactive UI/widgets |

### claude-code-setup (1)
| Skill | Purpose |
|-------|---------|
| claude-code-setup:claude-automation-recommender | Analyze codebase, recommend Claude Code automations |

### pai (jeffh-claude-plugins) (6)
| Skill | Purpose |
|-------|---------|
| pai:CORE | PAI system core; auto-loads at session start |
| pai:research | Multi-source parallel research with Fabric patterns |
| pai:story-explanation | Story-format summaries with UltraThink |
| pai:fabric | Native Fabric pattern execution (extract_wisdom, summarize, etc.) |
| pai:prompting | Prompt engineering standards for AI agents |
| pai:create-skill | Create/update/validate Claude Code skills |

### Other plugin skills
| Skill | Purpose |
|-------|---------|
| loop | Run a prompt/command on recurring interval |
| schedule | Create/manage scheduled remote agents (cron triggers) |

### Task Master (tm:*) — 35 skills
| Skill | Purpose |
|-------|---------|
| tm:list-tasks | Show all tasks |
| tm:next-task | Get next available task |
| tm:show-task | View task details |
| tm:add-task | Add new task |
| tm:update-task | Update task |
| tm:update-single-task | Update single task |
| tm:expand-task | Break task into subtasks |
| tm:expand-all-tasks | Expand all tasks |
| tm:add-subtask | Add subtask |
| tm:remove-subtask | Remove subtask |
| tm:remove-subtasks | Remove subtasks |
| tm:remove-all-subtasks | Remove all subtasks |
| tm:remove-task | Remove task |
| tm:add-dependency | Add dependency |
| tm:remove-dependency | Remove dependency |
| tm:validate-dependencies | Validate dependencies |
| tm:fix-dependencies | Fix dependencies |
| tm:analyze-complexity | Analyze complexity |
| tm:complexity-report | Complexity report |
| tm:project-status | Project status |
| tm:parse-prd | Parse PRD |
| tm:parse-prd-with-research | Parse PRD with research |
| tm:auto-implement-tasks | Auto implement tasks |
| tm:smart-workflow | Smart workflow |
| tm:command-pipeline | Command pipeline |
| tm:sync-readme | Sync README |
| tm:init-project | Init project |
| tm:init-project-quick | Init project (quick) |
| tm:install-taskmaster | Install TaskMaster |
| tm:quick-install-taskmaster | Quick install TaskMaster |
| tm:setup-models | Setup models |
| tm:view-models | View models |
| tm:learn | Learn |
| tm:help | Help |
| tm:to-pending / to-in-progress / to-review / to-done / to-deferred / to-cancelled | Status transitions |
| tm:list-tasks-by-status / list-tasks-with-subtasks | Filtered views |
| tm:update-tasks-from-id / update-subtask / convert-task-to-subtask / analyze-project | Advanced operations |

---

## Patchy Bot Skills (10)

Path: `~/Patchy_Bot/.claude-plugin/skills/*/SKILL.md`

| Skill | Purpose |
|-------|---------|
| check-logs | Read/filter recent bot service logs from journalctl |
| db-inspect | Query and summarize SQLite database state (all 11 tables) |
| debug-schedule | Diagnose TV schedule issues: runner status, pending episodes, stuck tracks |
| env-check | Validate .env configuration completeness and consistency |
| gh-issues-auto-fixer | Fetch GitHub issues, route to domain agents, implement fixes, open PRs |
| restart | Restart systemd service and verify healthy startup |
| sync-parity | Audit Movie/TV search feature parity across code paths |
| telegram-chat-polisher | Refine Telegram UI: message text, button labels, keyboard layouts, navigation |
| telegram-ux-architect | Decide interaction placement (bot chat vs Mini App) and structure |
| test-bot | Run full quality suite: pytest + ruff lint + mypy type checking |

---

## MCP Servers (3 direct + plugin-provided)

### Direct (from ~/.mcp.json)

| Server | Transport | Tools | Has API Key | Purpose |
|--------|-----------|-------|-------------|---------|
| playwright | stdio | browser_click, browser_navigate, browser_snapshot, browser_fill_form, browser_take_screenshot, +20 more | No | Headless browser automation and testing |
| chrome-devtools | stdio | click, navigate_page, take_screenshot, evaluate_script, lighthouse_audit, performance traces, +20 more | No | Chrome DevTools Protocol debugging and automation |
| context7 | stdio | resolve-library-id, query-docs | Yes | Fetch current library/framework documentation |

### Plugin-Provided MCP Tools

| Source | Tools | Purpose |
|--------|-------|---------|
| exa (plugin) | web_search_exa, crawling_exa, get_code_context_exa | AI-powered neural web search |
| tavily (plugin) | tavily_search, tavily_crawl, tavily_extract, tavily_map, tavily_research, tavily_skill | Web search, crawling, and extraction |
| task-master (CLI v0.43.1) | get_tasks, get_task, next_task, expand_task, set_task_status, update_subtask, parse_prd | Task tracking and project management |
| microsoft-learn (plugin) | microsoft_docs_search, microsoft_code_sample_search, microsoft_docs_fetch | Official Microsoft documentation |

---

## Hooks — User Level

Path: `~/.claude/settings.json`

| Event | Matcher | Type | Script | Purpose |
|-------|---------|------|--------|---------|
| SessionStart | (all) | command | `session-start.sh` | Verify security tools installed (semgrep, bandit, ruff, shellcheck, trivy) |
| UserPromptSubmit | (all) | command | `mandatory-activation.sh` | Force evaluation of relevant subagents/skills before every prompt |
| PreToolUse | Bash | command | `pre-bash-safety.sh` | Block dangerous commands (rm -rf system dirs, dd, mkfs, chmod 777) |
| PreToolUse | Bash | command | `pre-commit-gate.sh` | Intercept git commit/push; run tests first |
| PostToolUse | Write\|Edit | command | `post-edit-lint.sh` | Auto-format: ruff fix+format (Python), shellcheck (Bash) |
| PostToolUse | Write\|Edit | command | `post-edit-security.sh` | Auto-scan: semgrep + bandit on edited files |
| Stop | (all) | command | `pre-exit.sh` | Warn about uncommitted changes before session end |
| PermissionRequest | (all) | command | `auto-approve.sh` | Auto-approve all permission requests (zero-prompts mode) |

---

## Hooks — Patchy Bot

Path: `~/Patchy_Bot/.claude/settings.json`

| Event | Matcher | Type | Script | Purpose |
|-------|---------|------|--------|---------|
| SubagentStop | (all) | command | (inline) | Auto-run pytest on recently modified .py files after subagent completes |

---

## CLAUDE.md Files

| Path | Purpose |
|------|---------|
| `~/.claude/CLAUDE.md` | Global: response style (explain like 15yo), analysis preferences, code style, decision making |
| `~/.claude/rules/truth-verification.md` | Global rule: never invent facts, quality gate, verification protocol, recovery procedures |
| `~/CLAUDE.md` | Home project: core rules, secrets/safety, before-acting checklist, planning, subagent color rules, sub-agent routing, Task Master workflow, git policy |
| `~/Patchy_Bot/CLAUDE.md` | Patchy Bot: system overview, package map, domain boundaries, state management, coding conventions, testing patterns, safety rules, service operations, subagent-driven development workflow, git write policy |

---

## Settings

Source: `~/.claude/settings.json`

- **Default permission mode:** `bypassPermissions`
- **Advisor model:** `claude-opus-4-6`
- **skipDangerousModePermissionPrompt:** `true`
- **Extra marketplaces:** `jeffh-claude-plugins` (GitHub: `jeffh/claude-plugins`)

### Enabled Plugins (21)

| Plugin | Source |
|--------|--------|
| superpowers | claude-plugins-official |
| context7 | claude-plugins-official |
| code-review | claude-plugins-official |
| code-simplifier | claude-plugins-official |
| feature-dev | claude-plugins-official |
| playwright | claude-plugins-official |
| typescript-lsp | claude-plugins-official |
| claude-md-management | claude-plugins-official |
| security-guidance | claude-plugins-official |
| claude-code-setup | claude-plugins-official |
| pyright-lsp | claude-plugins-official |
| agent-sdk-dev | claude-plugins-official |
| plugin-dev | claude-plugins-official |
| hookify | claude-plugins-official |
| rust-analyzer-lsp | claude-plugins-official |
| chrome-devtools-mcp | claude-plugins-official |
| semgrep | claude-plugins-official |
| microsoft-docs | claude-plugins-official |
| atomic-agents | claude-plugins-official |
| mcp-server-dev | claude-plugins-official |
| pai | jeffh-claude-plugins |

### Disabled Plugins (Notable)
frontend-design, skill-creator, telegram, gopls-lsp, csharp-lsp, jdtls-lsp, php-lsp, huggingface-skills, clangd-lsp, swift-lsp, firecrawl, kotlin-lsp, lua-lsp, ruby-lsp, remember, goodmem, optibot, ai-plugins, elixir-ls-lsp, ui5, figma

### Patchy Bot Project Settings
- **Default permission mode:** `acceptEdits`
- **alwaysThinkingEnabled:** `true`
- **respectGitignore:** `true`
- **Denied reads:** `.env`, `.env.*`, `secrets/**`
- **Allowed Bash:** git read commands, pytest only

---

## Totals Summary

| Category | Count |
|----------|-------|
| User-level agents | 12 |
| Patchy Bot project agents | 9 |
| User skills | 89 |
| Plugin skills | ~75 |
| Patchy Bot skills | 10 |
| MCP servers (direct) | 3 |
| MCP tool sources (plugin) | 4 |
| User hooks | 8 |
| Project hooks | 1 |
| CLAUDE.md files | 4 |
| Enabled plugins | 21 |
