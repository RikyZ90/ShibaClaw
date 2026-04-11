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


async def api_onboard_providers(request: Request):
    """Return provider list with detection status for the onboard wizard."""
    from shibaclaw.cli.onboard import (
        _ONBOARD_PROVIDERS, _detect_env_keys, _detect_oauth,
    )

    if not agent_manager.config:
        agent_manager.load_latest_config()

    env_found = _detect_env_keys()
    oauth_found = _detect_oauth()

    cfg = agent_manager.config
    current_provider = cfg.agents.defaults.provider if cfg else ""
    current_model = cfg.agents.defaults.model if cfg else ""
    # Strip erroneous provider prefix (e.g. "openrouter/") from model names
    if current_provider and current_model.startswith(current_provider + "/"):
        current_model = current_model[len(current_provider) + 1:]

    providers = []
    for name, label, env_key, default_model, is_local, is_oauth in _ONBOARD_PROVIDERS:
        has_key = False
        if cfg:
            p = getattr(cfg.providers, name, None)
            has_key = bool(p and p.api_key)

        status = "available"
        if name in env_found:
            status = "env_detected"
        elif name in oauth_found:
            status = "oauth_ok"
        elif has_key:
            status = "configured"

        providers.append({
            "name": name,
            "label": label,
            "env_key": env_key,
            "default_model": default_model,
            "is_local": is_local,
            "is_oauth": is_oauth,
            "status": status,
        })

    return JSONResponse({
        "providers": providers,
        "current_provider": current_provider,
        "current_model": current_model,
    })


async def api_onboard_templates(request: Request):
    """Return workspace template status (new vs existing)."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return JSONResponse({"new_files": [], "existing_files": []})

    wp = agent_manager.config.workspace_path
    from importlib.resources import files as pkg_files
    try:
        tpl = pkg_files("shibaclaw") / "templates"
    except Exception:
        return JSONResponse({"new_files": [], "existing_files": []})

    new_files, existing_files = [], []
    for item in tpl.iterdir():
        if item.name.endswith(".md") and not item.name.startswith("."):
            dest = wp / item.name
            (existing_files if dest.exists() else new_files).append(item.name)

    mem_dest = wp / "memory" / "MEMORY.md"
    if mem_dest.exists():
        existing_files.append("memory/MEMORY.md")
    else:
        new_files.append("memory/MEMORY.md")

    return JSONResponse({"new_files": new_files, "existing_files": existing_files})


async def api_onboard_submit(request: Request):
    """Apply onboard wizard configuration."""
    data = await request.json()
    provider_name = data.get("provider", "").strip()
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "").strip()
    overwrite_templates = data.get("overwrite_templates", [])

    if not provider_name or not model:
        return JSONResponse({"error": "provider and model are required"}, status_code=422)

    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        from shibaclaw.config.schema import Config
        agent_manager.config = Config()

    cfg = agent_manager.config

    # Apply provider key
    if api_key:
        p = getattr(cfg.providers, provider_name, None)
        if p is not None:
            p.api_key = api_key

    # Apply model and provider
    cfg.agents.defaults.model = model
    cfg.agents.defaults.provider = provider_name

    # Save config
    from shibaclaw.config.loader import save_config, get_config_path
    config_path = get_config_path()
    save_config(cfg, config_path)

    # Run plugin defaults
    from shibaclaw.cli.onboard import _onboard_plugins
    _onboard_plugins(config_path)

    # Sync workspace templates
    wp = cfg.workspace_path
    if not wp.exists():
        wp.mkdir(parents=True, exist_ok=True)

    from importlib.resources import files as pkg_files
    try:
        tpl = pkg_files("shibaclaw") / "templates"
    except Exception:
        tpl = None

    if tpl and tpl.is_dir():
        overwrite_set = set(overwrite_templates)
        for item in tpl.iterdir():
            if item.name.endswith(".md") and not item.name.startswith("."):
                dest = wp / item.name
                if not dest.exists() or item.name in overwrite_set:
                    dest.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")

        mem_tpl = tpl / "memory" / "MEMORY.md"
        mem_dest = wp / "memory" / "MEMORY.md"
        mem_dest.parent.mkdir(parents=True, exist_ok=True)
        if not mem_dest.exists() or "memory/MEMORY.md" in overwrite_set:
            mem_dest.write_text(mem_tpl.read_text(encoding="utf-8"), encoding="utf-8")

        hist_dest = wp / "memory" / "HISTORY.md"
        if not hist_dest.exists():
            hist_dest.write_text("", encoding="utf-8")

    from shibaclaw.helpers.helpers import sync_skills, sync_profiles
    sync_skills(wp)
    sync_profiles(wp)

    # Reset agent and reload from freshly saved config on disk.
    # This ensures the provider is correctly initialised from the new config
    # without depending on the in-memory object, which may be stale.
    await agent_manager.reset_agent()
    agent_manager.load_latest_config()
    await agent_manager.ensure_agent()

    return JSONResponse({"status": "ok"})
