import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp import types
from shibaclaw.agent.tools.mcp import (
    MCPListTools,
    MCPCallTool,
    _mcp_sessions,
    _mcp_configs,
    get_mcp_servers_info,
    clear_mcp_sessions,
)


class MockToolDef:
    def __init__(self, name: str, description: str, schema: dict):
        self.name = name
        self.description = description
        self.inputSchema = schema


class MockToolsList:
    def __init__(self, tools: list):
        self.tools = tools


class MockCallResult:
    def __init__(self, text: str):
        self.content = [types.TextContent(type="text", text=text)]


@pytest.mark.asyncio
async def test_mcp_lazy_discovery_and_execution():
    clear_mcp_sessions()

    mock_session = AsyncMock()
    
    tool_defs = [
        MockToolDef("search_code", "Search for code snippets", {"type": "object", "properties": {"query": {"type": "string"}}}),
        MockToolDef("get_issue", "Get issue info", {"type": "object", "properties": {"issue_id": {"type": "integer"}}})
    ]
    mock_session.list_tools.return_value = MockToolsList(tool_defs)
    mock_session.call_tool.return_value = MockCallResult("Operation completed successfully!")

    _mcp_sessions["github"] = mock_session
    
    mock_cfg = MagicMock()
    mock_cfg.enabled_tools = ["*"]
    mock_cfg.tool_timeout = 10
    _mcp_configs["github"] = mock_cfg

    info = get_mcp_servers_info()
    assert "- **github**" in info

    list_tool = MCPListTools()
    assert list_tool.name == "mcp_list_tools"
    
    list_result = await list_tool.execute(server_name="github")
    assert "search_code" in list_result
    assert "get_issue" in list_result
    assert "Search for code snippets" in list_result

    call_tool = MCPCallTool()
    assert call_tool.name == "mcp_call_tool"

    call_result = await call_tool.execute(server_name="github", tool_name="search_code", arguments={"query": "test"})
    assert "Operation completed successfully!" in call_result
    mock_session.call_tool.assert_called_once_with("search_code", arguments={"query": "test"})

    mock_cfg.enabled_tools = ["search_code"]
    
    call_result_2 = await call_tool.execute(server_name="github", tool_name="search_code", arguments={"query": "test2"})
    assert "Operation completed successfully!" in call_result_2

    call_result_3 = await call_tool.execute(server_name="github", tool_name="get_issue", arguments={"issue_id": 123})
    assert "Error: Tool 'get_issue' is not enabled" in call_result_3

    # Test casting of stringified JSON arguments parameter
    casted = call_tool.cast_params({
        "server_name": "github",
        "tool_name": "search_code",
        "arguments": '{"query": "test_json"}'
    })
    assert isinstance(casted["arguments"], dict)
    assert casted["arguments"]["query"] == "test_json"

    clear_mcp_sessions()


@pytest.mark.asyncio
async def test_mcp_dynamic_registration(monkeypatch):
    from shibaclaw.agent.tools.registry import SkillVault
    from shibaclaw.agent.tools.mcp import connect_mcp_servers, register_active_mcp_tools, clear_mcp_sessions
    from contextlib import AsyncExitStack

    clear_mcp_sessions()

    # Mock tools and session
    mock_session = AsyncMock()
    tool_defs = [
        MockToolDef("search_code", "Search for code snippets", {"type": "object", "properties": {"query": {"type": "string"}}}),
        MockToolDef("get_issue", "Get issue info", {"type": "object", "properties": {"issue_id": {"type": "integer"}}})
    ]
    mock_session.list_tools.return_value = MockToolsList(tool_defs)
    mock_session.call_tool.return_value = MockCallResult("Result of search")

    # Mock stdio_client
    class MockContextManager:
        async def __aenter__(self):
            return ("read", "write")
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("mcp.client.stdio.stdio_client", lambda params: MockContextManager())

    # Mock ClientSession
    class MockSessionContextManager:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("mcp.ClientSession", lambda read, write: MockSessionContextManager())

    # Create mock configurations
    mock_cfg = MagicMock()
    mock_cfg.type = "stdio"
    mock_cfg.command = "python"
    mock_cfg.args = []
    mock_cfg.env = {}
    mock_cfg.enabled_tools = ["*"]
    mock_cfg.tool_timeout = 10

    mcp_servers = {"github": mock_cfg}
    registry = SkillVault()

    async with AsyncExitStack() as stack:
        await connect_mcp_servers(mcp_servers, registry, stack)

    # Check if tools are registered
    assert registry.has("mcp_github_search_code")
    assert registry.has("mcp_github_get_issue")
    assert registry.has("mcp_list_tools")
    assert registry.has("mcp_call_tool")

    # Try executing the dynamic tool
    result = await registry.execute("mcp_github_search_code", {"query": "hello"})
    assert result == "Result of search"
    mock_session.call_tool.assert_called_once_with("search_code", arguments={"query": "hello"})

    # Test reconfiguration recovery
    new_registry = SkillVault()
    assert not new_registry.has("mcp_github_search_code")

    register_active_mcp_tools(new_registry)
    assert new_registry.has("mcp_github_search_code")
    assert new_registry.has("mcp_github_get_issue")
    assert new_registry.has("mcp_list_tools")
    assert new_registry.has("mcp_call_tool")

    clear_mcp_sessions()


@pytest.mark.asyncio
async def test_mcp_execute_cancelled_propagation():
    import asyncio
    clear_mcp_sessions()

    mock_session = AsyncMock()
    mock_session.call_tool.side_effect = asyncio.CancelledError()

    _mcp_sessions["github"] = mock_session

    mock_cfg = MagicMock()
    mock_cfg.enabled_tools = ["*"]
    mock_cfg.tool_timeout = 10
    _mcp_configs["github"] = mock_cfg

    call_tool = MCPCallTool()

    with pytest.raises(asyncio.CancelledError):
        await call_tool.execute(server_name="github", tool_name="search_code", arguments={"query": "test"})

    clear_mcp_sessions()


@pytest.mark.asyncio
async def test_mcp_incremental_connect(monkeypatch):
    from shibaclaw.agent.tools.registry import SkillVault
    from shibaclaw.agent.tools.mcp import connect_mcp_servers, _mcp_sessions, clear_mcp_sessions
    from contextlib import AsyncExitStack

    clear_mcp_sessions()

    mock_stdio_enter_count = 0
    class MockContextManager:
        async def __aenter__(self):
            nonlocal mock_stdio_enter_count
            mock_stdio_enter_count += 1
            return ("read", "write")
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("mcp.client.stdio.stdio_client", lambda params: MockContextManager())

    mock_session = AsyncMock()
    mock_session.list_tools.return_value = MockToolsList([])
    class MockSessionContextManager:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("mcp.ClientSession", lambda read, write: MockSessionContextManager())

    cfg_github = MagicMock()
    cfg_github.type = "stdio"
    cfg_github.command = "python"
    cfg_github.args = []
    cfg_github.env = {}
    cfg_github.enabled_tools = ["*"]
    cfg_github.tool_timeout = 10

    mcp_servers_1 = {"github": cfg_github}
    registry = SkillVault()

    async with AsyncExitStack() as stack:
        await connect_mcp_servers(mcp_servers_1, registry, stack)
        
        assert "github" in _mcp_sessions
        assert mock_stdio_enter_count == 1

        cfg_slack = MagicMock()
        cfg_slack.type = "stdio"
        cfg_slack.command = "node"
        cfg_slack.args = []
        cfg_slack.env = {}
        cfg_slack.enabled_tools = ["*"]
        cfg_slack.tool_timeout = 10

        mcp_servers_2 = {"github": cfg_github, "slack": cfg_slack}
        await connect_mcp_servers(mcp_servers_2, registry, stack)

        assert "github" in _mcp_sessions
        assert "slack" in _mcp_sessions
        assert mock_stdio_enter_count == 2

        mcp_servers_3 = {"slack": cfg_slack}
        await connect_mcp_servers(mcp_servers_3, registry, stack)

        assert "github" not in _mcp_sessions
        assert "slack" in _mcp_sessions
        assert mock_stdio_enter_count == 2

    clear_mcp_sessions()


@pytest.mark.asyncio
async def test_mcp_self_healing_reconnect(monkeypatch):
    from shibaclaw.agent.tools.registry import SkillVault
    from shibaclaw.agent.tools.mcp import (
        connect_mcp_servers,
        MCPCallTool,
        clear_mcp_sessions,
    )
    from contextlib import AsyncExitStack
    from anyio import ClosedResourceError

    clear_mcp_sessions()

    # Mock stdio client entry count
    stdio_enters = 0
    class MockContextManager:
        async def __aenter__(self):
            nonlocal stdio_enters
            stdio_enters += 1
            return ("read", "write")
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("mcp.client.stdio.stdio_client", lambda params: MockContextManager())

    # Mock ClientSession
    mock_session_1 = AsyncMock()
    mock_session_1.list_tools.return_value = MockToolsList([])
    mock_session_1.call_tool.side_effect = ClosedResourceError()

    mock_session_2 = AsyncMock()
    mock_session_2.list_tools.return_value = MockToolsList([])
    mock_session_2.call_tool.return_value = MockCallResult("Self healed success!")

    sessions = [mock_session_1, mock_session_2]
    session_idx = 0

    class MockSessionContextManager:
        async def __aenter__(self):
            nonlocal session_idx
            s = sessions[session_idx]
            session_idx = min(session_idx + 1, len(sessions) - 1)
            return s
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("mcp.ClientSession", lambda read, write: MockSessionContextManager())

    cfg = MagicMock()
    cfg.type = "stdio"
    cfg.command = "python"
    cfg.args = []
    cfg.env = {}
    cfg.enabled_tools = ["*"]
    cfg.tool_timeout = 10

    registry = SkillVault()

    async with AsyncExitStack() as stack:
        await connect_mcp_servers({"github": cfg}, registry, stack)

        call_tool = MCPCallTool()
        res = await call_tool.execute(server_name="github", tool_name="search_code")
        assert "Self healed success!" in res
        assert stdio_enters == 2

    clear_mcp_sessions()


