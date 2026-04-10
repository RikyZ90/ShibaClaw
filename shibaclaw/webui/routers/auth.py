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
from shibaclaw.webui.auth import _auth_enabled, verify_token_value
from shibaclaw.brain.manager import PackManager


async def api_auth_verify(request: Request):
    """Verify an auth token."""
    data = await request.json()
    token = data.get("token", "").strip()
    auth_req = _auth_enabled()
    if not auth_req:
        return JSONResponse({"valid": True, "auth_required": False})
    if verify_token_value(token):
        return JSONResponse({"valid": True, "auth_required": True})
    return JSONResponse({"valid": False, "auth_required": True})


async def api_auth_status(request: Request):
    """Check if auth is enabled."""
    return JSONResponse({"auth_required": _auth_enabled()})
