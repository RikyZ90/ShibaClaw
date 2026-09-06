"""Batch-2 OpenClaw-inspired features tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from shibaclaw.agent.profiles import ProfileManager
from shibaclaw.agent.skill_workshop import SkillWorkshop
from shibaclaw.automation.grants import job_is_approved, operation_fingerprint
from shibaclaw.automation.types import AutomationJob, AutomationPayload, AutomationSchedule
from shibaclaw.brain.manager import PackManager
from shibaclaw.config.history import append_config_history, list_config_history


def test_automation_fingerprint_and_approval():
    sched = AutomationSchedule(kind="every", every_ms=60_000)
    payload = AutomationPayload(kind="scheduled", message="ping")
    fp = operation_fingerprint(sched, payload)
    job = AutomationJob(
        id="x",
        name="t",
        schedule=sched,
        payload=payload,
        require_approval=True,
        approved_fingerprint=None,
    )
    assert not job_is_approved(job)
    job.approved_fingerprint = fp
    assert job_is_approved(job)
    job.payload = AutomationPayload(kind="scheduled", message="pong")
    assert not job_is_approved(job)


def test_skill_workshop_max_three(tmp_path: Path):
    ws = SkillWorkshop(tmp_path)
    for i in range(3):
        r = ws.propose(
            name=f"skill{i}",
            description="d",
            skill_md=f"# Skill {i}\n",
        )
        assert r["ok"], r
    full = ws.propose(name="skill3", description="d", skill_md="# x\n")
    assert not full["ok"]
    assert "full" in full["error"]
    pending = ws.list_pending()
    assert len(pending) == 3
    ok = ws.approve(pending[0]["id"])
    assert ok["ok"]
    assert (tmp_path / "skills" / pending[0]["name"] / "SKILL.md").exists()
    assert len(ws.list_pending()) == 2


def test_profile_model_allowlist(tmp_path: Path):
    pm = ProfileManager(tmp_path)
    pm.create_profile(
        "trader",
        "Trader",
        allowed_models=["openai/gpt-4o", "google/*"],
    )
    assert pm.model_allowed("trader", "openai/gpt-4o")
    assert pm.model_allowed("trader", "google/gemini-3-flash")
    assert not pm.model_allowed("trader", "anthropic/claude-opus")
    # Substring must not match (e.g. gpt-4o inside a longer id).
    assert not pm.model_allowed("trader", "openai/gpt-4o-mini")
    assert pm.model_allowed("default", "anything")  # None = unrestricted

    pm.create_profile("locked", "Locked", allowed_models=[])
    assert not pm.model_allowed("locked", "openai/gpt-4o")  # [] = deny all


@pytest.mark.asyncio
async def test_memory_forget_rejects_short_needle(tmp_path: Path):
    from shibaclaw.agent.memory import ScentKeeper

    store = ScentKeeper(tmp_path)
    store.memory_file.parent.mkdir(parents=True, exist_ok=True)
    store.memory_file.write_text("keep this line\nsecret password here\n", encoding="utf-8")
    short = await store.forget_memory_lines("ab")
    assert short.get("error")
    assert "secret password here" in store.memory_file.read_text(encoding="utf-8")

    preview = await store.forget_memory_lines("password")
    assert preview.get("preview") is True
    assert preview["counts"]["MEMORY.md"] == 1
    assert "secret password here" in store.memory_file.read_text(encoding="utf-8")

    ok = await store.forget_memory_lines("password", confirm=True)
    assert not ok.get("error")
    assert not ok.get("preview")
    assert ok["MEMORY.md"] == 1
    assert "password" not in store.memory_file.read_text(encoding="utf-8")
    assert (tmp_path / "memory" / "quarantine").exists()
    assert (tmp_path / "memory" / "AUDIT.md").exists()


def test_incognito_toggle_purges_persisted_file(tmp_path: Path):
    pm = PackManager(tmp_path)
    s = pm.get_or_create("webui:was-normal")
    s.add_message("user", "persisted-secret-phrase")
    pm.save(s)
    path = pm._get_session_path("webui:was-normal")
    assert path.exists()
    assert any(
        "persisted-secret-phrase" in h.get("snippet", "")
        for h in pm.search_messages("persisted-secret-phrase")
    )

    s.metadata["incognito"] = True
    pm.purge_persisted_session(s.key)
    pm.save(s)
    assert not path.exists()
    assert pm.search_messages("persisted-secret-phrase") == []


@pytest.mark.asyncio
async def test_interactive_turn_context_isolation():
    import asyncio

    from shibaclaw.agent.interactive_ctx import (
        InteractiveTurnContext,
        bind_interactive_turn,
        reset_interactive_turn,
        turn_interactive,
    )

    results: dict[str, str] = {}

    async def worker(name: str, sk: str) -> None:
        token = bind_interactive_turn(
            InteractiveTurnContext(channel="webui", chat_id=name, session_key=sk)
        )
        try:
            await asyncio.sleep(0.05)
            results[name] = turn_interactive().session_key
        finally:
            reset_interactive_turn(token)

    await asyncio.gather(
        worker("a", "webui:a"),
        worker("b", "webui:b"),
    )
    assert results["a"] == "webui:a"
    assert results["b"] == "webui:b"


@pytest.mark.asyncio
async def test_interactive_resolve_requires_session_key():
    import asyncio

    from shibaclaw.agent.interactive import InteractiveHub

    hub = InteractiveHub()
    fut = asyncio.get_running_loop().create_future()
    hub._pending["rid123"] = fut
    hub._pending_meta["rid123"] = {"session_key": "webui:alpha", "kind": "ask"}
    assert hub.resolve("rid123", {"ok": True}, session_key="webui:other") is False
    assert not fut.done()
    assert hub.resolve("rid123", {"ok": True, "text": "hi"}, session_key="webui:alpha")
    assert fut.done()


def test_session_rewind_fork_incognito(tmp_path: Path):
    pm = PackManager(tmp_path)
    s = pm.get_or_create("webui:main")
    for i in range(5):
        s.add_message("user" if i % 2 == 0 else "assistant", f"msg-{i}")
    pm.save(s)
    assert len(s.messages) == 5

    forked = pm.fork_session("webui:main", 3)
    assert forked is not None
    assert len(forked.messages) <= 3
    assert forked.metadata.get("forked_from") == "webui:main"

    pm.rewind_session("webui:main", 2)
    s2 = pm.get_or_create("webui:main")
    assert len(s2.messages) <= 2

    inc = pm.get_or_create("webui:secret")
    inc.metadata["incognito"] = True
    inc.add_message("user", "do not persist")
    pm.save(inc)
    path = pm._get_session_path("webui:secret")
    assert not path.exists()


@pytest.mark.asyncio
async def test_session_search_denied_on_telegram(tmp_path: Path):
    from shibaclaw.agent.tools.interactive import SessionSearchTool

    pm = PackManager(tmp_path)
    s = pm.get_or_create("webui:secret")
    s.add_message("user", "top-secret-phrase")
    pm.save(s)

    tool = SessionSearchTool(sessions=pm)
    tool.set_context("telegram", "1", "telegram:1")
    out = await tool.execute(query="top-secret-phrase")
    assert "only available on WebUI" in out
    assert "top-secret-phrase" not in out

    tool.set_context("webui", "direct", "webui:direct")
    ok = await tool.execute(query="top-secret-phrase")
    assert "top-secret-phrase" in ok or "Found" in ok


@pytest.mark.asyncio
async def test_archive_snapshot_skips_incognito(tmp_path: Path):
    from unittest.mock import AsyncMock, MagicMock

    from shibaclaw.agent.memory import PackMemory

    pm = PackManager(tmp_path)
    sess = pm.get_or_create("webui:incog")
    sess.metadata["incognito"] = True
    sess.add_message("user", "secret chat content")

    consolidator = PackMemory(
        workspace=tmp_path,
        provider=MagicMock(),
        model="test",
        sessions=pm,
        context_window_tokens=8000,
        build_messages=lambda *a, **k: [],
        get_tool_definitions=lambda: [],
    )
    consolidator.consolidate_messages = AsyncMock(return_value=True)
    consolidator.maybe_compact_memory = AsyncMock()

    ok = await consolidator.archive_snapshot(
        [{"role": "user", "content": "secret chat content"}],
        session_key="webui:incog",
    )
    assert ok is True
    consolidator.consolidate_messages.assert_not_called()


def test_config_history(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "shibaclaw.config.history._history_path",
        lambda: tmp_path / "config_history.jsonl",
    )
    append_config_history(
        actor="test",
        reason="unit",
        data={"providers": {"openai": {"apiKey": "sk-secret"}}},
        changed_keys=["providers"],
    )
    rows = list_config_history(limit=5)
    assert rows
    assert rows[0]["snapshot"]["providers"]["openai"]["apiKey"] == "***"
