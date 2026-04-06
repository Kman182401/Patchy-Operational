---
name: system-design
description: >
  This skill should be used when the user asks to "design a system", "system design", "how would you architect", "design the backend for", "scalability plan", "high-level design", "HLD", "capacity planning", "load estimation", or describes a feature or product and wants an architecture proposal. Also trigger when discussing how to handle scale for a specific use case. For architecture decision records, prefer the architecture-designer skill instead.
---

# System Design

Framework for designing systems from requirements through architecture.

## Step 1: Requirements Gathering

Clarify before designing. Ask about anything not explicitly stated:

### Functional Requirements
- What are the core use cases?
- Who are the users (internal, external, API consumers)?
- What are the key workflows?

### Non-Functional Requirements
| Dimension | Question |
|-----------|----------|
| **Scale** | How many users? Requests per second? Data volume? |
| **Latency** | What response time is acceptable? P50, P99? |
| **Availability** | What's the uptime target? (99.9% = 8.7h downtime/year) |
| **Consistency** | Strong consistency or eventual consistency acceptable? |
| **Durability** | Can we lose data? What's the recovery point objective? |
| **Budget** | Cost constraints? Build vs. buy preference? |

### Constraints
- Existing tech stack to integrate with
- Team size and expertise
- Timeline and delivery milestones
- Regulatory or compliance requirements

## Step 2: Back-of-Envelope Estimation

Before proposing architecture, estimate the load:

```
Users: [N]
Daily active users: [N x activity rate]
Requests/second: [DAU x actions/day / 86400]
Peak RPS: [Average x peak multiplier (typically 3-10x)]
Storage: [Records x record size x retention period]
Bandwidth: [RPS x average response size]
```

These numbers drive architecture decisions. A system handling 10 RPS and one handling 100K RPS look very different.

## Step 3: High-Level Design

Propose the architecture with:

1. **Component diagram** — Major services, data stores, queues, caches, and how they connect.
2. **Data flow** — How a request moves through the system for each key use case.
3. **Data model** — Key entities, relationships, and storage choices.
4. **API design** — Core endpoints or interfaces between components.

## Step 4: Deep Dive

For each critical component, address:

- **Storage choice** — Why this database? SQL vs NoSQL, read vs write patterns.
- **Caching strategy** — What to cache, invalidation approach, cache-aside vs write-through.
- **Scaling approach** — Horizontal vs vertical, sharding strategy, read replicas.
- **Failure handling** — What happens when this component goes down? Circuit breakers, retries, fallbacks.
- **Data partitioning** — How to shard if needed, partition key selection.

## Step 5: Trade-off Analysis

Every design decision involves trade-offs. Make them explicit:

```
Decision: [What was chosen]
Alternative: [What was rejected]
Trade-off: [What we gain vs. what we give up]
When to revisit: [At what scale or condition does this decision need re-evaluation]
```

## Output

Present the design as a structured document with:
1. Requirements summary
2. Capacity estimation
3. High-level architecture (describe components and connections clearly)
4. Deep dives on critical components
5. Trade-off analysis
6. Open questions and future considerations
