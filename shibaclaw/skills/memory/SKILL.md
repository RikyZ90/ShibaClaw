---
name: memory
description: Split memory system with USER.md for durable personal profile and MEMORY.md for token-budgeted operational context.
always: true
---

# Memory

## Structure

- `USER.md` — Durable personal profile and preferences. Not token-compacted; keep it focused on long-lived user facts.
- `memory/MEMORY.md` — Operational long-term facts. Injected into every system prompt under `# Memory`, **truncated from the bottom** if it exceeds the token budget (~2000 tokens default).
- `memory/HISTORY.md` — Append-only log with `[YYYY-MM-DD HH:MM] [#tag1 #tag2]` entries. Never injected. Search it with `memory_search` or grep when historical context is missing.

## MEMORY.md Layout

Sections are ordered by **survival priority** — top sections persist under truncation, bottom sections are dropped first.

1. `## Environment` — OS, runtime, tooling constraints, local services, provider setup
2. `## Entities` — people, projects, repos, services referenced often
3. `## Project State` — milestones, blockers, medium-term status, important decisions
4. `## Dynamic Context` — current tasks, recent decisions, in-progress work

**Rules:**
- One fact per bullet, no prose paragraphs
- **Update/replace** existing facts instead of appending duplicates
- Put personal profile and preferences in `USER.md`, not in `memory/MEMORY.md`
- Put durable operational facts in the top three MEMORY sections; only transient state goes in Dynamic Context
- Keep the file concise — the system auto-compacts when it exceeds ~1600 tokens

## Missing Context

If a topic feels incomplete, **search `HISTORY.md` first** before assuming a fact was never recorded. Use the `memory_search` tool for semantic queries, or grep for exact matches:

```bash
grep -i "keyword" memory/HISTORY.md
```

## Proactive Context Retrieval

If the user refers to past discussions or ongoing workflows you don't recall: **search `HISTORY.md` before responding**.

## Auto-consolidation

Handled automatically every ~10 messages. Long-term memory is auto-compacted by the system when it grows beyond the configured threshold.