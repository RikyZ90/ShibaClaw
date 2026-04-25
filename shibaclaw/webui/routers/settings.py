from __future__ import annotations

import asyncio

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.utils import _deep_merge, _redact_secrets


async def api_settings_get(request: Request):
    """Get the current configuration (redacted)."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    data = agent_manager.config.model_dump(mode="json", by_alias=True)
    return JSONResponse(_redact_secrets(data))


_settings_update_lock = asyncio.Lock()


async def api_settings_post(request: Request):
    """Update configuration and reset the agent."""
    async with _settings_update_lock:
        if not agent_manager.config:
            agent_manager.load_latest_config()
        if not agent_manager.config:
            return JSONResponse({"error": "No config"}, status_code=400)

        data = await request.json()
        from shibaclaw.config.schema import Config

        merged = agent_manager.config.model_dump(mode="json", by_alias=True)
        if isinstance(data.get("tools"), dict) and "mcpServers" in data["tools"]:
            merged.setdefault("tools", {})["mcpServers"] = data["tools"]["mcpServers"]
        _deep_merge(merged, data)

        try:
            new_cfg = Config.model_validate(merged)
        except Exception as e:
            return JSONResponse({"error": f"Invalid config: {e}"}, status_code=422)

        from shibaclaw.config.loader import save_config

        save_config(new_cfg)
        agent_manager.config = new_cfg
        # Rebuild provider so the new configuration is applied immediately
        try:
            from shibaclaw.cli.commands import _make_provider

            agent_manager.provider = _make_provider(new_cfg, exit_on_error=False)
        except Exception:
            agent_manager.provider = None
        await agent_manager.reset_agent()
        logger.info("Config updated by {}", request.client.host if request.client else "unknown")

    return JSONResponse({"status": "updated"})
