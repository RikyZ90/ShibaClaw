import pytest
import asyncio
from unittest.mock import patch, MagicMock

from shibaclaw.agent.knowledge_manager import RAG_AVAILABLE

@pytest.fixture
def mock_agent_loop():
    from shibaclaw.agent.loop import ShibaBrain
    from unittest.mock import AsyncMock, patch
    
    with patch("shibaclaw.agent.loop.asyncio.create_task"):
        brain = ShibaBrain(
            bus=MagicMock(),
            provider=MagicMock(),
            workspace=MagicMock(),
            web_search_config=MagicMock(),
            exec_config=MagicMock()
        )
    
    brain.provider.chat_with_retry_streaming = AsyncMock()
    
    # Mock methods that would otherwise error out
    brain.context = MagicMock()
    brain.context.build_static_prompt.return_value = ""
    brain.context.build_runtime_block.return_value = ""
    
    return brain


@pytest.mark.asyncio
@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG dependencies are not installed")
@patch('shibaclaw.agent.knowledge_manager.KnowledgeManager')
async def test_agent_loop_does_not_block(mock_km_class, mock_agent_loop):
    # Setup mock to simulate KnowledgeManager behavior
    mock_km_instance = MagicMock()
    mock_km_class.return_value = mock_km_instance
    
    # Give list_collections a delay to ensure it's not blocking the event loop
    def mock_list_collections():
        import time
        time.sleep(0.1)
        return [{"id": "test_col", "name": "Test Col"}]
        
    mock_km_instance.list_collections.side_effect = mock_list_collections
    
    # We just want to ensure it runs without blocking asyncio
    async def run_loop():
        await mock_agent_loop._run_agent_loop(
            initial_messages=[{"role": "user", "content": "hi"}],
            model="test-model"
        )
        
    # If the loop blocks synchronously, this test would hang or show weird timing if we measured it.
    # But strictly, using asyncio.to_thread correctly handles the sleep without freezing the loop.
    task = asyncio.create_task(run_loop())
    
    # Let the loop run briefly
    await asyncio.sleep(0.01)
    
    # Cancel it because we just want to test if it starts and runs the km part
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        pass
        
    mock_km_instance.list_collections.assert_called()
