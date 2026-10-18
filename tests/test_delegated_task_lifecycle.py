"""Task history, capability inheritance and result delivery regressions."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from shibaclaw.agent.subagent import SubagentManager, WorkerError
from shibaclaw.agent.task_runs import TaskRuns
from shibaclaw.agent.tools.registry import SkillVault
from shibaclaw.agent.tools.spawn import SpawnTool, SpawnMeaTool
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.schema import ExecToolConfig
from shibaclaw.thinkers.base import LLMResponse, ToolCallRequest


KEY = "webui:fixture"


def manager(tmp_path, **kwargs):
    provider = MagicMock()
    provider.get_default_model.return_value = "fixture"
    return SubagentManager(provider, tmp_path, MessageBus(), **kwargs)


async def drain(m):
    tasks = list(m._running_tasks.values())
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await asyncio.sleep(0)


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "incomplete", "timed_out"])
async def test_spawn_publishes_the_actual_outcome_and_retains_card(tmp_path, outcome):
    m = manager(tmp_path, timeout=0.01 if outcome == "timed_out" else 0)

    async def worker(*args, **kwargs):
        if outcome == "timed_out":
            await asyncio.Event().wait()
        if outcome != "succeeded":
            raise WorkerError("failure", outcome)
        return "done"

    m._run_subagent_inner = worker
    await m.spawn("task", "webui", "fixture", KEY)
    await drain(m)
    (row,) = m.snapshot(KEY)
    assert row["status"] == outcome
    assert row["finished_at"] >= row["started_at"]
    event = await m.bus.consume_outbound()
    assert event.metadata["status"] == "running"
    event = await m.bus.consume_outbound()
    assert event.metadata["status"] == outcome
    assert TaskRuns(tmp_path).snapshot(KEY)[0]["status"] == outcome


async def test_cancel_requires_same_session_and_cleans_up_before_start(tmp_path):
    m = manager(tmp_path)
    m._run_subagent_inner = AsyncMock(side_effect=lambda *a, **k: asyncio.Event().wait())
    await m.spawn("task", "webui", "fixture", KEY)
    (task_id,) = m._running_tasks
    assert not await m.cancel_task("webui:other", task_id)
    assert await m.cancel_task(KEY, task_id)
    await asyncio.sleep(0)
    assert m.snapshot(KEY)[0]["status"] == "cancelled"
    assert not m.has_running_for_session(KEY)
    assert m.bus.inbound_size == 0


async def test_result_handoff_is_queued_and_outside_worker_timeout(tmp_path):
    runner = MagicMock()
    runner._checkpoint_forbidden.return_value = False
    m = manager(tmp_path, agent_runner=runner, timeout=0.01)
    m._run_subagent_inner = AsyncMock(return_value="result")
    await m.spawn("task", "webui", "fixture", KEY)
    await drain(m)
    runner.process_direct.assert_not_called()
    result = await m.bus.consume_inbound()
    assert result.session_key == KEY
    assert result.metadata["hidden"]
    assert result.metadata["task_id"] == m.snapshot(KEY)[0]["task_id"]
    assert m.snapshot(KEY)[0]["status"] == "succeeded"


@pytest.mark.parametrize("tool_class", [SpawnTool, SpawnMeaTool])
async def test_capability_snapshot_reaches_both_delegation_paths(tmp_path, tool_class):
    m = manager(tmp_path)
    seen = []

    async def worker(*args, **kwargs):
        vault = SkillVault()
        for name in ["read_file", "exec", "write_file"]:
            tool = MagicMock()
            tool.name = name
            vault.register(tool)
        m._apply_capabilities(vault)
        seen.append(vault.tool_names)
        return (
            {"status": "completed", "verdict": "PASSED"} if tool_class is SpawnMeaTool else "done"
        )

    m._run_subagent_inner = worker
    m._execute_mea_loop = worker
    tool = tool_class(m)
    tool.set_context(
        "webui", "fixture", KEY, allowed_tools=frozenset({"read_file"}), parent_turn_id="42"
    )
    await tool.execute("task")
    await drain(m)
    assert seen == [["read_file"]]
    assert m.snapshot(KEY)[0]["parent_turn_id"] == "42"


async def test_global_exec_disable_applies_to_direct_workers(tmp_path):
    m = manager(tmp_path, exec_config=ExecToolConfig(enable=False))
    vault = SkillVault()
    tool = MagicMock()
    tool.name = "exec"
    vault.register(tool)
    m._apply_capabilities(vault)
    assert not vault.has("exec")


async def test_mea_reports_audit_phase_and_timeout_without_false_success(tmp_path):
    m = manager(tmp_path, timeout=0.02)
    started = asyncio.Event()

    async def worker(*args, **kwargs):
        if str(args[0]).startswith("sub_exec"):
            return "done"
        started.set()
        await asyncio.Event().wait()

    m._run_subagent_sync = worker
    result = await m.execute_mea_loop("task", "webui", "fixture", KEY)
    assert started.is_set()
    assert result["status"] == "error"
    (row,) = m.snapshot(KEY)
    assert row["phase"] == "auditing"
    assert row["status"] == "timed_out"


async def test_mea_llm_error_does_not_proceed_to_audit(tmp_path):
    m = manager(tmp_path)
    m.provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(content="provider error", finish_reason="error")
    )
    await m.execute_mea_loop("task", "webui", "fixture", KEY)
    assert m.provider.chat_with_retry.await_count == 1
    assert m.snapshot(KEY)[0]["status"] == "failed"


async def test_iteration_exhaustion_is_incomplete(tmp_path):
    m = manager(tmp_path)
    m.provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content="still working",
            tool_calls=[ToolCallRequest(id="read", name="list_dir", arguments={"path": "."})],
            finish_reason="tool_calls",
        )
    )
    await m.spawn("task", "webui", "fixture", KEY)
    await drain(m)
    assert m.snapshot(KEY)[0]["status"] == "incomplete"


def test_history_is_session_scoped_bounded_and_terminal_states_do_not_regress(tmp_path):
    runs = TaskRuns(tmp_path)
    for i in range(110):
        runs.put(KEY, str(i), status="running", started_at=1)
        runs.put(KEY, str(i), status="succeeded", result="done")
    assert len(runs.snapshot(KEY)) == 100
    assert not runs.snapshot("webui:other")
    row = runs.put(KEY, "109", status="running")
    assert row["status"] == "succeeded"
    fresh = TaskRuns(tmp_path)
    assert len(fresh.snapshot(KEY)) == 100


def test_restart_marks_running_tasks_incomplete_and_private_runs_stay_in_memory(tmp_path):
    runs = TaskRuns(tmp_path)
    runs.put(KEY, "old", status="running")
    assert TaskRuns(tmp_path).snapshot(KEY)[0]["status"] == "incomplete"
    runs.set_private(KEY)
    runs.put(KEY, "private", status="running")
    assert runs.snapshot(KEY)
    assert not runs._path(KEY).exists()
    assert TaskRuns(tmp_path).snapshot(KEY) == []


async def test_direct_and_queued_result_share_the_session_lock(tmp_path):
    from shibaclaw.agent.loop import ShibaBrain
    from shibaclaw.bus.events import InboundMessage

    brain = object.__new__(ShibaBrain)
    brain.mcp = MagicMock(connect=AsyncMock())
    brain._active_tasks, brain._session_locks = {}, {}
    brain.bus = MessageBus()
    started, release = asyncio.Event(), asyncio.Event()
    active, peak = 0, 0

    async def process(msg, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if msg.content == "parent":
            started.set()
            await release.wait()
        active -= 1

    brain._process_message = process
    parent = asyncio.create_task(brain.process_direct("parent", KEY))
    await started.wait()
    result = asyncio.create_task(
        brain._dispatch(
            InboundMessage(
                channel="webui",
                chat_id="fixture",
                sender_id="subagent",
                content="result",
                session_key_override=KEY,
            )
        )
    )
    await asyncio.sleep(0)
    assert active == 1
    release.set()
    await asyncio.gather(parent, result)
    assert peak == 1


async def test_queued_result_from_a_reset_generation_is_discarded():
    from shibaclaw.agent.loop import ShibaBrain
    from shibaclaw.bus.events import InboundMessage

    brain = object.__new__(ShibaBrain)
    brain.subagents = MagicMock(generations={KEY: 1})
    assert (
        await brain._process_message(
            InboundMessage(
                channel="webui",
                chat_id="fixture",
                sender_id="subagent",
                content="obsolete",
                session_key_override=KEY,
                metadata={"_delegation_generation": 0},
            )
        )
        is None
    )


async def test_websocket_cancel_uses_the_socket_session_not_supplied_session(monkeypatch):
    from shibaclaw.webui import ws_handler

    socket = MagicMock(send_text=AsyncMock())
    request = AsyncMock(side_effect=[{"cancelled": False}, {"tasks": []}])
    monkeypatch.setitem(ws_handler.sessions, "test-socket", {"session_key": KEY})
    monkeypatch.setattr(ws_handler.gateway_client, "request", request)
    await ws_handler._handle_subagents(
        "test-socket", socket, {"task_id": "x", "session_key": "webui:other"}, cancel=True
    )
    assert request.await_args_list[0].args == (
        "subagent_cancel",
        {"session_key": KEY, "task_id": "x"},
    )
    assert request.await_args_list[1].args == ("subagent_snapshot", {"session_key": KEY})


async def test_private_toggle_purges_public_task_history_before_next_update(tmp_path):
    runner = MagicMock()
    runner._checkpoint_forbidden.return_value = False
    m = manager(tmp_path, agent_runner=runner)
    origin = {"channel": "webui", "chat_id": "fixture", "session_key": KEY}
    await m._status("one", origin, status="running")
    assert m.runs._path(KEY).exists()
    runner._checkpoint_forbidden.return_value = True
    await m._status("one", origin, status="succeeded")
    assert not m.runs._path(KEY).exists()


def test_privacy_tombstone_blocks_writes_from_an_already_running_gateway(tmp_path):
    gateway = TaskRuns(tmp_path)
    gateway.put(KEY, "task", status="running")
    TaskRuns(tmp_path).set_private(KEY, persist=True)
    gateway.put(KEY, "task", status="succeeded", result="private content")
    assert not gateway._path(KEY).exists()
    assert TaskRuns(tmp_path).snapshot(KEY) == []
