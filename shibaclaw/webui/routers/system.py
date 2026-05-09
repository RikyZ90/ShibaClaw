from __future__ import annotations

import asyncio
import os
import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager


async def api_update_check(request: Request):
    """Check GitHub for the latest ShibaClaw release."""
    force = request.query_params.get("force", "").lower() in ("1", "true", "yes")
    try:
        from shibaclaw.updater.checker import check_for_update

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: check_for_update(force=force)
        )
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

        manifest = await asyncio.get_event_loop().run_in_executor(
            None, lambda: fetch_manifest(manifest_url)
        )
        personal = personal_files_in_manifest(manifest)
        return JSONResponse({"manifest": manifest, "personal_files": personal})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


_restart_callback: "Callable[[], None] | None" = None


def set_restart_callback(fn: "Callable[[], None]") -> None:
    """Register a callback to be called when the WebUI requests a restart.

    In Desktop mode the callback restarts just the gateway subprocess instead
    of spawning a new top-level process.
    """
    global _restart_callback
    _restart_callback = fn


def _safe_argv() -> list[str]:
    """Return only trusted argv entries (flags + known subcommands).

    Only used when no restart callback is registered (standalone CLI mode).
    """
    import sys

    if getattr(sys, "frozen", False):
        safe = [sys.executable]
        for arg in sys.argv[1:]:
            if arg.startswith("-") or arg in _ALLOWED_SUBCOMMANDS:
                safe.append(arg)
        return safe
    elif hasattr(sys, "orig_argv"):
        return list(sys.orig_argv)
    else:
        return [sys.executable] + list(sys.argv)


async def api_update_apply(request: Request):
    """Apply a ShibaClaw update: backup personal files + pip upgrade."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    manifest = data.get("manifest")
    if not manifest or not isinstance(manifest, dict):
        return JSONResponse(
            {"error": "Missing or invalid 'manifest' in request body"}, status_code=400
        )

    if not agent_manager.config:
        return JSONResponse({"error": "Agent not configured"}, status_code=400)

    workspace_root = agent_manager.config.workspace_path

    try:
        from shibaclaw.updater.apply import apply_update

        loop = asyncio.get_event_loop()
        report = await loop.run_in_executor(None, lambda: apply_update(manifest, workspace_root))
    except Exception as e:
        logger.error("Update apply failed: {}", e)
        return JSONResponse({"error": str(e)}, status_code=500)

    if report.get("pip", {}).get("ok"):
        async def _do_restart():
            await asyncio.sleep(1.0)
            if _restart_callback is not None:
                _restart_callback()
            else:
                import subprocess
                subprocess.Popen(_safe_argv())
                os._exit(0)

        asyncio.create_task(_do_restart())
        report["restarting"] = True
    else:
        report["restarting"] = False

    return JSONResponse(report)


async def api_restart_server(request: Request):
    """Restart the ShibaClaw WebUI server process."""
    async def _do_restart():
        await asyncio.sleep(0.5)
        if _restart_callback is not None:
            _restart_callback()
        else:
            import subprocess
            subprocess.Popen(_safe_argv())
            os._exit(0)

    asyncio.create_task(_do_restart())
    return JSONResponse({"status": "restarting"})

