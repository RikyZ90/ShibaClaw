---
name: memory
description: Two-layer memory system with token-budgeted injection and auto-compaction of long-term facts.
always: true
---

# Memory

## Structure

- `memory/MEMORY.md` — Long-term facts. Injected into every system prompt under `# Memory`, **truncated by section** if it exceeds the token budget (~2000 tokens default).
- `memory/HISTORY.md` — Append-only log with `[YYYY-MM-DD HH:MM] [#tag1 #tag2]` entries. Never injected. Search it with grep when historical context is missing.

## Writing to MEMORY.md

Write immediately with `edit_file` / `write_file` for: user preferences, project context, important entities.

- One fact per bullet, no prose paragraphs
- **Update/replace** existing facts instead of appending duplicates
- Keep the file concise — the system auto-compacts when it exceeds ~1600 tokens
- Do not add speculative or redundant facts

## Missing Context

If a topic feels incomplete, **search `HISTORY.md` first** before assuming a fact was never recorded. Older sections of MEMORY.md may have been compacted away, but important facts are preserved.

```bash
grep -i "keyword" memory/HISTORY.md
```

## Proactive Context Retrieval

If the user refers to past discussions or ongoing workflows you don't recall: **search `HISTORY.md` before responding**.

## Auto-consolidation

Handled automatically every ~10 messages. Long-term memory is auto-compacted by the system when it grows beyond the configured threshold.