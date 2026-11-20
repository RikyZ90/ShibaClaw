"""MCP Server Manager API routes for ShibaClaw WebUI."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from typing import Any

import httpx

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from shibaclaw.webui.agent_manager import agent_manager


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_mcp_servers(cfg: Any) -> dict:
    """Return the mcpServers dict from config, normalised."""
    try:
        tools = cfg.tools
        if tools:
            if hasattr(tools, "mcp_servers") and tools.mcp_servers:
                return tools.mcp_servers
            if hasattr(tools, "mcpServers") and tools.mcpServers:
                return tools.mcpServers
            if hasattr(tools, "model_extra") and tools.model_extra:
                return tools.model_extra.get("mcp_servers") or tools.model_extra.get("mcpServers") or {}
    except Exception:
        pass
    return {}



def _cfg_to_dict(cfg: Any) -> dict:
    """Best-effort serialise a pydantic/dict config to plain dict."""
    if cfg is None:
        return {}
    try:
        return cfg.model_dump(mode="json", exclude_none=False)
    except Exception:
        pass
    try:
        return dict(cfg)
    except Exception:
        return {}


# ── route handlers ────────────────────────────────────────────────────────────

async def list_mcp_servers(request: Request) -> JSONResponse:
    """GET /api/mcp/servers – return all configured MCP servers."""
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    servers = _get_mcp_servers(cfg)
    result = []
    for name, sc in servers.items():
        entry = dict(sc) if isinstance(sc, dict) else _cfg_to_dict(sc)
        entry["_name"] = name
        result.append(entry)
    return JSONResponse({"servers": result})


async def get_mcp_server(request: Request) -> JSONResponse:
    """GET /api/mcp/servers/{name} – return a single server config."""
    name = request.path_params["name"]
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    servers = _get_mcp_servers(cfg)
    if name not in servers:
        return JSONResponse({"error": f"Server '{name}' not found"}, status_code=404)
    sc = servers[name]
    entry = dict(sc) if isinstance(sc, dict) else _cfg_to_dict(sc)
    entry["_name"] = name
    return JSONResponse({"server": entry})


async def upsert_mcp_server(request: Request) -> JSONResponse:
    """PUT /api/mcp/servers/{name} – create or replace a server config."""
    name = request.path_params["name"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    # Strip internal fields
    body.pop("_name", None)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config

    cfg_dict = _cfg_to_dict(cfg)
    if "tools" not in cfg_dict or cfg_dict["tools"] is None:
        cfg_dict["tools"] = {}
    
    tools = cfg_dict["tools"]
    if "mcp_servers" not in tools and "mcpServers" not in tools:
        tools["mcp_servers"] = {}
    
    servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
    if tools.get(servers_key) is None:
        tools[servers_key] = {}
        
    tools[servers_key][name] = body

    try:
        from shibaclaw.config.schema import Config
        from shibaclaw.config.loader import save_config

        new_cfg = Config.model_validate(cfg_dict)
        save_config(new_cfg)
        await agent_manager.reload_config(new_cfg)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"ok": True, "name": name})


async def delete_mcp_server(request: Request) -> JSONResponse:
    """DELETE /api/mcp/servers/{name} – remove a server."""
    name = request.path_params["name"]
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config

    cfg_dict = _cfg_to_dict(cfg)
    tools = cfg_dict.get("tools", {})
    servers = tools.get("mcp_servers") or tools.get("mcpServers") or {}
    if name not in servers:
        return JSONResponse({"error": f"Server '{name}' not found"}, status_code=404)

    del servers[name]
    servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
    tools[servers_key] = servers
    cfg_dict["tools"] = tools

    try:
        from shibaclaw.config.schema import Config
        from shibaclaw.config.loader import save_config

        new_cfg = Config.model_validate(cfg_dict)
        save_config(new_cfg)
        await agent_manager.reload_config(new_cfg)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"ok": True})


async def rename_mcp_server(request: Request) -> JSONResponse:
    """PATCH /api/mcp/servers/{name}/rename – rename a server."""
    old_name = request.path_params["name"]
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    new_name = (body.get("new_name") or "").strip()
    if not new_name:
        return JSONResponse({"error": "new_name is required"}, status_code=400)

    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config

    cfg_dict = _cfg_to_dict(cfg)
    tools = cfg_dict.get("tools", {})
    servers = tools.get("mcp_servers") or tools.get("mcpServers") or {}
    if old_name not in servers:
        return JSONResponse({"error": f"Server '{old_name}' not found"}, status_code=404)
    if new_name in servers and new_name != old_name:
        return JSONResponse({"error": f"Server '{new_name}' already exists"}, status_code=409)

    servers[new_name] = servers.pop(old_name)
    servers_key = "mcp_servers" if "mcp_servers" in tools else "mcpServers"
    tools[servers_key] = servers
    cfg_dict["tools"] = tools

    try:
        from shibaclaw.config.schema import Config
        from shibaclaw.config.loader import save_config

        new_cfg = Config.model_validate(cfg_dict)
        save_config(new_cfg)
        await agent_manager.reload_config(new_cfg)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"ok": True, "new_name": new_name})


_MCP_TEST_TIMEOUT = 10.0


def _probe_category(exc: Exception, stage: str) -> str:
    """Classify nested SDK failures without exposing exception text."""
    from mcp.shared.exceptions import McpError

    errors = [exc]
    seen = set()
    categories = set()
    while errors:
        error = errors.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        if isinstance(error, BaseExceptionGroup):
            errors.extend(error.exceptions)
        if error.__cause__ is not None:
            errors.append(error.__cause__)
        if isinstance(error, (TimeoutError, httpx.TimeoutException)) or (
            isinstance(error, McpError) and error.error.code == httpx.codes.REQUEST_TIMEOUT
        ):
            categories.add("timeout")
        if isinstance(error, httpx.HTTPStatusError) and error.response.status_code in (401, 403):
            categories.add("auth failure")
        if isinstance(error, (ConnectionRefusedError, httpx.ConnectError)):
            categories.add("connection refused")
    for category in ("timeout", "auth failure", "connection refused"):
        if category in categories:
            return category
    return stage


async def _raise_probe_stream_error(message: Any) -> None:
    """Raise transport and parser errors that the SDK logs and its default handler drops."""
    if isinstance(message, Exception):
        raise message


async def test_mcp_server(request: Request) -> JSONResponse:
    """POST /api/mcp/servers/{name}/test – initialize MCP and discover tools."""
    from mcp import ClientSession
    from shibaclaw.agent.tools.mcp import (
        _resolve_auth_headers, mcp_transport_type, open_mcp_transport,
    )
    from shibaclaw.config.schema import MCPServerConfig

    name = request.path_params["name"]
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    servers = _get_mcp_servers(cfg)
    if name not in servers:
        return JSONResponse({"error": f"Server '{name}' not found"}, status_code=404)

    transport = "unknown"
    stage = "MCP initialization failure"
    try:
        sc = servers[name]
        if isinstance(sc, dict):
            sc = MCPServerConfig.model_validate(sc)
        transport = mcp_transport_type(sc)
        # An OAuth server may open the browser login, as before; give it its callback time.
        limit = _MCP_TEST_TIMEOUT + (sc.oauth.callback_timeout if sc.oauth else 0.0)
        # Bound setup and cleanup on this task, so the SDK's cancel scopes enter and exit on one task.
        async with asyncio.timeout(limit):
            async with AsyncExitStack() as stack:
                stage = "auth failure"
                headers = await _resolve_auth_headers(name, sc)
                stage = "MCP initialization failure"
                read, write = await open_mcp_transport(
                    stack, name, sc, headers, request_timeout=_MCP_TEST_TIMEOUT,
                )
                session = await stack.enter_async_context(ClientSession(
                    read, write, message_handler=_raise_probe_stream_error,
                ))
                await session.initialize()
                stage = "tool discovery failure"
                await session.list_tools()
        return JSONResponse({
            "ok": True, "transport": transport, "category": "ready",
            "detail": "MCP initialized; tools discovered.",
        })
    except Exception as exc:
        category = _probe_category(exc, stage)
        messages = {
            "connection refused": "Connection refused.",
            "timeout": "MCP test timed out.",
            "auth failure": "Authentication failed.",
            "MCP initialization failure": "MCP initialization failed.",
            "tool discovery failure": "Tool discovery failed.",
        }
        return JSONResponse({
            "ok": False, "transport": transport, "category": category,
            "error": messages[category],
        })


# ── router registration ───────────────────────────────────────────────────────

routes = [
    Route("/api/mcp/servers", list_mcp_servers, methods=["GET"]),
    Route("/api/mcp/servers/{name}", get_mcp_server, methods=["GET"]),
    Route("/api/mcp/servers/{name}", upsert_mcp_server, methods=["PUT"]),
    Route("/api/mcp/servers/{name}", delete_mcp_server, methods=["DELETE"]),
    Route("/api/mcp/servers/{name}/rename", rename_mcp_server, methods=["PATCH"]),
    Route("/api/mcp/servers/{name}/test", test_mcp_server, methods=["POST"]),
]
