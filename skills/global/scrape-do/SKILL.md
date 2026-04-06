---
name: scrape-do-automation
description: This skill should be used when the user asks to "scrape with proxy rotation", "anonymous web scraping", "geo-targeted scraping", "scrape from different countries", "residential proxy scraping", or needs proxy-based web scraping with geographic targeting. Automates Scrape.do tasks via Rube MCP (Composio).
metadata:
  author: ComposioHQ
  version: "1.0.0"
  domain: web-scraping
  triggers: proxy scraping, geo-targeted scrape, residential proxy, anonymous scraping, country-specific scraping, IP rotation, scrape.do
  role: specialist
  scope: automation
  requires_mcp: rube
---

# Scrape.do Automation via Rube MCP

Automate proxy-based web scraping through Composio's Scrape.do toolkit via Rube MCP. Specializes in geo-targeted scraping with residential proxy rotation and anti-detection.

## When to Use This Skill

- Scraping that requires proxy rotation or residential IPs
- Geo-targeted scraping (viewing content as seen from specific countries)
- Anonymous scraping without revealing origin IP
- Accessing region-locked web content
- High-volume scraping with rate limit management

## Prerequisites

- Rube MCP server must be connected (configured in `.mcp.json`)
- Scrape.do account and active connection via Rube

## Core Workflow

**Always follow this 3-step pattern. Never skip Step 1.**

### Step 1: Discover Available Tools

```
RUBE_SEARCH_TOOLS
  queries: [{"use_case": "scrape web pages using Scrape.do with proxy rotation", "known_fields": ""}]
  session: {"generate_id": true}
```

Returns available tool slugs, input schemas, execution plans, and known pitfalls.

### Step 2: Verify Connection

```
RUBE_MANAGE_CONNECTIONS
  toolkits: ["scrape_do"]
  session_id: "<session_id_from_step_1>"
```

If not `ACTIVE`, follow the authentication link. Confirm active before proceeding.

### Step 3: Execute Scraping Tools

Use discovered tool slugs with exact schemas from Step 1:

```
RUBE_MULTI_EXECUTE_TOOL
  tool_slug: "<discovered_tool_slug>"
  inputs: [
    {"url": "https://example.com/page1", "country": "us"},
    {"url": "https://example.com/page2", "country": "de"}
  ]
  session_id: "<session_id>"
```

## Key Capabilities

| Feature | Description |
|---------|-------------|
| Proxy Rotation | Automatic IP rotation across requests |
| Geo-Targeting | View pages as seen from specific countries |
| Residential Proxies | Use real residential IPs for stealth |
| JS Rendering | Render JavaScript-heavy pages |
| Anti-Detection | Bypass fingerprinting and bot detection |

## ScrapingBee vs Scrape.do

| Feature | ScrapingBee | Scrape.do |
|---------|-------------|-----------|
| JS Rendering | Yes | Yes |
| Proxy Rotation | Yes | Yes (focus) |
| Geo-Targeting | Basic | Advanced |
| Residential IPs | Add-on | Built-in |
| Best For | General scraping | Proxy-heavy needs |

Use ScrapingBee for general-purpose scraping. Use Scrape.do when proxy rotation, geo-targeting, or residential IPs are the priority.

## Important Rules

- **Always search tools first** - schemas update frequently
- **Check connection before execution** - inactive connections fail silently
- **Use batch execution** for multiple URLs via `RUBE_MULTI_EXECUTE_TOOL`
- **For high-volume jobs** (100+ URLs), use `RUBE_REMOTE_WORKBENCH`

## Additional Resources

- Toolkit docs: `composio.dev/toolkits/scrape_do`
- **`references/usage-patterns.md`** - Proxy strategies and geo-targeting patterns
