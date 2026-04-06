---
name: regex-vs-llm
description: This skill should be used when the user asks to "parse structured text", "extract data from text", "scrape content", "regex vs LLM", "build a text parser", "parse quizzes or forms", "extract fields from documents", or needs to decide between regex and LLM approaches for text extraction. Provides a decision framework and hybrid pipeline pattern for structured text parsing.
license: MIT
metadata:
  author: affaan-m
  version: "1.0.0"
  domain: data-processing
  triggers: text parsing, regex, LLM extraction, structured text, data extraction, scraping, hybrid pipeline, confidence scoring
  role: specialist
  scope: implementation
  output-format: code
---

# Structured Text Parsing Framework (Regex vs LLM)

Decision framework for choosing between regex and LLMs when parsing structured text. Start with regex, add LLMs only for low-confidence edge cases.

## When to Use This Skill

- Parsing structured text with repeating patterns (quizzes, forms, tables, logs)
- Deciding whether to use regex or LLM for text extraction
- Building hybrid pipelines combining both approaches
- Optimizing cost/accuracy tradeoffs in text processing
- Extracting fields from semi-structured documents

## Core Principle

Regular expressions handle 95-98% of standard cases. Reserve LLMs for items failing confidence checks. This reduces API costs by approximately 95%.

## Decision Tree

```
Is text format consistent and repetitive?
+-- Yes (>90% follows a pattern) --> Start with regex
|   +-- Regex handles 95%+ --> Done, no LLM needed
|   +-- Regex handles <95% --> Add LLM only for edge cases
+-- No (freeform, highly variable) --> Use LLM directly
```

## Hybrid Pipeline Architecture

```
Input Text
    |
    v
[Regex Parser] --> extracts structure (95-98% accuracy)
    |
    v
[Text Cleaner] --> removes noise (markup, page numbers, artifacts)
    |
    v
[Confidence Scorer] --> flags low-confidence extractions
    |
    +---> confidence >= 0.95 --> Direct Output (no LLM needed)
    |
    +---> confidence < 0.95  --> [LLM Validator] --> Corrected Output
```

## Implementation Pattern

### Step 1: Define the Data Structure

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ParsedItem:
    """Represents a single extracted item with confidence metadata."""
    raw_text: str
    fields: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    needs_llm_review: bool = False

    def score_confidence(self, criteria: dict[str, any]) -> float:
        """Score extraction quality against expected criteria.

        Args:
            criteria: Expected properties, e.g.:
                {"min_length": 10, "required_fields": ["title", "body"]}
        """
        score = 1.0

        required = criteria.get("required_fields", [])
        for f in required:
            if f not in self.fields or not self.fields[f].strip():
                score -= 0.3

        min_len = criteria.get("min_length", 0)
        for value in self.fields.values():
            if len(value.strip()) < min_len:
                score -= 0.1

        self.confidence = max(0.0, min(1.0, score))
        self.needs_llm_review = self.confidence < 0.95
        return self.confidence
```

### Step 2: Build the Regex Parser

Write regex patterns targeting the repeating structure. Test against representative samples before adding complexity.

```python
import re

def parse_items(text: str, pattern: str) -> list[ParsedItem]:
    """Extract items using a compiled regex pattern.

    Args:
        text: Raw input text.
        pattern: Regex with named groups matching fields.
    """
    compiled = re.compile(pattern, re.DOTALL | re.MULTILINE)
    items = []
    for match in compiled.finditer(text):
        item = ParsedItem(
            raw_text=match.group(0),
            fields=match.groupdict(),
        )
        items.append(item)
    return items
```

### Step 3: Add Confidence Scoring and Route

```python
CONFIDENCE_THRESHOLD = 0.95

def route_items(
    items: list[ParsedItem],
    criteria: dict[str, any],
) -> tuple[list[ParsedItem], list[ParsedItem]]:
    """Split items into high-confidence and needs-review buckets."""
    high_conf, needs_review = [], []
    for item in items:
        item.score_confidence(criteria)
        if item.needs_llm_review:
            needs_review.append(item)
        else:
            high_conf.append(item)
    return high_conf, needs_review
```

### Step 4: LLM Validation (Only for Low-Confidence Items)

Send only the flagged items to an LLM. Use a cost-effective model (Claude Haiku is ideal for validation tasks where the goal is fixing minor formatting or extraction errors).

```python
def build_llm_prompt(item: ParsedItem, expected_fields: list[str]) -> str:
    """Build a focused prompt for LLM to fix a single extraction."""
    return f"""Fix this text extraction. Return only the corrected JSON.

Raw text:
{item.raw_text}

Current extraction (may have errors):
{item.fields}

Expected fields: {expected_fields}

Return valid JSON with the corrected fields."""
```

## When to Skip Regex Entirely

- Text has no repeating structure
- Format changes between every item
- Natural language with no delimiters or markers
- Content requires semantic understanding (sentiment, intent, summarization)

In these cases, go straight to LLM extraction.

## Cost Optimization Summary

| Approach | Cost | Accuracy | Speed |
|----------|------|----------|-------|
| Regex only | Free | 95-98% on structured | Fast |
| LLM only | High | 99%+ | Slow |
| Hybrid (recommended) | ~5% of LLM-only | 99%+ | Fast for most items |

## Additional Resources

### Reference Files

For detailed regex patterns, advanced pipeline configurations, and real-world examples:
- **`references/patterns.md`** - Common regex patterns for structured text, cleaning utilities, and end-to-end pipeline examples
