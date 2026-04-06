---
name: extracta-ai-automation
description: This skill should be used when the user asks to "extract data from documents", "parse PDFs with AI", "extract fields from invoices", "structured data extraction", "pull data from receipts", "AI document parsing", or needs to extract structured data from unstructured documents (PDFs, images, forms). Automates Extracta AI tasks via Rube MCP (Composio).
metadata:
  author: ComposioHQ
  version: "1.0.0"
  domain: data-extraction
  triggers: extract from documents, parse PDF, AI extraction, invoice parsing, receipt data, form extraction, document intelligence, structured extraction
  role: specialist
  scope: automation
  requires_mcp: rube
---

# Extracta AI Automation via Rube MCP

Automate structured data extraction from unstructured documents using Extracta AI through Composio's Rube MCP. Extracts fields from PDFs, images, invoices, receipts, and forms.

## When to Use This Skill

- Extracting structured fields from PDFs or scanned documents
- Parsing invoices, receipts, or forms into structured data
- Converting unstructured document content to JSON
- Bulk document processing pipelines
- AI-powered data extraction where templates vary

## Prerequisites

- Rube MCP server must be connected (configured in `.mcp.json`)
- Extracta AI account and active connection via Rube

## Core Workflow

**Always follow this 3-step pattern. Never skip Step 1.**

### Step 1: Discover Available Tools

```
RUBE_SEARCH_TOOLS
  queries: [{"use_case": "extract structured data from documents using Extracta AI", "known_fields": ""}]
  session: {"generate_id": true}
```

Returns available tool slugs, input schemas, execution plans, and known pitfalls.

### Step 2: Verify Connection

```
RUBE_MANAGE_CONNECTIONS
  toolkits: ["extracta_ai"]
  session_id: "<session_id_from_step_1>"
```

If not `ACTIVE`, follow the returned authentication link. Confirm active before proceeding.

### Step 3: Execute Extraction Tools

Use discovered tool slugs with exact schemas from Step 1:

```
RUBE_MULTI_EXECUTE_TOOL
  tool_slug: "<discovered_extraction_tool>"
  inputs: [
    {"document_url": "https://example.com/invoice.pdf", "fields": ["total", "date", "vendor"]},
    {"document_url": "https://example.com/receipt.pdf", "fields": ["amount", "items"]}
  ]
  session_id: "<session_id>"
```

## Key Capabilities

| Feature | Description |
|---------|-------------|
| PDF Extraction | Parse text and tables from PDF documents |
| Image/Scan OCR | Extract text from scanned documents and images |
| Field Extraction | Pull specific named fields into structured JSON |
| Template-Free | AI-driven extraction without predefined templates |
| Batch Processing | Process multiple documents in a single call |

## Common Use Cases

- **Invoices**: Extract vendor, date, line items, totals, tax
- **Receipts**: Extract merchant, date, items, amounts
- **Forms**: Extract field labels and values from filled forms
- **Contracts**: Extract parties, dates, terms, clauses
- **Reports**: Extract tables, figures, key metrics

## Important Rules

- **Always search tools first** - schemas change; never hardcode parameters
- **Check connection before execution** - inactive connections fail silently
- **Use batch execution** for multiple documents via `RUBE_MULTI_EXECUTE_TOOL`
- **For high-volume jobs** (100+ documents), use `RUBE_REMOTE_WORKBENCH`

## Additional Resources

- Toolkit docs: `composio.dev/toolkits/extracta_ai`
- **`references/usage-patterns.md`** - Extraction patterns and field mapping strategies
