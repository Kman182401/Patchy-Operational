---
name: ocr-web-service-automation
description: This skill should be used when the user asks to "OCR a document", "extract text from image", "read text from screenshot", "convert image to text", "digitize a scanned document", "OCR a PDF", or needs optical character recognition on images, screenshots, or scanned documents. Automates OCR Web Service tasks via Rube MCP (Composio).
metadata:
  author: ComposioHQ
  version: "1.0.0"
  domain: ocr
  triggers: OCR, extract text from image, image to text, read screenshot, digitize document, scan to text, optical character recognition
  role: specialist
  scope: automation
  requires_mcp: rube
---

# OCR Web Service Automation via Rube MCP

Automate optical character recognition tasks through Composio's OCR Web Service toolkit via Rube MCP. Converts images, screenshots, and scanned documents into machine-readable text.

## When to Use This Skill

- Extracting text from images or screenshots
- Digitizing scanned paper documents
- OCR processing of PDF scans (non-searchable PDFs)
- Reading text from photos of documents, signs, or labels
- Batch OCR processing of multiple images

## Prerequisites

- Rube MCP server must be connected (configured in `.mcp.json`)
- OCR Web Service account and active connection via Rube

## Core Workflow

**Always follow this 3-step pattern. Never skip Step 1.**

### Step 1: Discover Available Tools

```
RUBE_SEARCH_TOOLS
  queries: [{"use_case": "extract text from images using OCR", "known_fields": ""}]
  session: {"generate_id": true}
```

Returns available tool slugs, input schemas, execution plans, and known pitfalls.

### Step 2: Verify Connection

```
RUBE_MANAGE_CONNECTIONS
  toolkits: ["ocr_web_service"]
  session_id: "<session_id_from_step_1>"
```

If not `ACTIVE`, follow the authentication link. Confirm active before proceeding.

### Step 3: Execute OCR Tools

Use discovered tool slugs with exact schemas from Step 1:

```
RUBE_MULTI_EXECUTE_TOOL
  tool_slug: "<discovered_ocr_tool>"
  inputs: [
    {"image_url": "https://example.com/scan1.png"},
    {"image_url": "https://example.com/scan2.jpg"}
  ]
  session_id: "<session_id>"
```

## Key Capabilities

| Feature | Description |
|---------|-------------|
| Image OCR | Extract text from PNG, JPG, TIFF, BMP images |
| PDF OCR | Extract text from scanned/non-searchable PDFs |
| Multi-Language | Supports multiple languages and scripts |
| Table Detection | Recognize and extract tabular data |
| Handwriting | Basic handwritten text recognition |

## When to Use OCR vs Extracta AI

| Scenario | Use OCR | Use Extracta AI |
|----------|---------|-----------------|
| Raw text extraction from image | Yes | Overkill |
| Structured field extraction from invoice | No | Yes |
| Screenshot text capture | Yes | No |
| Parse PDF into named fields | No | Yes |
| Digitize a scanned book page | Yes | No |
| Extract line items from receipt | Maybe | Yes |

Use OCR for raw text extraction. Use Extracta AI when you need structured fields (key-value pairs, tables, named data).

## Important Rules

- **Always search tools first** - schemas update frequently
- **Check connection before execution** - inactive connections fail silently
- **Use batch execution** for multiple images via `RUBE_MULTI_EXECUTE_TOOL`
- **For high-volume jobs** (100+ images), use `RUBE_REMOTE_WORKBENCH`

## Additional Resources

- Toolkit docs: `composio.dev/toolkits/ocr_web_service`
- **`references/usage-patterns.md`** - OCR optimization and preprocessing tips
