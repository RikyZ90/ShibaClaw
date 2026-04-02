"""ShibaBridge — FastAPI + Socket.IO server for the ShibaClaw WebUI.

Usage (standalone):
    python -m shibaclaw.webui.server --port 3000

Or via CLI:
    shibaclaw web --port 3000
"""

from __future__ import annotations

import asyncio
import argparse
import uvicorn
import socketio
from pathlib import Path
from typing import Any
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from loguru import logger

from .auth import (
    AuthMiddleware, 
    get_auth_token, 
    _auth_enabled, 
    mask_token, 
    get_cors_origins
)
from .agent_manager import agent_manager
from .socket_io import register_socket_handlers
from .api import (
    api_auth_verify, api_auth_status, api_status,
    api_settings_get, api_settings_post,
    api_sessions_list, api_sessions_get, api_sessions_patch, api_sessions_delete, api_sessions_archive,
    api_context_get, api_gateway_health, api_gateway_restart,
    api_oauth_providers, api_oauth_login, api_oauth_job, api_oauth_code,
    api_upload, api_file_get, api_file_save, api_fs_explore
)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    config: Any | None = None,
    provider: Any | None = None,
    port: int = 3000,
) -> tuple[socketio.ASGIApp, socketio.AsyncServer]:
    """Create the ASGI app with Socket.IO attached."""
    
    # 1. Initialize logic manager
    if config:
        agent_manager.config = config
    if provider:
        agent_manager.provider = provider
    
    # 2. Socket.IO server
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=get_cors_origins(port),
        logger=False,
        engineio_logger=False,
    )
    
    # Shared sessions state
    sessions: dict[str, dict] = {}
    agent_manager.set_socket_io(sio, sessions)
    
    # Register handlers
    register_socket_handlers(sio, sessions)

    # 3. Starlette routes
    async def index(request):
        return FileResponse(STATIC_DIR / "index.html")

    routes = [
        Route("/", index),
        Route("/api/auth/verify", api_auth_verify, methods=["POST"]),
        Route("/api/auth/status", api_auth_status, methods=["GET"]),
        Route("/api/status", api_status),
        Route("/api/settings", api_settings_get, methods=["GET"]),
        Route("/api/settings", api_settings_post, methods=["POST"]),
        Route("/api/sessions", api_sessions_list),
        Route("/api/sessions/{session_id}", api_sessions_get, methods=["GET"]),
        Route("/api/sessions/{session_id}", api_sessions_patch, methods=["PATCH"]),
        Route("/api/sessions/{session_id}", api_sessions_delete, methods=["DELETE"]),
        Route("/api/sessions/{session_id}/archive", api_sessions_archive, methods=["POST"]),
        Route("/api/context", api_context_get),
        Route("/api/gateway-health", api_gateway_health),
        Route("/api/gateway-restart", api_gateway_restart, methods=["POST"]),
        Route("/api/oauth/providers", api_oauth_providers, methods=["GET"]),
        Route("/api/oauth/login", api_oauth_login, methods=["POST"]),
        Route("/api/oauth/job/{job_id}", api_oauth_job, methods=["GET"]),
        Route("/api/oauth/code", api_oauth_code, methods=["POST"]),
        Route("/api/upload", api_upload, methods=["POST"]),
        Route("/api/file-get", api_file_get, methods=["GET"]),
        Route("/api/file-save", api_file_save, methods=["POST"]),
        Route("/api/fs/explore", api_fs_explore, methods=["GET"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]

    app = Starlette(routes=routes)

    if _auth_enabled():
        app.add_middleware(AuthMiddleware)

    # Combine Socket.IO and Starlette
    combined = socketio.ASGIApp(sio, app)
    return combined, sio


async def run_server(port: int = 3000, host: str = "127.0.0.1", config=None, provider=None):
    """Start the WebUI server."""
    app, _ = create_app(config=config, provider=provider, port=port)

    token = get_auth_token()
    if token:
        logger.info("🔒 Auth enabled — token: {}", mask_token(token))
        logger.info("🔑 To retrieve the full token, run: docker exec -it shibaclaw-gateway shibaclaw print-token")
    else:
        logger.warning("\n" + "!"*60 + "\nWARNING: Authentication is DISABLED\n" + "!"*60)

    server_config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(server_config)
    await server.serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShibaClaw WebUI Server")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()

    print(f"🐕 Starting ShibaClaw WebUI on http://localhost:{args.port}")
    asyncio.run(run_server(port=args.port))
