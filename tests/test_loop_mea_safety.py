"""Regression coverage for private delegation, reset, stop and tool protocol."""

import asyncio
import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shibaclaw.agent.checkpoint_manager import CheckpointManager
from shibaclaw.agent.context_overflow_guard import ContextOverflowGuard
from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.agent.tools.registry import SkillVault
from shibaclaw.agent.tools.spawn import SpawnMeaTool
from shibaclaw.agent.turn_journal import REFUSAL, TurnJournal
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.schema import ExecToolConfig, WebSearchConfig
from shibaclaw.thinkers.base import LLMResponse, ToolCallRequest


KEY = "webui:fixture"


def _tool(call_id="same-id", query="query", content=None):
    return LLMResponse(
        content=content,
        tool_calls=[ToolCallRequest(id=call_id, name="web_search", arguments={"query": query})],
        finish_reason="tool_calls",
    )


def _brain(tmp_path, responses):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat_with_retry_streaming = AsyncMock(side_effect=responses)
    with patch("shibaclaw.agent.loop.MCPManager"):
        brain = ShibaBrain(
            MessageBus(), provider, tmp_path,
            web_search_config=WebSearchConfig(enabled=False),
            exec_config=ExecToolConfig(enabled=False),
        )
    brain.mcp.connect = AsyncMock()
    brain._schedule_background = lambda coro: coro.close()
    brain.tools.get_definitions = MagicMock(return_value=[])
    brain.context.build_static_prompt = MagicMock(return_value="STATIC")
    brain.context.build_runtime_block = MagicMock(return_value="LIVE")
    brain._resolve_provider_for_model = MagicMock(return_value=provider)
    brain.subagents._build_subagent_prompt = MagicMock(return_value="subagent")
    brain.subagents._announce_result = AsyncMock()
    return brain, provider


def _delegating_brain(tmp_path):
    return _brain(tmp_path, [
        LLMResponse(
            content=None,
            tool_calls=[ToolCallRequest(id="spawn1", name="spawn_mea", arguments={"task": "fixture-task"})],
            finish_reason="tool_calls",
        ),
        LLMResponse(content="Delegation started"),
        LLMResponse(content="Followup handled"),
    ])


async def _direct(brain, content):
    return await brain.process_direct(content, KEY, channel="webui", chat_id="fixture")


def _tasks(brain):
    return list(brain.subagents._running_tasks.values())


def _tools():
    tools = MagicMock()
    tools.get_definitions.return_value = []
    tools.execute = AsyncMock(return_value="fixture tool result")
    return tools


@pytest.mark.asyncio
async def test_new_removes_checkpoint_and_old_task_from_next_prompt(tmp_path):
    brain, provider = _brain(tmp_path, [_tool("old-call", "old-task"), LLMResponse(content="new answer")])
    brain.max_iterations = 1
    brain.tools.execute = AsyncMock(return_value="old-result")
    prompts = []
    responses = [_tool("old-call", "old-task"), LLMResponse(content="new answer")]

    async def chat(**kwargs):
        prompts.append(copy.deepcopy(kwargs["messages"]))
        return responses[len(prompts) - 1]

    provider.chat_with_retry_streaming = chat
    await _direct(brain, "old-task")
    assert CheckpointManager(tmp_path).load_checkpoint(KEY) is not None
    out = await _direct(brain, "/new")
    assert out.content == "New session started."
    assert CheckpointManager(tmp_path).load_checkpoint(KEY) is None
    await _direct(brain, "new-task")
    assert all(m.get("content") not in {"old-task", "old-result"} for m in prompts[-1])


@pytest.mark.asyncio
async def test_new_cancels_active_work_before_resetting_checkpoint(tmp_path):
    brain, provider = _brain(tmp_path, [])
    started = asyncio.Event()

    async def chat(**kwargs):
        started.set()
        await asyncio.Event().wait()

    provider.chat_with_retry_streaming = chat
    turn = asyncio.create_task(_direct(brain, "old-task"))
    await asyncio.wait_for(started.wait(), 2)
    out = await _direct(brain, "/new")
    assert out.content == "New session started."
    assert turn.cancelled()
    assert CheckpointManager(tmp_path).load_checkpoint(KEY) is None
    assert brain.sessions.get_or_create(KEY).messages == []


@pytest.mark.asyncio
async def test_pivot_follows_all_results_and_budgeting_never_orphans_results(tmp_path):
    brain, provider = _brain(tmp_path, [])
    brain.tools.execute = AsyncMock(return_value="Error: fixture failure")
    responses = [
        _tool(f"c{i}", f"q{i}", content=f"Attempt {i}: " + "x" * 1000)
        for i in range(3)
    ]
    responses[2].tool_calls.append(ToolCallRequest(id="c3", name="web_search", arguments={"query": "extra"}))
    responses.append(LLMResponse(content="done"))
    prompts = []

    async def chat(**kwargs):
        prompts.append(copy.deepcopy(kwargs["messages"]))
        return responses[len(prompts) - 1]

    provider.chat_with_retry_streaming = chat
    await brain._run_agent_loop(
        [{"role": "system", "content": "s"}, {"role": "user", "content": "task"}],
        session_key=KEY,
    )
    messages = prompts[-1]
    call_index = next(i for i, m in enumerate(messages) if any(c["id"] == "c2" for c in m.get("tool_calls", [])))
    assert [m.get("tool_call_id") for m in messages[call_index + 1:call_index + 3]] == ["c2", "c3"]
    assert messages[call_index + 3]["role"] == "system"
    guard = ContextOverflowGuard(tmp_path)
    for budget in range(50, 900):
        pruned = guard.budget_context(messages, max_tokens=budget)
        declared = {c["id"] for m in pruned for c in m.get("tool_calls", [])}
        results = {m["tool_call_id"] for m in pruned if m.get("role") == "tool"}
        assert results == declared


@pytest.mark.asyncio
@pytest.mark.parametrize("privacy", [None, "incognito", "ephemeral"])
async def test_public_mea_dedupes_across_parent_turns_and_keeps_private_progress_in_memory(tmp_path, privacy):
    brain, provider = _delegating_brain(tmp_path)
    if privacy:
        brain.sessions.get_or_create(KEY).metadata[privacy] = True
    duplicate_ready, release = asyncio.Event(), asyncio.Event()
    responses = [_tool(), _tool(), LLMResponse(content="execution done"), _tool(), LLMResponse(content="PASSED")]
    calls = 0

    async def child_chat(**kwargs):
        nonlocal calls
        index = calls
        calls += 1
        if index == 1:
            duplicate_ready.set()
            await release.wait()
        return responses[index]

    provider.chat_with_retry = child_chat
    tools = _tools()
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        await _direct(brain, "delegate")
        await asyncio.wait_for(duplicate_ready.wait(), 2)
        assert tools.execute.await_count == 1
        # A new parent input changes the root journal scope while MEA is running.
        await _direct(brain, "followup")
        pending = _tasks(brain)
        release.set()
        result, = await asyncio.gather(*pending)

    assert result["status"] == "completed"
    assert result["verdict"] == "PASSED"
    # One executor operation and one auditor operation, despite the reused ID.
    assert tools.execute.await_count == 2
    brain.subagents._announce_result.assert_awaited_once()
    files = list((tmp_path / "memory" / "mea").glob("*.md"))
    if privacy:
        assert not (tmp_path / "memory" / "mea").exists()
        assert list((tmp_path / "runtime" / "turns").glob("*.jsonl")) == []
    else:
        assert len(files) == 1
        assert "**Status**: Completed" in files[0].read_text(encoding="utf-8")
        rows = brain.turn_journal._load(KEY)
        executed = [row for row in rows if row.get("status") == "completed" and row.get("tool") is None]
        assert len(executed) == 3  # spawn, execute, audit
    assert brain.subagents.get_running_count() == 0


@pytest.mark.asyncio
async def test_explicit_ephemeral_mea_binds_privacy_before_background_session_changes(tmp_path):
    brain, provider = _delegating_brain(tmp_path)
    brain.sessions.get_or_create(KEY).metadata["incognito"] = True
    provider.chat_with_retry = AsyncMock(side_effect=[LLMResponse(content="private result"), LLMResponse(content="PASSED")])
    # Set the tool's context while private, then change the session before launch.
    brain._set_tool_context("webui", "fixture", None, KEY)
    brain.sessions.get_or_create(KEY).metadata.clear()
    await brain.tools.get("spawn_mea").execute("private fixture task")
    await asyncio.gather(*_tasks(brain))
    assert not (tmp_path / "memory" / "mea").exists()
    assert list((tmp_path / "runtime" / "turns").glob("*.jsonl")) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("privacy", ["incognito", "ephemeral"])
async def test_direct_mea_resolves_private_session_without_spawn_context(tmp_path, privacy):
    brain, provider = _brain(tmp_path, [])
    brain.sessions.get_or_create(KEY).metadata[privacy] = True
    provider.chat_with_retry = AsyncMock(side_effect=[LLMResponse(content="private result"), LLMResponse(content="PASSED")])
    result = await brain.subagents.execute_mea_loop("private fixture task", "webui", "fixture", KEY)
    assert result["status"] == "completed"
    assert not (tmp_path / "memory" / "mea").exists()


@pytest.mark.asyncio
async def test_public_idle_stop_prevents_tools_returned_by_pending_mea_provider(tmp_path):
    brain, provider = _delegating_brain(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()

    async def chat(**kwargs):
        started.set()
        await release.wait()
        return _tool()

    provider.chat_with_retry = AsyncMock(side_effect=chat)
    tools = _tools()
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        await _direct(brain, "delegate")
        await asyncio.wait_for(started.wait(), 2)
        pending = _tasks(brain)
        stopped = await _direct(brain, "/stop idle")
        assert stopped.content == "Stopping when the current tool finishes."
        release.set()
        result, = await asyncio.gather(*pending)
    assert result["status"] == "stopped"
    tools.execute.assert_not_awaited()
    provider.chat_with_retry.assert_awaited_once()
    brain.subagents._announce_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_idle_stop_finishes_current_mea_tool_and_latches_across_parent_input(tmp_path):
    brain, provider = _delegating_brain(tmp_path)
    response = _tool("first")
    response.tool_calls.append(ToolCallRequest(id="second", name="web_search", arguments={"query": "next"}))
    provider.chat_with_retry = AsyncMock(return_value=response)
    started, release = asyncio.Event(), asyncio.Event()
    tools = _tools()

    async def execute(*args):
        started.set()
        await release.wait()
        return "finished current tool"

    tools.execute = AsyncMock(side_effect=execute)
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        await _direct(brain, "delegate")
        await asyncio.wait_for(started.wait(), 2)
        pending = _tasks(brain)
        await _direct(brain, "/stop idle")
        await _direct(brain, "followup")
        assert not pending[0].done()
        release.set()
        result, = await asyncio.gather(*pending)
    assert result["status"] == "stopped"
    tools.execute.assert_awaited_once()
    provider.chat_with_retry.assert_awaited_once()
    assert brain.subagents._stop_modes == {}


@pytest.mark.asyncio
async def test_public_hard_stop_cancels_running_mea_tool_and_records_cancellation(tmp_path):
    brain, provider = _delegating_brain(tmp_path)
    provider.chat_with_retry = AsyncMock(return_value=_tool())
    started, canceled = asyncio.Event(), asyncio.Event()
    tools = _tools()

    async def execute(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            canceled.set()

    tools.execute = AsyncMock(side_effect=execute)
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        await _direct(brain, "delegate")
        await asyncio.wait_for(started.wait(), 2)
        stopped = await _direct(brain, "/stop")
    assert "Halted 1 hunt" in stopped.content
    assert canceled.is_set()
    assert brain.subagents.get_running_count() == 0
    provider.chat_with_retry.assert_awaited_once()
    brain.subagents._announce_result.assert_not_awaited()
    assert any(str(row.get("id", "")).startswith("sub_exec_") and row.get("status") == "canceled" for row in brain.turn_journal._load(KEY))


@pytest.mark.asyncio
async def test_sync_mea_reuses_journal_and_refuses_corrupt_records(tmp_path):
    journal = TurnJournal(tmp_path / "turns")
    journal.accept_input(KEY, "input")
    runner = MagicMock()
    runner._journal_for.return_value = journal
    provider = MagicMock()
    provider.get_default_model.return_value = "fixture-model"
    provider.chat_with_retry = AsyncMock(side_effect=[_tool(), _tool(), LLMResponse(content="done")])
    manager = SubagentManager(provider, tmp_path, MessageBus(), agent_runner=runner)
    manager._build_subagent_prompt = MagicMock(return_value="subagent")
    tools = _tools()
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        assert await manager._run_subagent_sync("task1", "task", "execute", session_key=KEY) == "done"
    tools.execute.assert_awaited_once()
    journal._path(KEY).write_text("not valid json", encoding="utf-8")
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        assert await manager._run_subagent_sync("task2", "task", "execute", session_key=KEY) == REFUSAL
    tools.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_journal_completion_uses_claimed_turn_after_new_parent_input(tmp_path):
    journal = TurnJournal(tmp_path)
    journal.accept_input(KEY, "first")
    turn = journal.scope(KEY)

    async def execute():
        journal.commit_turn(KEY)
        journal.accept_input(KEY, "second")
        return "done"

    result, halt = await journal.execute_claimed(KEY, "child:call", "exec", execute, turn=turn)
    assert (result, halt) == ("done", False)
    assert journal.claim(KEY, "child:call", "exec", turn=turn).result == "done"
    assert all(row["turn"] == turn for row in journal._load(KEY) if row.get("kind") == "operation")


@pytest.mark.asyncio
async def test_direct_idle_stop_with_no_work_does_not_count_command_itself(tmp_path):
    brain, _ = _brain(tmp_path, [])
    assert (await _direct(brain, "/stop idle")).content == "No active scent to stop."
    assert (await _direct(brain, "/stop")).content == "No active scent to stop."


@pytest.mark.asyncio
async def test_main_idle_stop_finishes_current_tool_and_completes_protocol_batch(tmp_path):
    response = _tool("first")
    response.tool_calls.extend([
        ToolCallRequest(id="second", name="web_search", arguments={"query": "next"}),
        ToolCallRequest(id="third", name="web_search", arguments={"query": "last"}),
    ])
    brain, provider = _brain(tmp_path, [response])
    started, release = asyncio.Event(), asyncio.Event()

    async def execute(*args):
        started.set()
        await release.wait()
        return "finished current tool"

    brain.tools.execute = AsyncMock(side_effect=execute)
    task = asyncio.create_task(_direct(brain, "work"))
    await asyncio.wait_for(started.wait(), 2)
    await _direct(brain, "/stop idle")
    release.set()
    out = await task
    assert "not started" in out.content
    brain.tools.execute.assert_awaited_once()
    provider.chat_with_retry_streaming.assert_awaited_once()
    history = brain.sessions.get_or_create(KEY).get_history(max_messages=0)
    declared = {call["id"] for message in history for call in message.get("tool_calls", [])}
    results = {message["tool_call_id"] for message in history if message["role"] == "tool"}
    assert declared == results == {"first", "second", "third"}


@pytest.mark.asyncio
async def test_main_hard_stop_cancels_shielded_tool_future(tmp_path):
    brain, _ = _brain(tmp_path, [_tool()])
    started, canceled = asyncio.Event(), asyncio.Event()

    async def execute(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            canceled.set()

    brain.tools.execute = AsyncMock(side_effect=execute)
    task = asyncio.create_task(_direct(brain, "work"))
    await asyncio.wait_for(started.wait(), 2)
    out = await _direct(brain, "/stop")
    assert "Halted 1 hunt" in out.content
    assert task.cancelled()
    assert canceled.is_set()


@pytest.mark.asyncio
async def test_regular_subagent_obeys_idle_stop_after_parent_clears_journal_stop(tmp_path):
    brain, provider = _brain(tmp_path, [LLMResponse(content="followup handled")])
    response = _tool("first")
    response.tool_calls.append(ToolCallRequest(id="second", name="web_search", arguments={"query": "next"}))
    provider.chat_with_retry = AsyncMock(return_value=response)
    tools = _tools()
    started, release = asyncio.Event(), asyncio.Event()

    async def execute(*args):
        started.set()
        await release.wait()
        return "finished current tool"

    tools.execute = AsyncMock(side_effect=execute)
    with patch("shibaclaw.agent.subagent.SkillVault", return_value=tools):
        await brain.subagents.spawn("fixture task", "webui", "fixture", KEY)
        await asyncio.wait_for(started.wait(), 2)
        pending = _tasks(brain)
        await _direct(brain, "/stop idle")
        await _direct(brain, "followup")
        release.set()
        await asyncio.gather(*pending)
    tools.execute.assert_awaited_once()
    provider.chat_with_retry.assert_awaited_once()
    assert brain.subagents.get_running_count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("privacy", ["incognito", "ephemeral"])
async def test_concurrent_public_turn_cannot_overwrite_pending_private_mea_context(tmp_path, privacy):
    brain, private_provider = _brain(tmp_path, [])
    public_provider = MagicMock()
    public_provider.chat_with_retry_streaming = AsyncMock(return_value=LLMResponse(content="public handled"))
    private_key, public_key = "webui:private", "webui:public"
    private_session = brain.sessions.get_or_create(private_key)
    private_session.metadata.update({privacy: True, "model": "private-model"})
    brain.sessions.get_or_create(public_key).metadata["model"] = "public-model"
    brain._resolve_provider_for_model.side_effect = lambda model: (
        private_provider if model == "private-model" else public_provider
    )
    waiting, release, completed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = 0

    async def private_chat(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            waiting.set()
            await release.wait()
            return LLMResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="private-spawn", name="spawn_mea", arguments={"task": "private fixture"})],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="private delegation started")

    private_provider.chat_with_retry_streaming = private_chat
    for provider in (private_provider, public_provider):
        provider.chat_with_retry = AsyncMock(side_effect=[LLMResponse(content="execution done"), LLMResponse(content="PASSED")])
    seen = {}
    execute_mea = brain.subagents.execute_mea_loop

    async def capture(**kwargs):
        seen.update(kwargs)
        try:
            return await execute_mea(**kwargs)
        finally:
            completed.set()

    brain.subagents.execute_mea_loop = capture
    pending_private = asyncio.create_task(brain.process_direct(
        "delegate privately", private_key, channel="webui", chat_id="private",
    ))
    await asyncio.wait_for(waiting.wait(), 2)
    await brain.process_direct("public context", public_key, channel="webui", chat_id="public")
    release.set()
    await pending_private
    await asyncio.wait_for(completed.wait(), 2)
    assert not (tmp_path / "memory" / "mea").exists()
    assert seen["origin_channel"] == "webui"
    assert seen["origin_chat_id"] == "private"
    assert seen["session_key"] == private_key
    assert seen["provider"] is private_provider
    assert seen["model"] == "private-model"
    assert seen["ephemeral"] is True
    assert all(row.get("tool") != "spawn_mea" for row in brain.turn_journal._load(public_key))


@pytest.mark.asyncio
async def test_direct_registry_mea_context_is_isolated_between_caller_tasks():
    manager = MagicMock()
    calls, background = {}, []

    async def capture(**kwargs):
        calls[kwargs["task"]] = kwargs
        return {"status": "completed"}

    manager.execute_mea_loop = capture
    manager.track.side_effect = lambda session_key, task: background.append((session_key, task))
    tool = SpawnMeaTool(manager)
    registry = SkillVault()
    registry.register(tool)
    private_provider, public_provider = object(), object()
    private_waiting, public_finished = asyncio.Event(), asyncio.Event()

    async def private_call():
        tool.set_context("webui", "private", "webui:private", model="private-model", provider=private_provider, ephemeral=True)
        private_waiting.set()
        await public_finished.wait()
        await registry.execute("spawn_mea", {"task": "private task"})

    async def public_call():
        await private_waiting.wait()
        tool.set_context("telegram", "public", "telegram:public", model="public-model", provider=public_provider)
        await registry.execute("spawn_mea", {"task": "public task"})
        public_finished.set()

    await asyncio.gather(private_call(), public_call())
    await asyncio.gather(*(task for _, task in background))
    assert calls["private task"]["session_key"] == "webui:private"
    assert calls["private task"]["ephemeral"] is True
    assert calls["private task"]["provider"] is private_provider
    assert calls["private task"]["model"] == "private-model"
    assert calls["public task"]["session_key"] == "telegram:public"
    assert calls["public task"]["ephemeral"] is False
    assert calls["public task"]["provider"] is public_provider
    assert {session_key for session_key, _ in background} == {"webui:private", "telegram:public"}
