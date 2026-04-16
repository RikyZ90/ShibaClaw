"""WebUI server module."""

from __future__ import annotations

import asyncio
import argparse
import os
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
    api_cron_list, api_cron_trigger, api_heartbeat_status, api_heartbeat_trigger,
    api_oauth_providers, api_oauth_login, api_oauth_job, api_oauth_code,
    api_upload, api_file_get, api_file_save, api_fs_explore,
    api_update_check, api_update_manifest, api_update_apply, api_restart_server,
    api_onboard_providers, api_onboard_templates, api_onboard_submit,
    api_skills_list, api_skills_pin, api_skills_delete, api_skills_import,
    api_profiles_list, api_profiles_get, api_profiles_create, api_profiles_update, api_profiles_delete,
    api_internal_session_notify,
)

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    config: Any | None = None,
    provider: Any | None = None,
    port: int = 3000,
    host: str = "127.0.0.1",
) -> tuple[socketio.ASGIApp, socketio.AsyncServer]:
    if config:
        agent_manager.config = config
    if provider:
        agent_manager.provider = provider
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=get_cors_origins(port, host),
        logger=False,
        engineio_logger=False,
    )
    sessions: dict[str, dict] = {}
    agent_manager.set_socket_io(sio, sessions)
    register_socket_handlers(sio, sessions)

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

        Route("/api/cron/jobs", api_cron_list, methods=["GET"]),
        Route("/api/cron/jobs/{job_id}/trigger", api_cron_trigger, methods=["POST"]),
        Route("/api/heartbeat/status", api_heartbeat_status, methods=["GET"]),
        Route("/api/heartbeat/trigger", api_heartbeat_trigger, methods=["POST"]),
        Route("/api/oauth/providers", api_oauth_providers, methods=["GET"]),
        Route("/api/oauth/login", api_oauth_login, methods=["POST"]),
        Route("/api/oauth/job/{job_id}", api_oauth_job, methods=["GET"]),
        Route("/api/oauth/code", api_oauth_code, methods=["POST"]),
        Route("/api/upload", api_upload, methods=["POST"]),
        Route("/api/file-get", api_file_get, methods=["GET"]),
        Route("/api/file-save", api_file_save, methods=["POST"]),
        Route("/api/fs/explore", api_fs_explore, methods=["GET"]),
        Route("/api/update/check", api_update_check, methods=["GET"]),
        Route("/api/update/manifest", api_update_manifest, methods=["GET"]),
        Route("/api/update/apply", api_update_apply, methods=["POST"]),
        Route("/api/restart", api_restart_server, methods=["POST"]),
        Route("/api/onboard/providers", api_onboard_providers, methods=["GET"]),
        Route("/api/onboard/templates", api_onboard_templates, methods=["GET"]),
        Route("/api/onboard/submit", api_onboard_submit, methods=["POST"]),
        Route("/api/skills", api_skills_list, methods=["GET"]),
        Route("/api/skills/pin", api_skills_pin, methods=["POST"]),
        Route("/api/skills/import", api_skills_import, methods=["POST"]),
        Route("/api/skills/{name}", api_skills_delete, methods=["DELETE"]),
        Route("/api/profiles", api_profiles_list, methods=["GET"]),
        Route("/api/profiles", api_profiles_create, methods=["POST"]),
        Route("/api/profiles/{profile_id}", api_profiles_get, methods=["GET"]),
        Route("/api/profiles/{profile_id}", api_profiles_update, methods=["PUT"]),
        Route("/api/profiles/{profile_id}", api_profiles_delete, methods=["DELETE"]),
        Route("/api/internal/session-notify", api_internal_session_notify, methods=["POST"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]

    app = Starlette(routes=routes)

    if _auth_enabled():
        app.add_middleware(AuthMiddleware)
    combined = socketio.ASGIApp(sio, app)
    return combined, sio


async def _check_update_on_startup() -> None:
    try:
        await asyncio.sleep(3)
        from shibaclaw.updater.checker import check_for_update
        result = await asyncio.get_event_loop().run_in_executor(None, check_for_update)
        if result.get("update_available"):
            logger.info(
                "🆕 ShibaClaw update available: {} → {}",
                result["current"],
                result["latest"],
            )
    except Exception:
        pass


async def _sync_skills_on_startup() -> None:
    """Sync built-in skills and profiles to workspace on startup."""
    try:
        await asyncio.sleep(1)
        from shibaclaw.helpers.helpers import sync_skills, sync_profiles
        cfg = agent_manager.config
        if cfg:
            sync_skills(cfg.workspace_path)
            sync_profiles(cfg.workspace_path)
            logger.info("Skills and profiles synced on startup")
    except Exception:
        logger.exception("Failed to sync skills/profiles on startup")


async def _ensure_config_on_startup() -> None:
    """Load config eagerly so routes have workspace info."""
    try:
        await asyncio.sleep(1)
        if not agent_manager.config:
            agent_manager.load_latest_config()
            logger.info("Config loaded on startup")
    except Exception:
        logger.exception("Failed to load config on startup")


async def run_server(port: int = 3000, host: str = "127.0.0.1", config=None, provider=None):
    app, _ = create_app(config=config, provider=provider, port=port, host=host)
    if host in ("0.0.0.0", "::") and not os.environ.get("SHIBACLAW_CORS_ORIGINS", "").strip():
        logger.warning("Binding to {} — set SHIBACLAW_CORS_ORIGINS for non-loopback clients", host)

    token = get_auth_token()
    if token:
        logger.info("🔒 Auth enabled — token: {}", mask_token(token))
    else:
        logger.warning("WARNING: Authentication is DISABLED")

    asyncio.create_task(_check_update_on_startup())
    asyncio.create_task(_sync_skills_on_startup())
    asyncio.create_task(_ensure_config_on_startup())

    server_config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(server_config)
    await server.serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShibaClaw WebUI Server")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()

    print(f"🐕 Starting ShibaClaw WebUI on http://{args.host}:{args.port}")
    asyncio.run(run_server(port=args.port, host=args.host))
