"""MCP Server Manager API routes for ShibaClaw WebUI."""

from __future__ import annotations

import asyncio
from typing import Any

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


async def test_mcp_server(request: Request) -> JSONResponse:
    """POST /api/mcp/servers/{name}/test – quick connectivity probe."""
    name = request.path_params["name"]
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    servers = _get_mcp_servers(cfg)
    if name not in servers:
        return JSONResponse({"error": f"Server '{name}' not found"}, status_code=404)

    sc = servers[name]
    sc_dict = dict(sc) if isinstance(sc, dict) else _cfg_to_dict(sc)
    server_type = sc_dict.get("type") or "stdio"
    url = sc_dict.get("url") or ""
    command = sc_dict.get("command") or ""
    args = sc_dict.get("args") or []
    env_vars: dict = sc_dict.get("env") or {}

    import os
    probe_env = {**os.environ, **{str(k): str(v) for k, v in env_vars.items()}}

    # SSE / streamableHttp – just do a HEAD/GET to the URL
    if server_type in ("sse", "streamableHttp") or (url and not command):
        if not url:
            return JSONResponse({"ok": False, "error": "No URL configured for HTTP server"})
        try:
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
            return JSONResponse({"ok": True, "detail": f"HTTP {status} from {url}"})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)})

    # stdio – try to spawn and read first bytes
    if not command:
        return JSONResponse({"ok": False, "error": "No command configured"})
    cmd = [command] + [str(a) for a in args]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=probe_env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=6)
        except asyncio.TimeoutError:
            proc.kill()
            # Timeout just means it's running and waiting for stdin – that's fine
            return JSONResponse({"ok": True, "detail": "Process started successfully (stdio, waiting for input)"})
        rc = proc.returncode
        if rc == 0 or (stdout and len(stdout) > 0):
            return JSONResponse({"ok": True, "detail": "Process exited cleanly"})
        err_text = (stderr or b"").decode(errors="replace")[:400]
        return JSONResponse({"ok": False, "error": f"Exit code {rc}: {err_text}"})
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": f"Command not found: {command}"})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


# ── router registration ───────────────────────────────────────────────────────

routes = [
    Route("/api/mcp/servers", list_mcp_servers, methods=["GET"]),
    Route("/api/mcp/servers/{name}", get_mcp_server, methods=["GET"]),
    Route("/api/mcp/servers/{name}", upsert_mcp_server, methods=["PUT"]),
    Route("/api/mcp/servers/{name}", delete_mcp_server, methods=["DELETE"]),
    Route("/api/mcp/servers/{name}/rename", rename_mcp_server, methods=["PATCH"]),
    Route("/api/mcp/servers/{name}/test", test_mcp_server, methods=["POST"]),
]
