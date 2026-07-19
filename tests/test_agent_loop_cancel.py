import pytest
import asyncio
from unittest.mock import MagicMock
from pathlib import Path

@pytest.mark.asyncio
async def test_shibabrain_task_cancelling():
    """Ensure the event loop handles task cancellation safely when asyncio.current_task() is checked."""
    from shibaclaw.agent.loop import ShibaBrain

    # Let's mock out the init to just test the logic inside `run` if possible
    # Wait, the NameError is in shibaclaw/agent/loop.py itself because it references WebSearchConfig but doesn't import it? Let's check loop.py.
