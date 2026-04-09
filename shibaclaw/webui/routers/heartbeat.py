from __future__ import annotations
import os
import uuid
import json
import asyncio
import urllib.parse
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from loguru import logger

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.auth import get_auth_token, _auth_enabled
from shibaclaw.brain.manager import PackManager

from shibaclaw.webui.utils import _resolve_gateway_hosts, _gateway_request


async def api_heartbeat_status(request: Request):
    """Proxy heartbeat status from the gateway, fall back to local service."""
    result = await _gateway_request("GET", "/heartbeat/status")
    if result is not None:
        return JSONResponse({"reachable": True, **result})
    if agent_manager.heartbeat:
        return JSONResponse({"reachable": True, **agent_manager.heartbeat.status()})
    return JSONResponse({"reachable": False, "reason": "gateway_unreachable"})


async def api_heartbeat_trigger(request: Request):
    """Proxy heartbeat trigger to the gateway, fall back to local service."""
    result = await _gateway_request("POST", "/heartbeat/trigger")
    if result is not None:
        return JSONResponse(result)
    if agent_manager.heartbeat:
        try:
            resp = await agent_manager.heartbeat.trigger_now()
            return JSONResponse({"triggered": True, "response": resp})
        except Exception as e:
            return JSONResponse({"triggered": False, "error": str(e)})
    return JSONResponse({"error": "Gateway unreachable"}, status_code=503)
