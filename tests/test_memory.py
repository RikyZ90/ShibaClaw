"""Tests for the memory_search tool and memory template layout."""

import asyncio
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from shibaclaw.agent.tools.memory_search import (
    MemorySearchTool,
    _build_idf,
    _importance_score,
    _parse_entries,
    _recency_score,
    _relevance_score,
    _tokenize,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_history(tmp_path: Path, content: str) -> Path:
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir(parents=True, exist_ok=True)
    history = mem_dir / "HISTORY.md"
    history.write_text(content, encoding="utf-8")
    return history


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_basic(self):
        assert _tokenize("Hello World") == ["hello", "world"]

    def test_removes_stop_words(self):
        tokens = _tokenize("the quick brown fox is a dog")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "a" not in tokens
        assert "quick" in tokens

    def test_empty(self):
        assert _tokenize("") == []


# ---------------------------------------------------------------------------
# _parse_entries
# ---------------------------------------------------------------------------


class TestParseEntries:
    def test_standard_entry(self):
        raw = "[2025-01-15 10:30] [#python #debugging] [★3] Fixed import error in main.py"
        entries = _parse_entries(raw)
        assert len(entries) == 1
        e = entries[0]
        assert e["ts"] == datetime(2025, 1, 15, 10, 30)
        assert e["tags"] == ["python", "debugging"]
        assert e["importance"] == 3
        assert "Fixed import error" in e["body"]

    def test_entry_without_importance(self):
        raw = "[2025-01-15 10:30] [#python] Discussed project architecture"
        entries = _parse_entries(raw)
        assert len(entries) == 1
        assert entries[0]["importance"] == 1

    def test_entry_without_tags(self):
        raw = "[2025-01-15 10:30] Some plain entry"
        entries = _parse_entries(raw)
        assert len(entries) == 1
        assert entries[0]["tags"] == []

    def test_multiple_entries(self):
        raw = textwrap.dedent("""\
            [2025-01-15 10:30] [#python] Entry one

            [2025-01-14 09:00] [#rust] Entry two
        """)
        entries = _parse_entries(raw)
        assert len(entries) == 2

    def test_unparseable_block(self):
        raw = "Just some random text without timestamps"
        entries = _parse_entries(raw)
        assert len(entries) == 1
        assert entries[0]["ts"] is None
        assert entries[0]["importance"] == 1

    def test_importance_clamped(self):
        raw = "[2025-01-15 10:30] [#test] [★9] Over-rated entry"
        entries = _parse_entries(raw)
        assert entries[0]["importance"] == 5


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------


class TestRecencyScore:
    def test_now_is_one(self):
        now = datetime.now()
        assert _recency_score(now, now) == pytest.approx(1.0)

    def test_half_life(self):
        now = datetime.now()
        ts = now - timedelta(days=14)
        assert _recency_score(ts, now) == pytest.approx(0.5, abs=0.05)

    def test_none_timestamp(self):
        assert _recency_score(None, datetime.now()) == 0.0


class TestImportanceScore:
    def test_range(self):
        assert _importance_score(1) == pytest.approx(0.2)
        assert _importance_score(5) == pytest.approx(1.0)


class TestRelevanceScore:
    def test_exact_match(self):
        entries = [{"body": "python debugging error", "tags": ["python"]}]
        idf = _build_idf(entries)
        query = _tokenize("python debugging")
        entry_tokens = _tokenize("python debugging error python")
        score = _relevance_score(query, entry_tokens, idf)
        assert score > 0

    def test_no_match(self):
        entries = [{"body": "python debugging", "tags": []}]
        idf = _build_idf(entries)
        query = _tokenize("rust compiler")
        entry_tokens = _tokenize("python debugging")
        score = _relevance_score(query, entry_tokens, idf)
        assert score == 0.0

    def test_empty_query(self):
        assert _relevance_score([], ["python"], {}) == 0.0


# ---------------------------------------------------------------------------
# MemorySearchTool (integration)
# ---------------------------------------------------------------------------


class TestMemorySearchTool:
    def test_missing_history(self, tmp_path):
        tool = MemorySearchTool(workspace=tmp_path)
        result = asyncio.get_event_loop().run_until_complete(tool.execute(query="anything"))
        assert "not found" in result.lower()

    def test_empty_history(self, tmp_path):
        _write_history(tmp_path, "")
        tool = MemorySearchTool(workspace=tmp_path)
        result = asyncio.get_event_loop().run_until_complete(tool.execute(query="anything"))
        assert "empty" in result.lower()

    def test_returns_ranked_results(self, tmp_path):
        now = datetime.now()
        recent = now.strftime("%Y-%m-%d %H:%M")
        old = (now - timedelta(days=60)).strftime("%Y-%m-%d %H:%M")
        content = textwrap.dedent(f"""\
            [{recent}] [#python #flask] [★4] Built REST API with Flask and SQLAlchemy

            [{old}] [#rust #cli] [★2] Experimented with Rust CLI tools

            [{recent}] [#python #django] [★3] Migrated database to PostgreSQL with Django ORM
        """)
        _write_history(tmp_path, content)
        tool = MemorySearchTool(workspace=tmp_path)
        result = asyncio.get_event_loop().run_until_complete(
            tool.execute(query="python web framework", top_k=2)
        )
        lines = result.strip().split("\n")
        numbered = [line for line in lines if line and line[0].isdigit()]
        assert len(numbered) == 2
        assert "python" in result.lower()

    def test_top_k_limit(self, tmp_path):
        now = datetime.now()
        entries = []
        for i in range(10):
            ts = (now - timedelta(days=i)).strftime("%Y-%m-%d %H:%M")
            entries.append(f"[{ts}] [#test] [★1] Entry number {i}")
        _write_history(tmp_path, "\n\n".join(entries))
        tool = MemorySearchTool(workspace=tmp_path)
        result = asyncio.get_event_loop().run_until_complete(
            tool.execute(query="test entry", top_k=3)
        )
        numbered = [line for line in result.strip().split("\n") if line and line[0].isdigit()]
        assert len(numbered) == 3

    def test_schema(self):
        tool = MemorySearchTool(workspace=Path("."))
        schema = tool.to_schema()
        assert schema["function"]["name"] == "memory_search"
        assert "query" in schema["function"]["parameters"]["properties"]


# ---------------------------------------------------------------------------
# MEMORY.md template layout
# ---------------------------------------------------------------------------


class TestMemoryTemplate:
    def test_section_order(self):
        template_path = (
            Path(__file__).resolve().parent.parent
            / "shibaclaw"
            / "templates"
            / "memory"
            / "MEMORY.md"
        )
        content = template_path.read_text(encoding="utf-8")
        sections = [
            m.group(1)
            for m in __import__("re").finditer(r"^## (.+)$", content, __import__("re").MULTILINE)
        ]
        assert sections == ["Environment", "Entities", "Project State", "Dynamic Context"]


class TestUserProfileStore:
    def test_reads_and_writes_user_profile(self, tmp_path):
        from shibaclaw.agent.memory import ScentKeeper

        keeper = ScentKeeper(tmp_path)
        assert keeper.read_user_profile() == ""

        asyncio.run(keeper.write_user_profile("# User Profile\n\n- **Name**: Alice\n"))

        assert keeper.read_user_profile() == "# User Profile\n\n- **Name**: Alice\n"
        assert (tmp_path / "USER.md").read_text(
            encoding="utf-8"
        ) == "# User Profile\n\n- **Name**: Alice\n"


# ---------------------------------------------------------------------------
# _truncate_to_budget preserves static sections
# ---------------------------------------------------------------------------


class TestTruncationOrder:
    def test_drops_dynamic_first(self):
        from shibaclaw.agent.memory import ScentKeeper

        content = textwrap.dedent("""\
            ## Environment
            - Windows laptop with local Ollama

            ## Entities
            - Project X

            ## Project State
            - Release cut planned for Friday

            ## Dynamic Context
            - Fixing the onboarding modal spacing today
        """).strip()
        truncated = ScentKeeper._truncate_to_budget(content, max_tokens=40)
        assert "Environment" in truncated
        assert "Windows laptop" in truncated
