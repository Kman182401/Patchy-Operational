---
name: stormglass-io-automation
description: This skill should be used when the user asks to "get weather data", "ocean conditions", "tide information", "marine forecast", "wave height data", "sea temperature", "wind speed at coordinates", or needs marine/weather/environmental data for specific locations. Automates Stormglass IO tasks via Rube MCP (Composio).
metadata:
  author: ComposioHQ
  version: "1.0.0"
  domain: weather-data
  triggers: weather data, ocean conditions, tide data, marine forecast, wave height, sea temperature, wind data, environmental data, stormglass
  role: specialist
  scope: automation
  requires_mcp: rube
---

# Stormglass IO Automation via Rube MCP

Automate marine weather, tide, and environmental data retrieval through Composio's Stormglass IO toolkit via Rube MCP. Access high-resolution ocean and weather data by coordinates.

## When to Use This Skill

- Retrieving weather data for specific GPS coordinates
- Getting tide predictions and astronomical data
- Fetching wave height, period, and direction data
- Querying sea surface temperature and salinity
- Building weather/marine data pipelines for multiple locations

## Prerequisites

- Rube MCP server must be connected (configured in `.mcp.json`)
- Stormglass IO account and active connection via Rube

## Core Workflow

**Always follow this 3-step pattern. Never skip Step 1.**

### Step 1: Discover Available Tools

```
RUBE_SEARCH_TOOLS
  queries: [{"use_case": "get marine weather and tide data from Stormglass", "known_fields": ""}]
  session: {"generate_id": true}
```

Returns available tool slugs, input schemas, execution plans, and known pitfalls.

### Step 2: Verify Connection

```
RUBE_MANAGE_CONNECTIONS
  toolkits: ["stormglass_io"]
  session_id: "<session_id_from_step_1>"
```

If not `ACTIVE`, follow the authentication link. Confirm active before proceeding.

### Step 3: Execute Weather Tools

Use discovered tool slugs with exact schemas from Step 1. For multiple locations:

```
RUBE_MULTI_EXECUTE_TOOL
  tool_slug: "<discovered_weather_tool>"
  inputs: [
    {"lat": 36.9741, "lng": -122.0308},
    {"lat": 21.3069, "lng": -157.8583}
  ]
  session_id: "<session_id>"
```

## Key Capabilities

| Feature | Description |
|---------|-------------|
| Weather Forecast | Air temp, wind, pressure, humidity, cloud cover |
| Wave Data | Height, period, direction for swell and wind waves |
| Tide Predictions | High/low tides, astronomical tides, sea level |
| Ocean Data | Water temp, salinity, currents |
| Multi-Source | Aggregates data from NOAA, SMHI, DWD, and others |

## Common Parameters

| Parameter | Example | Description |
|-----------|---------|-------------|
| `lat` | `36.9741` | Latitude (decimal degrees) |
| `lng` | `-122.0308` | Longitude (decimal degrees) |
| `start` | `2026-04-04` | Start date (ISO 8601) |
| `end` | `2026-04-07` | End date (ISO 8601) |

## Important Rules

- **Always search tools first** - schemas change; never hardcode parameters
- **Check connection before execution** - inactive connections fail silently
- **Use batch execution** for multiple locations via `RUBE_MULTI_EXECUTE_TOOL`
- Stormglass free tier has daily API call limits - be mindful of batch sizes

## Additional Resources

- Toolkit docs: `composio.dev/toolkits/stormglass_io`
- **`references/usage-patterns.md`** - Data parameters and multi-location query patterns
