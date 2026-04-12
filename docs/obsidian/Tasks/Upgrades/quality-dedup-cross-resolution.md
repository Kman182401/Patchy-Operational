---
tags: [upgrade, priority-low, open]
created: 2026-04-11
module: patchy_bot/quality.py
related: []
---

# Upgrade: Quality-based deduplication and cross-resolution comparison

## Problem / What
Three deferred design decisions documented in `quality.py` (lines 384-397):

1. **Quality-based deduplication** — content identity matching (same movie, different encode) to reduce duplicate results
2. **Cross-resolution comparison** — subjective trade-offs like 720p remux vs 1080p WEB-DL are user-specific
3. **Re-scoring old DB results** — old searches expire naturally (24h TTL); re-scoring on algorithm changes adds complexity

## Expected Behavior / Why
These were intentionally deferred because:
- Content identity matching is complex and error-prone
- Resolution-first ordering is predictable and expected by users
- TTL-based expiry makes re-scoring unnecessary

They remain documented in case priorities change.

## Context
- Affects: `quality.py` scoring engine, search result display
- Root cause: design trade-offs, not bugs
- Related: [[Architecture/modules|Module Map]]

## Claude Code Notes
Do not implement unless explicitly requested. If implementing #1, ensure it doesn't break the existing resolution-tier-first ordering. Run `pytest -q` and verify search result rankings are preserved.
