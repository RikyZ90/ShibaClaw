"""MCP client: connects to MCP servers and wraps their tools as native shibaclaw tools."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

from anyio.abc import ObjectReceiveStream
import httpx
from loguru import logger

from shibaclaw.agent.tools.base import Tool
from shibaclaw.agent.tools.registry import SkillVault

class MCPWrappedTool(Tool):
    """Dynamically registers an individual tool from an MCP server as a native tool, with eager self-healing reconnect capabilities."""

    def __init__(self, server_name: str, tool_def: Any, session: Any, timeout: int = 30) -> None:
        self._server_name = server_name
        self._tool_name = tool_def.name
        self._name = f"mcp_{server_name}_{tool_def.name}"
        self._description = tool_def.description or f"Execute tool '{tool_def.name}' on MCP server '{server_name}'."
        self._parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._session = session
        self._timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._tool_name, arguments=kwargs),
                timeout=self._timeout if self._timeout > 0 else None,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "MCP tool '{}' on server '{}' timed out after {}s",
                self._tool_name,
                self._server_name,
                self._timeout,
            )
            return f"(MCP tool call timed out after {self._timeout}s)"
        except asyncio.CancelledError:
            logger.warning(
                "MCP tool '{}' on server '{}' was cancelled",
                self._tool_name,
                self._server_name,
            )
            raise
        except Exception as exc:
            # Check for connection or closed stream errors and try self-healing reconnect
            is_conn_err = False
            exc_type_name = type(exc).__name__
            if (
                "ClosedResource" in exc_type_name
                or "ConnectionError" in exc_type_name
                or "RequestError" in exc_type_name
                or "ClosedResource" in str(exc)
                or "EndOfStream" in exc_type_name
                or "EndOfStream" in str(exc)
            ):
                is_conn_err = True

            if is_conn_err:
                reconnected = await reconnect_server(self._server_name)
                if reconnected:
                    new_session = _mcp_sessions.get(self._server_name)
                    if new_session:
                        self._session = new_session
                        try:
                            result = await asyncio.wait_for(
                                self._session.call_tool(self._tool_name, arguments=kwargs),
                                timeout=self._timeout if self._timeout > 0 else None,
                            )
                            parts = []
                            for block in result.content:
                                if isinstance(block, types.TextContent):
                                    parts.append(block.text)
                                else:
                                    parts.append(str(block))
                            return "\n".join(parts) or "(no output)"
                        except Exception as retry_exc:
                            exc = retry_exc
                else:
                    raise MCPReconnectError(
                        f"Failed to reconnect to MCP server '{self._server_name}' after transport failure: {exc}"
                    )

            logger.exception(
                "MCP tool '{}' on server '{}' failed: {}: {}",
                self._tool_name,
                self._server_name,
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


# Global registry of active MCP sessions and configs
_mcp_sessions: dict[str, Any] = {}
_mcp_configs: dict[str, Any] = {}
_mcp_wrapped_tools: list[MCPWrappedTool] = []
_mcp_stacks: dict[str, AsyncExitStack] = {}
_parent_stack: AsyncExitStack | None = None
_registry: SkillVault | None = None
_mcp_cleanup_registered = False
_mcp_lock: asyncio.Lock | None = None

def _get_mcp_lock() -> asyncio.Lock:
    global _mcp_lock
    if _mcp_lock is None:
        _mcp_lock = asyncio.Lock()
    return _mcp_lock


class MCPReconnectError(Exception):
    """Raised when self-healing reconnection of an MCP server fails."""
    pass

class SafeReadStream(ObjectReceiveStream[Any]):
    """Wrapper around anyio receive stream that converts ClosedResourceError and other errors

    into graceful EndOfStream, and triggers a reconnect in the background.
    """
    def __init__(self, original_stream: Any, server_name: str) -> None:
        self._original_stream = original_stream
        self._server_name = server_name

    async def receive(self) -> Any:
        import anyio
        try:
            return await self._original_stream.receive()
        except (anyio.ClosedResourceError, anyio.EndOfStream):
            raise anyio.EndOfStream()
        except Exception as e:
            logger.warning(
                "Transport read error on MCP server '{}' (converting to EOF): {}",
                self._server_name,
                e,
            )
            # Trigger self-healing reconnect in the background
            asyncio.create_task(reconnect_server(self._server_name))
            raise anyio.EndOfStream()

    async def aclose(self) -> None:
        try:
            await self._original_stream.aclose()
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original_stream, name)


async def _close_all_mcp_stacks() -> None:
    global _mcp_cleanup_registered
    for name, server_stack in list(_mcp_stacks.items()):
        try:
            await server_stack.aclose()
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)
    _mcp_stacks.clear()
    _mcp_cleanup_registered = False


def _cfg_to_json(cfg: Any) -> Any:
    if cfg is None:
        return None
    if hasattr(cfg, "model_dump"):
        return cfg.model_dump(mode="json")
    if isinstance(cfg, dict):
        return cfg
    return str(cfg)


def _mcp_config_differ(cfg_a: Any, cfg_b: Any) -> bool:
    def _extract_connection_fields(cfg: Any) -> dict:
        if cfg is None:
            return {}
        cfg_dict = _cfg_to_json(cfg)
        return {
            k: cfg_dict.get(k)
            for k in ("type", "command", "args", "env", "url", "headers", "oauth")
        }
    return _extract_connection_fields(cfg_a) != _extract_connection_fields(cfg_b)


def clear_mcp_sessions() -> None:
    global _parent_stack, _registry, _mcp_cleanup_registered
    _mcp_sessions.clear()
    _mcp_configs.clear()
    _mcp_wrapped_tools.clear()
    _mcp_stacks.clear()
    _parent_stack = None
    _registry = None
    _mcp_cleanup_registered = False


async def reconnect_server(name: str) -> bool:
    """Attempt to reconnect a single MCP server by name."""
    global _parent_stack, _registry
    async with _get_mcp_lock():
        if not _parent_stack or not _registry:
            return False
        cfg = _mcp_configs.get(name)
        if not cfg:
            return False

        logger.info("Self-healing: Reconnecting MCP server '{}'...", name)
        try:
            server_stack = _mcp_stacks.pop(name, None)
            if server_stack:
                try:
                    await server_stack.aclose()
                except Exception as _e:
                    logger.debug("Ignored error: {}", _e)
            
            _mcp_sessions.pop(name, None)
            await _connect_mcp_servers_impl({name: cfg}, _registry, _parent_stack, is_reconfigure=False)
            return name in _mcp_sessions
        except Exception as e:
            logger.error("Self-healing reconnection failed for '{}': {}", name, e)
            return False


def register_active_mcp_tools(registry: SkillVault) -> None:
    """Register all active MCP tools and wrapper utilities to the registry."""
    if not _mcp_sessions:
        registry.unregister("mcp_list_tools")
        registry.unregister("mcp_call_tool")
        return
    registry.register(MCPListTools())
    registry.register(MCPCallTool())
    for tool in _mcp_wrapped_tools:
        registry.register(tool)


def get_mcp_servers_info() -> str:
    if not _mcp_sessions:
        return ""
    lines = []
    for name in sorted(_mcp_sessions.keys()):
        lines.append(f"- **{name}**: Use `mcp_list_tools(server_name=\"{name}\")` to see available tools.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# OAuth helper
# ---------------------------------------------------------------------------


async def _resolve_auth_headers(
    server_name: str,
    cfg: Any,  # MCPServerConfig
    *,
    interactive: bool = True,
) -> dict[str, str]:
    """
    Return the headers dict to use for this server, injecting a dynamic
    ``Authorization: Bearer <token>`` when an OAuth config is present.

    Falls back transparently to ``cfg.headers`` for non-OAuth servers,
    preserving 100 % backward compatibility.
    """
    base_headers: dict[str, str] = dict(cfg.headers or {})

    if cfg.oauth is None:
        return base_headers

    from shibaclaw.security.oauth_flow import OAuthFlow
    from shibaclaw.security.oauth_store import OAuthTokenStore

    store = OAuthTokenStore()
    flow = OAuthFlow(store=store)

    try:
        token_data = await flow.get_valid_token(
            server_name,
            cfg.oauth,
            callback_timeout=cfg.oauth.callback_timeout,
            interactive=interactive,
        )
    except Exception as exc:
        raise RuntimeError(
            f"MCP server '{server_name}': OAuth authentication failed: {exc}"
        ) from exc

    access_token = token_data.get("access_token", "")
    # Dynamic Authorization header overrides any static one in cfg.headers
    return {**base_headers, "Authorization": f"Bearer {access_token}"}


# ---------------------------------------------------------------------------
# SSRF hook factory
# ---------------------------------------------------------------------------


def _make_ssrf_hook(origin_url: str):
    """Return an httpx request hook that blocks SSRF redirects.

    The ``origin_url`` is captured by value in the closure so that iterating
    over multiple MCP servers in a loop never causes hooks to share state.
    Only redirect targets that leave the origin are validated; the original
    configured URL is always trusted (it may be localhost).
    """
    from shibaclaw.security.network import validate_resolved_url

    _origin = origin_url.rstrip("/")

    async def _ssrf_hook(request: httpx.Request) -> None:
        req_url = str(request.url).rstrip("/")
        # Allow requests that stay on the configured origin
        if (
            req_url == _origin
            or req_url.startswith(_origin + "/")
            or req_url.startswith(_origin + "?")
        ):
            return
        redir_ok, redir_err = await asyncio.to_thread(validate_resolved_url, req_url)
        if not redir_ok:
            raise httpx.RequestError(
                f"Redirect blocked: {redir_err}", request=request
            )

    return _ssrf_hook


def _make_oauth_hook(server_name: str, cfg: Any):
    """Return an httpx request hook that refreshes and injects OAuth headers."""
    if cfg.oauth is None:
        return None

    async def _oauth_hook(request: httpx.Request) -> None:
        try:
            auth_headers = await _resolve_auth_headers(server_name, cfg, interactive=False)
            if "Authorization" in auth_headers:
                request.headers["Authorization"] = auth_headers["Authorization"]
        except Exception as exc:
            logger.warning(
                "MCP server '{}': OAuth token refresh failed: {}",
                server_name,
                exc,
            )

    return _oauth_hook


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


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
                timeout=timeout if timeout > 0 else None,
            )
        except asyncio.TimeoutError:
            logger.warning("MCP tool '{}' on server '{}' timed out after {}s", tool_name, server_name, timeout)
            return f"(MCP tool call timed out after {timeout}s)"
        except asyncio.CancelledError:
            logger.warning("MCP tool '{}' on server '{}' was cancelled", tool_name, server_name)
            raise
        except Exception as exc:
            # Check for connection or closed stream errors and try self-healing reconnect
            is_conn_err = False
            exc_type_name = type(exc).__name__
            if (
                "ClosedResource" in exc_type_name
                or "ConnectionError" in exc_type_name
                or "RequestError" in exc_type_name
                or "ClosedResource" in str(exc)
            ):
                is_conn_err = True

            if is_conn_err:
                reconnected = await reconnect_server(server_name)
                if reconnected:
                    new_session = _mcp_sessions.get(server_name)
                    if new_session:
                        session = new_session
                        try:
                            result = await asyncio.wait_for(
                                session.call_tool(tool_name, arguments=args),
                                timeout=timeout,
                            )
                            parts = []
                            for block in result.content:
                                if isinstance(block, types.TextContent):
                                    parts.append(block.text)
                                else:
                                    parts.append(str(block))
                            return "\n".join(parts) or "(no output)"
                        except Exception as retry_exc:
                            exc = retry_exc

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


# ---------------------------------------------------------------------------
# Connection bootstrap
# ---------------------------------------------------------------------------


async def connect_mcp_servers(
    mcp_servers: dict,
    registry: SkillVault,
    stack: AsyncExitStack,
    *,
    is_reconfigure: bool = True,
) -> None:
    """Connect to configured MCP servers and register their sessions (thread-safe entry)."""
    async with _get_mcp_lock():
        await _connect_mcp_servers_impl(
            mcp_servers, registry, stack, is_reconfigure=is_reconfigure
        )


async def _connect_mcp_servers_impl(
    mcp_servers: dict,
    registry: SkillVault,
    stack: AsyncExitStack,
    *,
    is_reconfigure: bool = True,
) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    global _parent_stack, _registry, _mcp_cleanup_registered
    _parent_stack = stack
    _registry = registry

    if not _mcp_cleanup_registered:
        stack.push_async_callback(_close_all_mcp_stacks)
        _mcp_cleanup_registered = True

    if is_reconfigure:
        # 1. Identify servers to remove (either not in new config, or configuration changed)
        to_remove = []
        for name in list(_mcp_sessions.keys()):
            if name not in mcp_servers:
                to_remove.append(name)
            elif _mcp_config_differ(_mcp_configs.get(name), mcp_servers[name]):
                to_remove.append(name)

        # 2. Close and clean up removed servers
        for name in to_remove:
            logger.info("Disconnecting MCP server '{}'...", name)
            _mcp_sessions.pop(name, None)
            _mcp_configs.pop(name, None)

            # Remove wrapped tools from registry
            for tool in list(_mcp_wrapped_tools):
                if tool._server_name == name:
                    registry.unregister(tool.name)
            _mcp_wrapped_tools[:] = [t for t in _mcp_wrapped_tools if t._server_name != name]

            server_stack = _mcp_stacks.pop(name, None)
            if server_stack:
                try:
                    await server_stack.aclose()
                except Exception as e:
                    logger.warning("Error closing stack for MCP server '{}': {}", name, e)

        # Clean up wrapper tools from registry if no sessions left
        if not _mcp_sessions:
            registry.unregister("mcp_list_tools")
            registry.unregister("mcp_call_tool")

    # Resolve all auth headers concurrently to eliminate O(n) OAuth latency
    auth_headers_map = {}
    async def resolve_auth(name: str, cfg: Any) -> None:
        if name in _mcp_sessions:
            return
        try:
            auth_headers_map[name] = await _resolve_auth_headers(name, cfg, interactive=False)
        except Exception as e:
            logger.error("Failed to resolve auth headers for MCP server '{}': {}", name, e)
            auth_headers_map[name] = {}

    to_connect = [name for name in mcp_servers if name not in _mcp_sessions]
    if to_connect:
        await asyncio.gather(*(resolve_auth(name, mcp_servers[name]) for name in to_connect))

    connected_any = bool(_mcp_sessions)

    # Connect sequentially to ensure anyio task-binding of cancel scopes remains on _mcp_worker
    for name in to_connect:
        cfg = mcp_servers[name]
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

            logger.info("Connecting to MCP server '{}' (transport: {})...", name, transport_type)
            server_stack = AsyncExitStack()
            await server_stack.__aenter__()
            _mcp_stacks[name] = server_stack

            if transport_type == "stdio":
                params = StdioServerParameters(
                    command=cfg.command, args=cfg.args, env=cfg.env or None
                )
                read, write = await server_stack.enter_async_context(stdio_client(params))

            elif transport_type == "sse":
                auth_headers = auth_headers_map.get(name, {})
                oauth_hook = _make_oauth_hook(name, cfg)

                def _make_httpx_client_factory(
                    resolved_headers: dict[str, str],
                    origin_url: str,
                    oauth_hook: Any | None = None,
                ) -> Any:
                    _ssrf = _make_ssrf_hook(origin_url)
                    hooks = [_ssrf]
                    if oauth_hook:
                        hooks.append(oauth_hook)

                    def httpx_client_factory(
                        headers: dict[str, str] | None = None,
                        timeout: httpx.Timeout | None = None,
                        auth: httpx.Auth | None = None,
                    ) -> httpx.AsyncClient:
                        merged_headers = {**resolved_headers, **(headers or {})}
                        if timeout is None:
                            timeout = httpx.Timeout(connect=40.0, read=40.0, write=40.0, pool=40.0)
                        return httpx.AsyncClient(
                            headers=merged_headers or None,
                            follow_redirects=True,
                            timeout=timeout,
                            auth=auth,
                            event_hooks={"request": hooks},
                        )
                    return httpx_client_factory

                read, write = await server_stack.enter_async_context(
                    sse_client(cfg.url, httpx_client_factory=_make_httpx_client_factory(auth_headers, cfg.url, oauth_hook))
                )

            elif transport_type == "streamableHttp":
                auth_headers = auth_headers_map.get(name, {})
                oauth_hook = _make_oauth_hook(name, cfg)
                hooks = [_make_ssrf_hook(cfg.url)]
                if oauth_hook:
                    hooks.append(oauth_hook)

                connect_timeout = getattr(cfg, "tool_timeout", 30) + 10

                http_client = await server_stack.enter_async_context(
                    httpx.AsyncClient(
                        headers=auth_headers or None,
                        follow_redirects=True,
                        timeout=httpx.Timeout(connect=connect_timeout, read=connect_timeout, write=connect_timeout, pool=connect_timeout),
                        event_hooks={"request": hooks},
                    )
                )
                read, write, _ = await server_stack.enter_async_context(
                    streamable_http_client(cfg.url, http_client=http_client)
                )

            else:
                logger.warning("MCP server '{}': unknown transport type '{}'", name, transport_type)
                _mcp_stacks.pop(name, None)
                await server_stack.aclose()
                continue

            # Wrap stream in SafeReadStream to prevent unhandled background crashes
            safe_read = SafeReadStream(read, name)
            session = await server_stack.enter_async_context(ClientSession(safe_read, write))
            await session.initialize()

            _mcp_sessions[name] = session
            _mcp_configs[name] = cfg
            logger.info("MCP server '{}': connected and session registered", name)
            connected_any = True

            # Dynamically register tools from the server as native tools
            try:
                tools_list = await session.list_tools()
                enabled_tools = set(cfg.enabled_tools) if cfg and hasattr(cfg, "enabled_tools") else {"*"}
                allow_all = "*" in enabled_tools
                for tool_def in tools_list.tools:
                    wrapped_name = f"mcp_{name}_{tool_def.name}"
                    if not allow_all and tool_def.name not in enabled_tools and wrapped_name not in enabled_tools:
                        continue

                    wrapped_tool = MCPWrappedTool(
                        server_name=name,
                        tool_def=tool_def,
                        session=session,
                        timeout=getattr(cfg, "tool_timeout", 30),
                    )
                    _mcp_wrapped_tools.append(wrapped_tool)
                    logger.debug("Registered MCP tool '{}' as native tool '{}'", tool_def.name, wrapped_name)
            except Exception as e:
                logger.error("Failed to list and register tools for MCP server '{}': {}", name, e)

        except Exception as e:
            logger.error("MCP server '{}': failed to connect: {}", name, e)
            _mcp_stacks.pop(name, None)
            try:
                await server_stack.aclose()
            except Exception as _e:
                logger.debug("Ignored error: {}", _e)

    if connected_any:
        register_active_mcp_tools(registry)
