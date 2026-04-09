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


async def api_update_check(request: Request):
    """Check GitHub for the latest ShibaClaw release."""
    force = request.query_params.get("force", "").lower() in ("1", "true", "yes")
    try:
        from shibaclaw.updater.checker import check_for_update
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: check_for_update(force=force))
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_update_manifest(request: Request):
    """Download and return the update manifest for a given manifest_url."""
    manifest_url = request.query_params.get("url", "").strip()
    if not manifest_url:
        return JSONResponse({"error": "Missing url parameter"}, status_code=400)

    parsed = urllib.parse.urlparse(manifest_url)
    allowed_hosts = {"github.com", "raw.githubusercontent.com"}
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        return JSONResponse({"error": "Invalid manifest URL"}, status_code=400)

    try:
        from shibaclaw.updater.manifest import fetch_manifest, personal_files_in_manifest
        manifest = await asyncio.get_event_loop().run_in_executor(None, lambda: fetch_manifest(manifest_url))
        personal = personal_files_in_manifest(manifest)
        return JSONResponse({"manifest": manifest, "personal_files": personal})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


_ALLOWED_SUBCOMMANDS = frozenset({"web", "gateway", "cli"})


def _safe_argv() -> list[str]:
    """Return only trusted argv entries (flags + known subcommands)."""
    import sys
    safe = [sys.executable, "-m", "shibaclaw"]
    for arg in sys.argv[1:]:
        if arg.startswith("-") or arg in _ALLOWED_SUBCOMMANDS:
            safe.append(arg)
    return safe


async def api_restart_server(request: Request):
    """Restart the ShibaClaw WebUI server process."""
    safe_argv = _safe_argv()

    async def _do_restart():
        await asyncio.sleep(0.5)
        os.execv(sys.executable, safe_argv)

    asyncio.create_task(_do_restart())
    return JSONResponse({"status": "restarting"})
