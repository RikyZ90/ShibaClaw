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


async def api_sessions_list(request: Request):
    """List all saved sessions."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    pm = PackManager(agent_manager.config.workspace_path)
    return JSONResponse({"sessions": pm.list_sessions()})


async def api_sessions_get(request: Request):
    """Get details for a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    pm = PackManager(agent_manager.config.workspace_path)
    session = pm.get_or_create(session_id)
    return JSONResponse({
        "messages": session.messages,
        "nickname": session.metadata.get("nickname"),
        "profile_id": session.metadata.get("profile_id", "default"),
    })


async def api_sessions_patch(request: Request):
    """Update session metadata (like nickname)."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    data = await request.json()
    pm = PackManager(agent_manager.config.workspace_path)
    session = pm.get_or_create(session_id)
    
    if "nickname" in data:
        session.metadata["nickname"] = data["nickname"]
    if "profile_id" in data:
        session.metadata["profile_id"] = data["profile_id"]
    if "nickname" in data or "profile_id" in data:
        pm.save(session)
        return JSONResponse({"status": "updated", "profile_id": session.metadata.get("profile_id", "default")})
    return JSONResponse({"error": "Nothing to update"}, status_code=400)


async def api_sessions_delete(request: Request):
    """Delete a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    pm = PackManager(agent_manager.config.workspace_path)
    
    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
        pm.invalidate(session_id)
        return JSONResponse({"status": "deleted"})
    return JSONResponse({"error": "Session not found"}, status_code=404)


async def api_sessions_archive(request: Request):
    """Archive session messages via gateway memory consolidation."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)

    session_id = request.path_params["session_id"]
    pm = PackManager(agent_manager.config.workspace_path)
    session = pm.get_or_create(session_id)

    snapshot = list(session.messages[session.last_consolidated:])

    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
    pm.invalidate(session_id)

    if snapshot:
        asyncio.create_task(agent_manager.archive_via_gateway(snapshot))

    return JSONResponse({"status": "archived"})
