# Skill Phase Map — Complete Reference

Skills organized by when to activate them during task execution. Use this reference when the quick tables in SKILL.md are insufficient.

## Phase 1: Intake Skills

These skills help understand and classify the task before any work begins.

### Research & Discovery
| Skill | Trigger |
|-------|---------|
| `researcher` | Unfamiliar library, framework, API, or technology |
| `pai:research` | Deep multi-source research needed |
| `exa-ai` | AI-powered semantic web search |
| `spec-miner` | Legacy or undocumented codebase, reverse-engineering needed |
| `expert-analysis` | Deep evidence-first investigation needed |

### Context & Documentation Lookup
| Tool/Skill | Trigger |
|------------|---------|
| `context7` MCP | Any library, framework, SDK, or API question |
| `microsoft-docs` plugin | Any Microsoft/Azure technology |
| `atlassian-mcp` | Jira or Confluence integration |

### Bug/Error Classification
| Skill | Trigger |
|-------|---------|
| `debugger` | ANY error, failure, bug, or unexpected behavior (MANDATORY) |
| `debugging-wizard` | Same — always pair with `debugger` (MANDATORY) |
| `superpowers:systematic-debugging` | Structured debugging methodology |

### Creative/New Work
| Skill | Trigger |
|-------|---------|
| `superpowers:brainstorming` | ANY creative work — new features, components, functionality |
| `the-fool` | Challenge existing plans, play devil's advocate |

## Phase 2: Planning Skills

These skills structure the approach before touching code.

### Planning & Architecture
| Skill | Trigger |
|-------|---------|
| `plan-builder` | Any non-trivial multi-step task |
| `superpowers:writing-plans` | Spec or requirements exist for multi-step work |
| `system-design` | "Design a system", "how would you architect" |
| `architecture-designer` | High-level system architecture, ADRs |
| `microservices-architect` | Distributed systems, service decomposition |
| `feature-forge` | Feature requirements gathering, user stories |

### Strategy & Assessment
| Skill | Trigger |
|-------|---------|
| `testing-strategy` | "What should I test", test plan needed |
| `tech-debt` | "Technical debt audit", "what to refactor" |
| `deploy-checklist` | Deployment planning, pre-release review |
| `legacy-modernizer` | Migrating old systems, strangler fig pattern |

## Phase 3: Execution Skills — By Domain

### Python Ecosystem
| Skill | Trigger |
|-------|---------|
| `python-pro` | Any Python 3.11+ code |
| `fastapi-expert` | FastAPI endpoints, Pydantic V2 |
| `django-expert` | Django models, views, DRF |
| `pandas-pro` | DataFrame operations, data analysis |

### JavaScript/TypeScript Ecosystem
| Skill | Trigger |
|-------|---------|
| `javascript-pro` | Vanilla JS, ES2023+, Node.js |
| `typescript-pro` | TypeScript type systems, tRPC |
| `react-expert` | React 18+, Next.js App Router |
| `nextjs-developer` | Next.js 14+ specific features |
| `vue-expert` / `vue-expert-js` | Vue 3, Nuxt 3 |
| `angular-architect` | Angular 17+ standalone |
| `nestjs-expert` | NestJS backend |
| `react-native-expert` | React Native / Expo mobile |

### Systems Languages
| Skill | Trigger |
|-------|---------|
| `rust-engineer` | Rust, ownership, tokio |
| `golang-pro` | Go, goroutines, gRPC |
| `cpp-pro` | C++20/23, templates, SIMD |
| `java-architect` | Java, Spring Boot 3.x |
| `csharp-developer` | C#, .NET 8+, ASP.NET Core |
| `kotlin-specialist` | Kotlin, coroutines, Compose |
| `swift-expert` | iOS/macOS, SwiftUI |

### Web Frameworks
| Skill | Trigger |
|-------|---------|
| `rails-expert` | Rails 7+, Turbo, Hotwire |
| `laravel-specialist` | Laravel 10+, Eloquent |
| `spring-boot-engineer` | Spring Boot 3.x, WebFlux |
| `dotnet-core-expert` | .NET 8, minimal APIs |
| `php-pro` | PHP 8.3+, Symfony |
| `wordpress-pro` | WordPress themes/plugins |
| `shopify-expert` | Shopify themes, Liquid |
| `flutter-expert` | Flutter 3+, Dart |

### Infrastructure & DevOps
| Skill | Trigger |
|-------|---------|
| `devops-engineer` | CI/CD, Dockerfiles, Kubernetes manifests |
| `kubernetes-specialist` | K8s workloads, pods, services |
| `terraform-engineer` | Terraform IaC, state management |
| `cloud-architect` | AWS/Azure/GCP architecture |
| `monitoring-expert` | Prometheus/Grafana, logging, alerting |
| `sre-engineer` | SLOs, error budgets, capacity |
| `embedded-systems` | Firmware, RTOS, STM32, ESP32 |

### Data & APIs
| Skill | Trigger |
|-------|---------|
| `api-designer` | REST/GraphQL API design |
| `graphql-architect` | GraphQL schemas, Apollo Federation |
| `database-optimizer` | Query optimization, PostgreSQL/MySQL |
| `postgres-pro` | PostgreSQL specific |
| `sql-pro` | SQL queries, schema design |
| `websocket-engineer` | Real-time communication |

### Security (Execution)
| Skill | Trigger |
|-------|---------|
| `security-review` | Auth, user input, secrets, API endpoints |
| `security-reviewer` | Post-edit security check |
| `secure-code-guardian` | OWASP Top 10 prevention |
| `fullstack-guardian` | Full-stack security implementation |
| `security-scan` | Claude Code config security |

### AI/ML
| Skill | Trigger |
|-------|---------|
| `ml-pipeline` | ML pipeline infrastructure |
| `rag-architect` | RAG systems, embeddings, vector stores |
| `fine-tuning-expert` | LLM fine-tuning, LoRA/QLoRA |
| `prompt-engineer` | Prompt design, evaluation |

### Testing (Execution)
| Skill | Trigger |
|-------|---------|
| `tdd-workflow` | Test-driven development |
| `superpowers:test-driven-development` | TDD methodology |
| `test-master` | Test file generation, mocking |
| `playwright-expert` | E2E browser tests |
| `chaos-engineer` | Chaos experiments, failure injection |

### Content & Processing
| Skill | Trigger |
|-------|---------|
| `scrapingbee` | Web scraping with JS rendering |
| `scrape-do` | Proxy-based scraping |
| `ocr-web-service` | Text extraction from images |
| `extracta-ai` | Structured data from documents |
| `regex-vs-llm` | Text parsing decisions |
| `pai:fabric` | Content processing with Fabric patterns |

### CLI & Tools
| Skill | Trigger |
|-------|---------|
| `cli-developer` | CLI tools, argument parsing |
| `mcp-developer` | MCP servers/clients |
| `game-developer` | Game systems, Unity/Unreal |
| `spark-engineer` | Apache Spark, big data |

### Platform Skills
| Skill | Trigger |
|-------|---------|
| `salesforce-developer` | Salesforce, Apex, LWC |
| `stormglass-io` | Marine/weather data |

## Phase 4: Verification Skills

### Testing
| Skill | Trigger |
|-------|---------|
| `test-runner` | ALWAYS after code changes (MANDATORY) |
| `linter` | ALWAYS after file edits (MANDATORY) |
| `verification-loop` | Comprehensive verification system |
| `superpowers:verification-before-completion` | Before claiming work is done |

### Review
| Skill | Trigger |
|-------|---------|
| `analyze` | Deep post-completion review (PROACTIVE) |
| `code-reviewer` | Code diff analysis |
| `audit` | Full professional audit |
| `security-reviewer` | Security-focused review |
| `security-reviewer-fds` | Structured security audit report |

### Quality
| Skill | Trigger |
|-------|---------|
| `eval-harness` | Formal evaluation framework |
| `simplify` | Review changed code for reuse/quality |

## Phase 5: Completion Skills

### Integration
| Skill | Trigger |
|-------|---------|
| `superpowers:requesting-code-review` | Before merging |
| `superpowers:receiving-code-review` | Processing review feedback |
| `superpowers:finishing-a-development-branch` | Branch ready to merge |
| `superpowers:using-git-worktrees` | Feature work needing isolation |

### Documentation & Reporting
| Skill | Trigger |
|-------|---------|
| `documentation` | README, runbook, onboarding guide |
| `code-documenter` | Docstrings, OpenAPI specs |
| `standup` | Daily status update |
| `incident-response` | Postmortem, RCA |

### Project Management
| Skill | Trigger |
|-------|---------|
| `plan-implementation` | Execute an approved plan |
| `superpowers:executing-plans` | Execute plan with review checkpoints |
| `superpowers:subagent-driven-development` | Parallel independent tasks |
| `superpowers:dispatching-parallel-agents` | 2+ independent tasks |

### Meta/Tooling
| Skill | Trigger |
|-------|---------|
| `superpowers:writing-skills` | Creating new skills |
| `claude-api` | Claude API / Anthropic SDK code |
| `project-builder` | Claude.ai project setup |
| `claude-md-management:revise-claude-md` | Update CLAUDE.md |
| `claude-md-management:claude-md-improver` | Audit CLAUDE.md files |
| `claude-code-setup:claude-automation-recommender` | Optimize Claude Code setup |

## Common Skill Combinations

### Python Feature Development
1. `superpowers:brainstorming` → `plan-builder` → `python-pro` skill + `python-pro` agent → `tdd-workflow` → `test-runner` → `linter` → `security-auditor` agent → `analyze`

### FastAPI Endpoint
1. `context7` (FastAPI docs) → `fastapi-expert` skill + `fastapi-developer` agent → `security-review` → `test-runner` → `linter` → `security-auditor` agent → `analyze`

### Bug Fix
1. `debugger` + `debugging-wizard` → `error-detective` agent → domain skill + domain agent → `test-runner` → `linter` → `analyze`

### Infrastructure Change
1. `devops-engineer` + `docker-expert` agent → `security-review` → `security-auditor` agent → `deploy-checklist`

### Security Implementation
1. `secure-code-guardian` + `security-engineer` agent → `security-auditor` agent → `penetration-tester` agent (if offensive testing authorized)
