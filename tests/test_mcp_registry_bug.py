import pytest
from shibaclaw.agent.tools.mcp import clear_mcp_sessions, reconnect_server

@pytest.mark.asyncio
async def test_mcp_name_error_clear():
    # This should not raise a NameError for _registry
    clear_mcp_sessions()

@pytest.mark.asyncio
async def test_mcp_name_error_reconnect():
    # This should also not raise a NameError for _registry
    await reconnect_server("non_existent_server")
