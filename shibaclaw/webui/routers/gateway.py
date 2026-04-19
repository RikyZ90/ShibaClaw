from __future__ import annotations

import asyncio
import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.auth import get_auth_token
from shibaclaw.webui.gateway_client import gateway_client
from shibaclaw.webui.utils import _resolve_gateway_hosts


async def api_gateway_health(request: Request):
    """Proxy health check to the gateway, preferring WebSocket when available."""
    # Try WebSocket first
    if gateway_client.connected:
        result = await gateway_client.request("status")
        if result is not None:
            return JSONResponse({"reachable": True, **result})

    # Fallback: raw HTTP
    hosts, port = _resolve_gateway_hosts()
    if not hosts:
        return JSONResponse({"reachable": False, "reason": "no_config"})

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=3.0
            )
            try:
                writer.write(b"GET /health HTTP/1.0\r\nHost: health\r\n\r\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.read(1024), timeout=2.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    try:
                        info = json.loads(data[body_start + 4 :])
                        return JSONResponse({"reachable": True, **info})
                    except Exception:
                        pass
                return JSONResponse({"reachable": True})
        except Exception:
            continue

    # No gateway found and no local agent — system is offline
    return JSONResponse({"reachable": False, "reason": "unreachable"})


async def api_gateway_restart(request: Request):
    """Proxy restart command to the gateway."""
    # Try WebSocket first
    if gateway_client.connected:
        result = await gateway_client.request("restart")
        if result is not None:
            await agent_manager.reset_agent()
            return JSONResponse({"status": "restarting"})

    # Fallback: raw HTTP
    hosts, port = _resolve_gateway_hosts()
    if not hosts:
        return JSONResponse({"error": "No config"}, status_code=400)

    auth_token = get_auth_token()
    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            try:
                auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""
                writer.write(f"POST /restart HTTP/1.0\r\nHost: gw\r\n{auth_hdr}\r\n".encode())
                await writer.drain()
                data = await asyncio.wait_for(reader.read(512), timeout=2.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                await agent_manager.reset_agent()
                return JSONResponse({"status": "restarting"})
        except Exception:
            continue
    return JSONResponse({"error": "Gateway unreachable"}, status_code=503)
