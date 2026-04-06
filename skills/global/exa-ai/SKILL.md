---
name: exa-ai-automation
description: This skill should be used when the user asks to "search the web with AI", "neural web search", "find similar pages", "semantic search", "research a topic online", "find content about", or needs AI-powered web search beyond traditional keyword matching. Automates Exa AI tasks via Rube MCP (Composio).
metadata:
  author: ComposioHQ
  version: "1.0.0"
  domain: web-search
  triggers: AI web search, neural search, semantic search, find similar pages, research topic, web intelligence, content discovery
  role: specialist
  scope: automation
  requires_mcp: rube
---

# Exa AI Search Automation via Rube MCP

Automate AI-powered web search and neural data retrieval through Composio's Exa toolkit via Rube MCP. Exa uses neural/semantic search to find content by meaning, not just keywords.

## When to Use This Skill

- Semantic web search (finding pages by meaning, not exact keywords)
- Finding similar pages to a given URL
- Research and content discovery on specific topics
- Retrieving clean text content from search results
- Building datasets from web search results

## Prerequisites

- Rube MCP server must be connected (configured in `.mcp.json`)
- Exa account and active connection via Rube

## Core Workflow

**Always follow this 3-step pattern. Never skip Step 1.**

### Step 1: Discover Available Tools

```
RUBE_SEARCH_TOOLS
  queries: [{"use_case": "search the web using Exa AI", "known_fields": ""}]
  session: {"generate_id": true}
```

Returns available tool slugs, input schemas, execution plans, and known pitfalls.

### Step 2: Verify Connection

```
RUBE_MANAGE_CONNECTIONS
  toolkits: ["exa"]
  session_id: "<session_id_from_step_1>"
```

If not `ACTIVE`, follow the authentication link. Confirm active status before proceeding.

### Step 3: Execute Search Tools

Use discovered tool slugs with exact schemas from Step 1:

```
RUBE_MULTI_EXECUTE_TOOL
  tool_slug: "<discovered_search_tool>"
  inputs: [
    {"query": "latest advances in quantum computing 2026"},
    {"query": "open source LLM benchmarks comparison"}
  ]
  session_id: "<session_id>"
```

## Key Capabilities

| Feature | Description |
|---------|-------------|
| Neural Search | Find content by meaning, not just keywords |
| Similar Pages | Find pages similar to a given URL |
| Content Retrieval | Get clean text/markdown from results |
| Date Filtering | Filter results by publication date |
| Domain Filtering | Restrict search to specific domains |

## When to Use Exa vs Regular Web Search

| Scenario | Use Exa | Use Regular Search |
|----------|---------|-------------------|
| Find conceptually similar content | Yes | No |
| Exact keyword lookup | No | Yes |
| Research a broad topic with nuance | Yes | Maybe |
| Find a specific URL or page | No | Yes |
| Build a dataset of related pages | Yes | No |

## Important Rules

- **Always search tools first** - schemas update frequently
- **Check connection before execution** - inactive connections cause failures
- **Use batch execution** for multiple queries via `RUBE_MULTI_EXECUTE_TOOL`
- Note: This is the Composio/Rube integration with Exa. The standalone Exa MCP may also be available.

## Additional Resources

- Toolkit docs: `composio.dev/toolkits/exa`
- **`references/usage-patterns.md`** - Search strategies and result processing
