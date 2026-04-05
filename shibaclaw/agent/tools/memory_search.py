"""Ranked search over HISTORY.md entries."""

import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from shibaclaw.agent.tools.base import Tool

_ENTRY_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\]"  # timestamp
    r"(?:\s*\[([^\]]*)\])?"                        # tags  (optional)
    r"(?:\s*\[★(\d)\])?"                           # importance (optional)
    r"\s*(.*)",                                     # body
    re.DOTALL,
)

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into about between through after before above below "
    "and or but not no nor so yet both either neither each every all "
    "some any few more most other such that this these those it its "
    "i me my we us our you your he him his she her they them their "
    "what which who whom whose when where how why".split()
)


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP_WORDS]


def _parse_entries(raw: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    blocks = raw.strip().split("\n\n")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = _ENTRY_RE.match(block)
        if not m:
            entries.append({
                "ts": None,
                "tags": [],
                "importance": 1,
                "body": block,
                "raw": block,
            })
            continue
        ts_str, tags_str, imp_str, body = m.groups()
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
        except ValueError:
            ts = None
        tags = re.findall(r"#([\w-]+)", tags_str or "")
        importance = int(imp_str) if imp_str else 1
        entries.append({
            "ts": ts,
            "tags": tags,
            "importance": max(1, min(5, importance)),
            "body": body.strip(),
            "raw": block,
        })
    return entries


def _recency_score(ts: datetime | None, now: datetime, half_life_days: float = 14.0) -> float:
    if ts is None:
        return 0.0
    age_days = max(0.0, (now - ts).total_seconds() / 86400)
    return math.exp(-0.693 * age_days / half_life_days)


def _importance_score(importance: int) -> float:
    return importance / 5.0


def _relevance_score(query_tokens: list[str], entry_tokens: list[str], idf: dict[str, float]) -> float:
    if not query_tokens or not entry_tokens:
        return 0.0
    entry_counter = Counter(entry_tokens)
    entry_len = len(entry_tokens)
    score = 0.0
    for qt in query_tokens:
        tf = entry_counter.get(qt, 0) / entry_len if entry_len else 0.0
        score += tf * idf.get(qt, 0.0)
    return score


def _build_idf(entries: list[dict[str, Any]]) -> dict[str, float]:
    n = len(entries)
    if n == 0:
        return {}
    df: Counter[str] = Counter()
    for entry in entries:
        tokens = set(_tokenize(entry["body"] + " " + " ".join(entry["tags"])))
        df.update(tokens)
    return {term: math.log((n + 1) / (count + 1)) + 1 for term, count in df.items()}


class MemorySearchTool(Tool):
    """Ranked search over HISTORY.md entries by recency, importance, and relevance."""

    W_RECENCY = 0.3
    W_IMPORTANCE = 0.25
    W_RELEVANCE = 0.45

    def __init__(self, workspace: Path):
        self._history_path = workspace / "memory" / "HISTORY.md"

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return (
            "Search past conversation history (HISTORY.md) by semantic relevance. "
            "Returns the top entries ranked by recency, importance, and keyword relevance. "
            "Use this instead of grep when you need context about past interactions."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — keywords or natural language describing what you are looking for.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5, max 20).",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        }

    async def execute(self, *, query: str, top_k: int = 5, **_: Any) -> str:
        if not self._history_path.exists():
            return "HISTORY.md not found — no history available yet."

        raw = self._history_path.read_text(encoding="utf-8")
        if not raw.strip():
            return "HISTORY.md is empty — no history available yet."

        entries = _parse_entries(raw)
        if not entries:
            return "No parseable entries found in HISTORY.md."

        query_tokens = _tokenize(query)
        idf = _build_idf(entries)
        now = datetime.now()

        max_rel = 0.0
        scored: list[tuple[float, float, float, dict[str, Any]]] = []
        for entry in entries:
            entry_tokens = _tokenize(entry["body"] + " " + " ".join(entry["tags"]))
            rec = _recency_score(entry["ts"], now)
            imp = _importance_score(entry["importance"])
            rel = _relevance_score(query_tokens, entry_tokens, idf)
            if rel > max_rel:
                max_rel = rel
            scored.append((rec, imp, rel, entry))

        results: list[tuple[float, dict[str, Any]]] = []
        for rec, imp, rel, entry in scored:
            norm_rel = (rel / max_rel) if max_rel > 0 else 0.0
            total = self.W_RECENCY * rec + self.W_IMPORTANCE * imp + self.W_RELEVANCE * norm_rel
            results.append((total, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        top = results[:min(top_k, 20)]

        if not top:
            return "No matching entries found."

        lines: list[str] = []
        for rank, (score, entry) in enumerate(top, 1):
            stars = "★" * entry["importance"]
            ts_label = entry["ts"].strftime("%Y-%m-%d %H:%M") if entry["ts"] else "unknown"
            tags = " ".join(f"#{t}" for t in entry["tags"])
            header = f"{rank}. [{ts_label}] {tags} {stars} (score: {score:.2f})"
            lines.append(header)
            lines.append(f"   {entry['body'][:300]}")
            lines.append("")

        return "\n".join(lines).rstrip()
