from __future__ import annotations
import os
import uuid
import json
import asyncio
from typing import Any, Dict, List, Set, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse
from loguru import logger

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.auth import get_auth_token, _auth_enabled
from shibaclaw.webui.utils import _gateway_request, _gateway_post


async def api_cron_list(request: Request):
    """List all scheduled jobs via the gateway."""
    result = await _gateway_request("GET", "/api/cron/list")
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"jobs": [], "error": "gateway_unreachable"}, status_code=503)


async def api_cron_trigger(request: Request):
    """Trigger a cron job via the gateway."""
    job_id = request.path_params["job_id"]
    result = await _gateway_post(f"/api/cron/trigger/{job_id}", {})
    if result is not None:
        return JSONResponse(result)
    return JSONResponse({"error": "Gateway unreachable"}, status_code=503)
