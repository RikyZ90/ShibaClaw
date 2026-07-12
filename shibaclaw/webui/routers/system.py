from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import threading
import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager


async def api_update_check(request: Request):
    """Check the relevant update source for the active installation method."""
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


_ALLOWED_SUBCOMMANDS = frozenset({"web", "gateway", "cli", "desktop"})

_restart_callback: "Callable[[Callable[[], None] | None], None] | None" = None
_shutdown_callback: "Callable[[], None] | None" = None


def set_restart_callback(fn: "Callable[[Callable[[], None] | None], None]") -> None:
    """Register a callback to be called when the WebUI requests a restart.

    In Desktop mode the callback restarts just the gateway subprocess instead
    of spawning a new top-level process.
    """
    global _restart_callback
    _restart_callback = fn


def set_shutdown_callback(fn: "Callable[[], None]") -> None:
    global _shutdown_callback
    _shutdown_callback = fn


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


def _graceful_shutdown_server() -> None:
    """Ask Uvicorn to shut down so TCP ports are released before respawn."""
    try:
        if sys.platform == "win32":
            os.kill(os.getpid(), signal.CTRL_C_EVENT)
        else:
            os.kill(os.getpid(), signal.SIGINT)
    except Exception as _e:
        logger.debug("Ignored error: {}", _e)


def _exec_restart() -> None:
    argv = _safe_argv()
    if sys.platform != "win32":
        os.execv(argv[0], argv)
    else:
        creationflags = (
            subprocess.CREATE_NEW_CONSOLE
        )
        try:
            # Drop close_fds=True so we don't cause Bad File Descriptor errors for console output
            subprocess.Popen(
                argv,
                creationflags=creationflags
            )
        except Exception as _e:
            logger.debug("Ignored error: {}", _e)
        os._exit(0)


def _schedule_restart_outside_loop(delay: float = 2.0) -> None:
    """Schedule _exec_restart on a daemon thread so it survives event-loop teardown.

    When Uvicorn receives SIGINT it shuts down the event loop, cancelling all
    pending asyncio tasks.  Running the delayed exec on a separate thread
    ensures the replacement process is always started.
    """
    import time

    def _restart_thread():
        time.sleep(delay)
        _exec_restart()

    t = threading.Thread(target=_restart_thread, daemon=False)
    t.start()


def restart_gateway_only(pre_start_hook: "Callable[[], None] | None" = None) -> None:
    """Restart only the gateway subprocess without touching the WebUI server.

    This is safe for frozen .exe environments where a full process restart
    (CTRL_C_EVENT + os._exit) would cause the application to hang.

    - Desktop mode: uses the registered ``_restart_callback`` which stops
      and relaunches the gateway subprocess via :class:`DesktopRuntime`.
    - CLI ``web --with-gateway`` mode: uses the registered ``_restart_callback``
      which terminates and respawns the managed gateway subprocess.
    - Standalone CLI (no callback): sends ``POST /restart`` to the gateway
      HTTP endpoint so the gateway can self-restart.
    """
    if _restart_callback is not None:
        logger.info("restart_gateway_only: using registered restart callback")
        try:
            _restart_callback(pre_start_hook)
        except Exception as exc:
            logger.error("restart_gateway_only callback failed: {}", exc)
        return

    # Fallback: poke the gateway's own /restart HTTP endpoint.
    # The gateway manages its own restart loop (see cli/gateway.py).
    logger.info("restart_gateway_only: no callback — sending POST /restart to gateway")
    try:
        import urllib.request
        from shibaclaw.config.loader import load_config

        cfg = load_config()
        host = cfg.gateway.host or "127.0.0.1"
        port = cfg.gateway.port
        req = urllib.request.Request(
            f"http://{host}:{port}/restart", method="POST"
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as exc:
        logger.warning("restart_gateway_only: failed to contact gateway: {}", exc)


async def api_update_apply(request: Request):
    """Apply a ShibaClaw update or return manual-action guidance."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    manifest = data.get("manifest")
    update_info = data.get("update")

    if manifest is not None and not isinstance(manifest, dict):
        return JSONResponse(
            {"error": "Invalid 'manifest' in request body"}, status_code=400
        )
    if update_info is not None and not isinstance(update_info, dict):
        return JSONResponse(
            {"error": "Invalid 'update' in request body"}, status_code=400
        )
    if update_info is None and manifest is None:
        return JSONResponse(
            {"error": "Missing 'update' or 'manifest' in request body"}, status_code=400
        )

    if not agent_manager.config:
        return JSONResponse({"error": "Agent not configured"}, status_code=400)

    workspace_root = agent_manager.config.workspace_path

    try:
        from shibaclaw.updater.apply import apply_update
        from shibaclaw.webui.ws_handler import _ws_clients
        
        loop = asyncio.get_event_loop()
        
        def progress_cb(current: int, total: int):
            if not _ws_clients:
                return
            percent = int((current / total) * 100) if total > 0 else 0
            payload = {
                "type": "system_event",
                "event": "update_progress",
                "data": {"current": current, "total": total, "percent": percent}
            }
            
            async def _send():
                import json
                raw = json.dumps(payload)
                for ws in list(_ws_clients.values()):
                    try:
                        await ws.send_text(raw)
                    except Exception as _e:
                        logger.debug("Ignored error: {}", _e)
                        
            asyncio.run_coroutine_threadsafe(_send(), loop)

        report = await loop.run_in_executor(
            None,
            lambda: apply_update(update_info, workspace_root, manifest=manifest, progress_cb=progress_cb),
        )
    except Exception as e:
        logger.error("Update apply failed: {}", e)
        return JSONResponse({"error": str(e)}, status_code=500)

    pip_result = report.get("pip") or {}
    exe_result = report.get("exe") or {}

    if pip_result.get("ok") or exe_result.get("ok"):
        async def _do_restart():
            await asyncio.sleep(1.0)

            from shibaclaw.updater.checker import invalidate_cache
            invalidate_cache()

            if exe_result.get("ok"):
                if _shutdown_callback is not None:
                    try:
                        _shutdown_callback()
                    except Exception as _e:
                        logger.debug("Ignored error: {}", _e)
                os._exit(0)
            elif _restart_callback is not None:
                _restart_callback()
            else:
                if _shutdown_callback is not None:
                    try:
                        _shutdown_callback()
                    except Exception as _e:
                        logger.debug("Ignored error: {}", _e)
                _schedule_restart_outside_loop(delay=2.0)
                _graceful_shutdown_server()

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
            _schedule_restart_outside_loop(delay=2.0)
            _graceful_shutdown_server()

    asyncio.create_task(_do_restart())
    return JSONResponse({"status": "restarting"})

