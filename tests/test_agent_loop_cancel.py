import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.config.schema import WebSearchConfig, ExecToolConfig


@pytest.mark.asyncio
async def test_shibabrain_task_cancelling():
    """Ensure the event loop handles task cancellation safely when asyncio.current_task() is checked."""
    brain = ShibaBrain(
        bus=MagicMock(),
        provider=MagicMock(),
        workspace=Path("/tmp"),
        web_search_config=WebSearchConfig(),
        exec_config=ExecToolConfig(),
    )

    async def mock_consume():
        await asyncio.sleep(0)  # Make it yield so task can be cancelled
        raise asyncio.CancelledError()

    brain.bus.consume_inbound = MagicMock(side_effect=mock_consume)
    brain.mcp = MagicMock()
    brain.mcp.connect = AsyncMock()
    brain.mcp.close = AsyncMock()

    async def run_loop():
        # Will exit or raise
        try:
            await brain.run()
        except asyncio.CancelledError:
            pass

    # Start the loop
    task = asyncio.create_task(run_loop())
    await asyncio.sleep(0.01)

    # Check that brain is running, then cancel
    task.cancel()

    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.CancelledError:
        pass

    assert True
