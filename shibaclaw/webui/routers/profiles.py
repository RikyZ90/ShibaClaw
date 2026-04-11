"""API router for agent profile CRUD operations."""

from __future__ import annotations

import re
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.agent.profiles import ProfileManager, DEFAULT_PROFILE_ID


def _get_pm() -> ProfileManager | None:
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return None
    return ProfileManager(agent_manager.config.workspace_path)


_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,48}[a-zA-Z0-9]$")


async def api_profiles_list(request: Request):
    """List all available agent profiles."""
    pm = _get_pm()
    if not pm:
        return JSONResponse({"error": "No config"}, status_code=400)
    return JSONResponse({"profiles": pm.list_profiles()})


async def api_profiles_get(request: Request):
    """Get a specific profile with its soul content."""
    pm = _get_pm()
    if not pm:
        return JSONResponse({"error": "No config"}, status_code=400)
    profile_id = request.path_params["profile_id"]
    profile = pm.get_profile(profile_id)
    if not profile:
        return JSONResponse({"error": "Profile not found"}, status_code=404)
    return JSONResponse(profile)


async def api_profiles_create(request: Request):
    """Create a new custom profile."""
    pm = _get_pm()
    if not pm:
        return JSONResponse({"error": "No config"}, status_code=400)
    data = await request.json()
    profile_id = data.get("id", "").strip()
    label = data.get("label", "").strip()
    description = data.get("description", "").strip()
    soul = data.get("soul", "").strip()
    avatar = data.get("avatar", "").strip() or None

    if not profile_id or not label:
        return JSONResponse({"error": "id and label are required"}, status_code=422)
    if not _PROFILE_ID_RE.match(profile_id):
        return JSONResponse(
            {"error": "Invalid id: use 2-50 alphanumeric chars, hyphens, or underscores"},
            status_code=422,
        )
    if pm.get_profile(profile_id):
        return JSONResponse({"error": "Profile already exists"}, status_code=409)

    profile = pm.create_profile(profile_id, label, description, soul, avatar=avatar)
    # Invalidate ScentBuilder bootstrap cache so the new profile is picked up
    if agent_manager.agent:
        agent_manager.agent.context._bootstrap_cache.clear()
        agent_manager.agent.context._bootstrap_mtimes.clear()
    return JSONResponse(profile, status_code=201)


async def api_profiles_update(request: Request):
    """Update an existing profile."""
    pm = _get_pm()
    if not pm:
        return JSONResponse({"error": "No config"}, status_code=400)
    profile_id = request.path_params["profile_id"]
    data = await request.json()

    result = pm.update_profile(
        profile_id,
        label=data.get("label"),
        description=data.get("description"),
        soul_content=data.get("soul"),
        avatar=data.get("avatar", ...),
    )
    if not result:
        return JSONResponse({"error": "Profile not found"}, status_code=404)
    # Invalidate cache
    if agent_manager.agent:
        agent_manager.agent.context._bootstrap_cache.pop(profile_id, None)
        agent_manager.agent.context._bootstrap_mtimes.pop(profile_id, None)
    return JSONResponse(result)


async def api_profiles_delete(request: Request):
    """Delete a custom profile."""
    pm = _get_pm()
    if not pm:
        return JSONResponse({"error": "No config"}, status_code=400)
    profile_id = request.path_params["profile_id"]
    if not pm.delete_profile(profile_id):
        return JSONResponse({"error": "Cannot delete built-in or default profile"}, status_code=403)
    # Invalidate cache
    if agent_manager.agent:
        agent_manager.agent.context._bootstrap_cache.pop(profile_id, None)
        agent_manager.agent.context._bootstrap_mtimes.pop(profile_id, None)
    return JSONResponse({"status": "deleted"})
