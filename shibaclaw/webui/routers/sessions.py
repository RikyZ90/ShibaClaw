from __future__ import annotations

import asyncio
import os

from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.webui.agent_manager import agent_manager


async def api_sessions_list(request: Request):
    """List all saved sessions."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    return JSONResponse({"sessions": pm.list_sessions()})


async def api_sessions_get(request: Request):
    """Get details for a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.get_or_create(session_id)

    # Normalize model ID if present
    if model := session.metadata.get("model"):
        from shibaclaw.helpers.model_ids import canonicalize_model_id

        canonical = canonicalize_model_id(agent_manager.config, model)
        if canonical != model:
            session.metadata["model"] = canonical
            pm.save(session)

    # Hydrate attachments for any role with persisted channel media.
    for m in session.messages:
        if "metadata" in m and m["metadata"].get("media"):
            from shibaclaw.webui.ws_handler import _build_attachments

            m.setdefault("metadata", {})["attachments"] = _build_attachments(m["metadata"]["media"])

    return JSONResponse(
        {
            "messages": session.messages,
            "nickname": session.metadata.get("nickname"),
            "profile_id": session.metadata.get("profile_id", "default"),
            "model": session.metadata.get("model", ""),
            "reasoning_effort": session.metadata.get("reasoning_effort", None),
            "knowledge_bases": session.metadata.get("knowledge_bases", []),
            "permission_mode": session.metadata.get("permission_mode"),
            "incognito": bool(session.metadata.get("incognito")),
        }
    )


async def api_sessions_patch(request: Request):
    """Update session metadata (like nickname, model, reasoning_effort)."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    data = await request.json()
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.get_or_create(session_id)

    if "nickname" in data:
        session.metadata["nickname"] = data["nickname"]
    if "profile_id" in data:
        old_profile_id = session.metadata.get("profile_id", "default")
        session.metadata["profile_id"] = data["profile_id"]
        try:
            from shibaclaw.agent.profiles import ProfileManager

            wp = agent_manager.config.workspace_path
            ProfileManager(wp).sync_session_knowledge_bases(
                session.metadata, data["profile_id"], old_profile_id
            )
        except Exception:
            pass
    if "model" in data:
        model = data["model"]
        if model:
            try:
                from shibaclaw.agent.profiles import ProfileManager

                profile_id = session.metadata.get("profile_id", "default")
                if "profile_id" in data:
                    profile_id = data["profile_id"]
                wp = agent_manager.config.workspace_path
                if not ProfileManager(wp).model_allowed(profile_id, str(model)):
                    return JSONResponse(
                        {"error": f"Model not allowed for profile '{profile_id}'"},
                        status_code=400,
                    )
            except Exception as e:
                logger.warning("Model allowlist validation failed: {}", e)
                return JSONResponse(
                    {"error": f"Model allowlist validation failed: {e}"},
                    status_code=403,
                )
        session.metadata["model"] = model
    if "reasoning_effort" in data:
        session.metadata["reasoning_effort"] = data["reasoning_effort"]
    if "knowledge_bases" in data:
        session.metadata["knowledge_bases"] = data["knowledge_bases"]
    if "permission_mode" in data:
        from shibaclaw.agent.interactive import PERMISSION_MODES

        mode = str(data["permission_mode"] or "").strip().lower()
        if mode and mode not in PERMISSION_MODES:
            return JSONResponse(
                {"error": f"permission_mode must be one of {sorted(PERMISSION_MODES)}"},
                status_code=400,
            )
        session.metadata["permission_mode"] = mode or None
    if "incognito" in data:
        enabling = bool(data["incognito"])
        was_incognito = bool(session.metadata.get("incognito"))
        session.metadata["incognito"] = enabling
        if enabling and not was_incognito:
            # Toggle onto existing persisted session → wipe disk file.
            pm.purge_persisted_session(session.key)
    touch_keys = (
        "nickname",
        "profile_id",
        "model",
        "reasoning_effort",
        "knowledge_bases",
        "permission_mode",
        "incognito",
    )
    if any(k in data for k in touch_keys):
        pm.save(session)
        return JSONResponse(
            {
                "status": "updated",
                "profile_id": session.metadata.get("profile_id", "default"),
                "reasoning_effort": session.metadata.get("reasoning_effort"),
                "permission_mode": session.metadata.get("permission_mode"),
                "incognito": bool(session.metadata.get("incognito")),
            }
        )
    return JSONResponse({"error": "Nothing to update"}, status_code=400)


async def api_sessions_fork(request: Request):
    """Fork a session from a message index into a new session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    data = await request.json()
    try:
        from_index = int(data.get("from_index"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "from_index must be an int"}, status_code=400)
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    forked = pm.fork_session(session_id, from_index)
    if not forked:
        return JSONResponse({"error": "Fork failed"}, status_code=500)
    return JSONResponse(
        {
            "status": "ok",
            "session_id": forked.key,
            "nickname": forked.metadata.get("nickname"),
            "message_count": len(forked.messages),
        }
    )


async def api_sessions_rewind(request: Request):
    """Rewind a session to a message index (truncate after)."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    data = await request.json()
    try:
        to_index = int(data.get("to_index"))
    except (TypeError, ValueError):
        return JSONResponse({"error": "to_index must be an int"}, status_code=400)
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.rewind_session(session_id, to_index)
    if not session:
        return JSONResponse({"error": "Rewind failed"}, status_code=500)
    return JSONResponse(
        {
            "status": "ok",
            "session_id": session.key,
            "message_count": len(session.messages),
        }
    )


async def api_config_history(request: Request):
    """List recent config change history snapshots."""
    try:
        limit = int(request.query_params.get("limit") or 50)
    except ValueError:
        limit = 50
    from shibaclaw.config.history import list_config_history

    return JSONResponse({"history": list_config_history(limit=limit)})



async def api_sessions_delete(request: Request):
    """Delete a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)

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
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    session = pm.get_or_create(session_id)

    snapshot = list(session.messages[session.last_consolidated :])
    incognito = bool(session.metadata.get("incognito") or session.metadata.get("ephemeral"))

    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
    pm.invalidate(session_id)

    # Incognito/ephemeral: drop session disk state without consolidating to memory.
    if snapshot and not incognito:
        asyncio.create_task(agent_manager.archive_via_gateway(snapshot, session_key=session_id))

    return JSONResponse({"status": "archived", "incognito_skipped": incognito})


async def api_sessions_search(request: Request):
    """Search conversation message bodies across sessions (authenticated WebUI only)."""
    from shibaclaw.webui.auth import (
        _auth_enabled,
        check_token,
        is_telegram_mini_surface,
    )

    # Owner WebUI only — Mini App / unauthenticated clients must not scan transcripts.
    if is_telegram_mini_surface(request):
        return JSONResponse(
            {"error": "session search is available on the browser WebUI only"},
            status_code=403,
        )
    if _auth_enabled() and not check_token(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    pm = agent_manager.pm
    if not pm:
        return JSONResponse({"error": "Agent manager not ready"}, status_code=500)
    q = (request.query_params.get("q") or "").strip()
    if not q:
        return JSONResponse({"error": "q is required"}, status_code=400)
    try:
        limit = int(request.query_params.get("limit") or 20)
    except ValueError:
        limit = 20
    hits = pm.search_messages(q, limit=limit)
    return JSONResponse({"query": q, "hits": hits})
