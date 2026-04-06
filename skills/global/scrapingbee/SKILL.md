---
name: scrapingbee-automation
description: This skill should be used when the user asks to "scrape a website", "extract web page content", "render JavaScript pages", "bypass anti-scraping", "get HTML from a URL", "headless browser scraping", or needs to fetch web content that requires JavaScript rendering or anti-bot bypass. Automates ScrapingBee tasks via Rube MCP (Composio).
metadata:
  author: ComposioHQ
  version: "1.0.0"
  domain: web-scraping
  triggers: scrape website, extract web page, headless browser, bypass anti-scraping, render JavaScript, get HTML, web data extraction
  role: specialist
  scope: automation
  requires_mcp: rube
---

# ScrapingBee Automation via Rube MCP

Automate web scraping tasks using ScrapingBee's headless browser rendering through Composio's Rube MCP. Handles JavaScript-heavy sites, anti-scraping bypasses, and structured web data extraction.

## When to Use This Skill

- Scraping websites that require JavaScript rendering
- Bypassing anti-scraping protections (CAPTCHAs, bot detection)
- Extracting structured data from web pages at scale
- Getting clean HTML/text from dynamic web applications
- Screenshot capture of rendered pages

## Prerequisites

- Rube MCP server must be connected (configured in `.mcp.json`)
- ScrapingBee account and active connection via Rube

## Core Workflow

**Always follow this 3-step pattern. Never skip Step 1.**

### Step 1: Discover Available Tools

Always call `RUBE_SEARCH_TOOLS` first. Tool schemas update frequently - never assume parameter names.

```
RUBE_SEARCH_TOOLS
  queries: [{"use_case": "scrape web page and extract content", "known_fields": ""}]
  session: {"generate_id": true}
```

This returns: available tool slugs, input schemas, recommended execution plans, and known pitfalls.

### Step 2: Verify Connection

```
RUBE_MANAGE_CONNECTIONS
  toolkits: ["scrapingbee"]
  session_id: "<session_id_from_step_1>"
```

If connection status is not `ACTIVE`, follow the returned authentication link. Confirm `ACTIVE` status before proceeding.

### Step 3: Execute Scraping Tools

Use the discovered tool slugs with the exact schemas returned in Step 1. For multiple URLs:

```
RUBE_MULTI_EXECUTE_TOOL
  tool_slug: "<discovered_tool_slug>"
  inputs: [
    {"url": "https://example.com/page1"},
    {"url": "https://example.com/page2"}
  ]
  session_id: "<session_id>"
```

## Key Capabilities

| Feature | Description |
|---------|-------------|
| JS Rendering | Full headless Chrome rendering for SPAs and dynamic content |
| Anti-Bot Bypass | Handles CAPTCHAs, rate limiting, IP rotation |
| Proxy Rotation | Automatic proxy management across geolocations |
| Screenshots | Capture rendered page screenshots |
| Structured Extract | Return clean text, HTML, or JSON from pages |

## Important Rules

- **Always search tools first** - schemas change; hardcoded parameters will break
- **Check connection before execution** - an inactive connection causes silent failures
- **Use batch execution** for multiple URLs via `RUBE_MULTI_EXECUTE_TOOL`
- **For high-volume jobs** (100+ URLs), use `RUBE_REMOTE_WORKBENCH` instead

## Additional Resources

- Toolkit docs: `composio.dev/toolkits/scrapingbee`
- **`references/usage-patterns.md`** - Common scraping patterns and error handling
