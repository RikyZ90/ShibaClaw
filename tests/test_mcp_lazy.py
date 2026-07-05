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
