import pytest
import asyncio
from shibaclaw.agent.subagent import SubagentManager
from shibaclaw.bus.queue import MessageBus
from shibaclaw.bus.events import OutboundMessage


@pytest.mark.asyncio
async def test_subagent_notify_status_in_same_session(tmp_path):
    # To avoid 'coroutine was never awaited' warnings, we mock the methods directly
    # with AsyncMocks that return a proper Future or simply mock them with a standard MagicMock
    from unittest.mock import MagicMock

    mock_bus = MagicMock(spec=MessageBus)

    async def dummy_publish(*args, **kwargs):
        pass

    mock_bus.publish_outbound = MagicMock(side_effect=dummy_publish)

    mock_runner = MagicMock()

    async def dummy_process_direct(*args, **kwargs):
        return OutboundMessage(
            channel="webui", chat_id="test_chat", content="Summary of completed task", metadata={}
        )

    mock_runner.process_direct = MagicMock(side_effect=dummy_process_direct)

    mock_provider = MagicMock()

    manager = SubagentManager(
        workspace=tmp_path, provider=mock_provider, agent_runner=mock_runner, bus=mock_bus
    )
    manager.timeout = 0

    # Start the subagent
    spawn_msg = await manager.spawn(
        task="Test task",
        session_key="webui:test_session",
        origin_channel="webui",
        origin_chat_id="test_chat",
        label="Test label",
    )
    import re

    m = re.search(r"id: (sub_[0-9a-f]+)", spawn_msg)
    assert m is not None
    task_id = m.group(1)

    # Wait briefly for the task to begin execution and fire the status update
    await asyncio.sleep(0.1)

    # Inspect the outbound messages sent to the bus
    outbound_calls = mock_bus.publish_outbound.call_args_list
    assert len(outbound_calls) > 0

    # Check that session key makes it through correctly on the result message
    # The first message is the completion notification, the second should be the result processed by the runner
    result_msg = outbound_calls[0][0][0]
    if result_msg.metadata.get("system_event"):
        result_msg = outbound_calls[1][0][0]

    assert result_msg.metadata.get("task_id") == task_id
    assert "session_key" in mock_runner.process_direct.call_args.kwargs
    assert mock_runner.process_direct.call_args.kwargs["session_key"] == "webui:test_session"
    assert result_msg.metadata.get("session_key") == "webui:test_session"

    # Cancel the running subagent cleanly
    await manager.cancel_by_session("webui:test_session")

    # Wait briefly for cancellation to propagate and inner tasks to clean up
    await asyncio.sleep(0.1)
