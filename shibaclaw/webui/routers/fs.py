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

from shibaclaw.webui.utils import _resolve_workspace_path


async def api_upload(request: Request):
    """Handle multi-file uploads into the workspace."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    
    try:
        form = await request.form()
        files = form.getlist("file")
        if not files:
            return JSONResponse({"error": "No files uploaded"}, status_code=400)
        
        upload_dir = agent_manager.config.workspace_path / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        auth_token = get_auth_token() or ""
        results = []
        for f in files:
            filename = f.filename
            safe_name = "".join([c for c in filename if c.isalnum() or c in "._- "]).strip()
            if not safe_name:
                safe_name = f"upload_{uuid.uuid4().hex[:8]}"
            
            target_path = upload_dir / safe_name
            counter = 1
            while target_path.exists():
                name_stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                target_path = upload_dir / f"{name_stem}_{counter}{suffix}"
                counter += 1
            
            content = await f.read()
            target_path.write_bytes(content)
            results.append({
                "filename": target_path.name,
                "url": f"/api/file-get?path={urllib.parse.quote(str(target_path.absolute()))}"
            })
        
        return JSONResponse({"status": "success", "files": results})
    except Exception as e:
        logger.exception("Upload failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_file_get(request: Request):
    """Serve a file from the filesystem — restricted to the agent workspace."""
    path_str = request.query_params.get("path")
    if not path_str:
        return JSONResponse({"error": "No path provided"}, status_code=400)

    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=503)

    resolved = _resolve_workspace_path(path_str)
    if not resolved:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if not resolved.exists() or not resolved.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    mime_type, _ = mimetypes.guess_type(path_str)
    if not mime_type:
        mime_type = "application/octet-stream"

    headers = {}
    if mime_type.startswith("image/"):
        headers["Cache-Control"] = "public, max-age=3600"
    else:
        headers["Cache-Control"] = "no-store"

    return FileResponse(resolved, media_type=mime_type, headers=headers)


async def api_file_save(request: Request):
    """Overwrite a workspace file with new text content."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    path_str = body.get("path")
    content = body.get("content")
    if not path_str or content is None:
        return JSONResponse({"error": "path and content are required"}, status_code=400)

    resolved = _resolve_workspace_path(path_str)
    if not resolved:
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if not resolved.exists() or not resolved.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    try:
        resolved.write_text(content, encoding="utf-8")
        written = resolved.stat().st_size
        logger.info("file-save: wrote {} bytes to {}", written, resolved)
        return JSONResponse({"status": "ok", "path": str(resolved), "bytes": written})
    except Exception as e:
        logger.exception("file-save failed for {}", resolved)
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_fs_explore(request: Request):
    """List files in a directory — restricted to the agent workspace."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=503)

    target_path_str = request.query_params.get("path")
    target_path = _resolve_workspace_path(target_path_str)
    if not target_path:
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    workspace = agent_manager.config.workspace_path.resolve()

    if not target_path.exists() or not target_path.is_dir():
        return JSONResponse({"error": "Directory not found"}, status_code=404)
    
    try:
        items = []
        with os.scandir(target_path) as it:
            for entry in it:
                try:
                    info = {
                        "name": entry.name,
                        "path": Path(entry.path).relative_to(workspace).as_posix(),
                        "is_dir": entry.is_dir(),
                        "size": entry.stat().st_size if not entry.is_dir() else None,
                        "mtime": entry.stat().st_mtime
                    }
                    items.append(info)
                except (PermissionError, OSError):
                    continue
        
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        return JSONResponse({
            "current_path": str(target_path.absolute()),
            "parent_path": str(target_path.parent.absolute()) if target_path.parent != target_path else None,
            "items": items
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
