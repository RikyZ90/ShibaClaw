"""MCP client: connects to MCP servers and wraps their tools as native shibaclaw tools."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

import httpx
from loguru import logger

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.registry import SkillVault

# Global registry of active MCP sessions and configs
_mcp_sessions: dict[str, Any] = {}
_mcp_configs: dict[str, Any] = {}


def clear_mcp_sessions() -> None:
    _mcp_sessions.clear()
    _mcp_configs.clear()


def get_mcp_servers_info() -> str:
    if not _mcp_sessions:
        return ""
    lines = []
    for name in sorted(_mcp_sessions.keys()):
        lines.append(f"- **{name}**: Use `mcp_list_tools(server_name=\"{name}\")` to see available tools.")
    return "\n".join(lines)


class MCPListTools(Tool):
    """List available tools on a connected MCP server."""

    def __init__(self) -> None:
        self._name = "mcp_list_tools"
        self._description = "List all tools and their parameter schemas available on a specific connected MCP server."
        self._parameters = {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "Name of the MCP server to inspect."
                }
            },
            "required": ["server_name"]
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, server_name: str) -> str:
        session = _mcp_sessions.get(server_name)
        if not session:
            available = ", ".join(_mcp_sessions.keys())
            return f"Error: MCP server '{server_name}' is not connected. Connected servers: {available or '(none)'}"

        cfg = _mcp_configs.get(server_name)
        enabled_tools = set(cfg.enabled_tools) if cfg else {"*"}
        allow_all = "*" in enabled_tools

        try:
            tools = await session.list_tools()
            lines = [f"Tools available on MCP server '{server_name}':"]
            for tool_def in tools.tools:
                wrapped_name = f"mcp_{server_name}_{tool_def.name}"
                if not allow_all and tool_def.name not in enabled_tools and wrapped_name not in enabled_tools:
                    continue
                lines.append(f"- Name: {tool_def.name}")
                if tool_def.description:
                    lines.append(f"  Description: {tool_def.description}")
                lines.append(f"  Schema: {tool_def.inputSchema}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing tools for MCP server '{server_name}': {str(e)}"


class MCPCallTool(Tool):
    """Execute a tool on a connected MCP server."""

    def __init__(self) -> None:
        self._name = "mcp_call_tool"
        self._description = "Execute a tool on an MCP server with the specified arguments."
        self._parameters = {
            "type": "object",
            "properties": {
                "server_name": {
                    "type": "string",
                    "description": "Name of the MCP server."
                },
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool to execute."
                },
                "arguments": {
                    "type": "object",
                    "description": "Key-value arguments to pass to the tool."
                }
            },
            "required": ["server_name", "tool_name"]
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, server_name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> str:
        from mcp import types
        session = _mcp_sessions.get(server_name)
        if not session:
            available = ", ".join(_mcp_sessions.keys())
            return f"Error: MCP server '{server_name}' is not connected. Connected servers: {available or '(none)'}"

        cfg = _mcp_configs.get(server_name)
        enabled_tools = set(cfg.enabled_tools) if cfg else {"*"}
        allow_all = "*" in enabled_tools
        wrapped_name = f"mcp_{server_name}_{tool_name}"

        if not allow_all and tool_name not in enabled_tools and wrapped_name not in enabled_tools:
            return f"Error: Tool '{tool_name}' is not enabled on MCP server '{server_name}'."

        args = arguments or {}
        timeout = cfg.tool_timeout if cfg else 30
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments=args),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' on server '{}' timed out after {}s", tool_name, server_name, timeout)
            return f"(MCP tool call timed out after {timeout}s)"
        except asyncio.CancelledError:
            task = asyncio.current_task()
            if task is not None and task.cancelling() > 0:
                raise
            logger.warning("MCP tool '{}' on server '{}' was cancelled", tool_name, server_name)
            return "(MCP tool call was cancelled)"
        except Exception as exc:
            logger.exception(
                "MCP tool '{}' on server '{}' failed: {}: {}",
                tool_name,
                server_name,
                type(exc).__name__,
                exc,
            )
            return f"(MCP tool call failed: {type(exc).__name__})"

        parts = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts) or "(no output)"


async def connect_mcp_servers(
    mcp_servers: dict, registry: SkillVault, stack: AsyncExitStack
) -> None:
    """Connect to configured MCP servers and register their sessions."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    clear_mcp_sessions()

    connected_any = False
    for name, cfg in mcp_servers.items():
        try:
            transport_type = cfg.type
            if not transport_type:
                if cfg.command:
                    transport_type = "stdio"
                elif cfg.url:
                    transport_type = (
                        "sse" if cfg.url.rstrip("/").endswith("/sse") else "streamableHttp"
                    )
                else:
                    logger.warning("MCP server '{}': no command or url configured, skipping", name)
                    continue

            if transport_type == "stdio":
                params = StdioServerParameters(
                    command=cfg.command, args=cfg.args, env=cfg.env or None
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            elif transport_type == "sse":

                def httpx_client_factory(
                    headers: dict[str, str] | None = None,
                    timeout: httpx.Timeout | None = None,
                    auth: httpx.Auth | None = None,
                ) -> httpx.AsyncClient:
                    from shibaclaw.security.network import validate_resolved_url

                    async def _ssrf_hook(request: httpx.Request):
                        redir_ok, redir_err = validate_resolved_url(str(request.url))
                        if not redir_ok:
                            raise httpx.RequestError(f"Redirect blocked: {redir_err}", request=request)

                    merged_headers = {**(cfg.headers or {}), **(headers or {})}
                    return httpx.AsyncClient(
                        headers=merged_headers or None,
                        follow_redirects=True,
                        timeout=timeout,
                        auth=auth,
                        event_hooks={"request": [_ssrf_hook]},
                    )

                read, write = await stack.enter_async_context(
                    sse_client(cfg.url, httpx_client_factory=httpx_client_factory)
                )
            elif transport_type == "streamableHttp":
                from shibaclaw.security.network import validate_resolved_url

                async def _ssrf_hook(request: httpx.Request):
                    redir_ok, redir_err = validate_resolved_url(str(request.url))
                    if not redir_ok:
                        raise httpx.RequestError(f"Redirect blocked: {redir_err}", request=request)

                http_client = await stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=cfg.headers or None,
                        follow_redirects=True,
                        timeout=None,
                        event_hooks={"request": [_ssrf_hook]},
                    )
                )
                read, write, _ = await stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )
            else:
                logger.warning("MCP server '{}': unknown transport type '{}'", name, transport_type)
                continue

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            _mcp_sessions[name] = session
            _mcp_configs[name] = cfg
            logger.info("MCP server '{}': connected and session registered", name)
            connected_any = True
        except Exception as e:
            logger.error("MCP server '{}': failed to connect: {}", name, e)

    if connected_any:
        registry.register(MCPListTools())
        registry.register(MCPCallTool())
