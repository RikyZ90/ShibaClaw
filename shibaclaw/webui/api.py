"""Starlette API route handlers for the ShibaClaw WebUI."""

from __future__ import annotations

import json
from starlette.requests import Request
from starlette.responses import JSONResponse

from shibaclaw.brain.manager import PackManager

from .agent_manager import agent_manager
from .utils import (
    _build_real_system_prompt,
    _compute_session_tokens,
    _gateway_request,
)


async def api_status(request: Request):
    """Get general server and agent status."""
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config
    from shibaclaw import __version__

    gw = await _gateway_request("GET", "/")
    print(f"DEBUG: api_status -> gw_resp={gw}")
    gw_ready = gw is not None and gw.get("status") in ("ok", "idle")

    # Check if any OAuth providers are configured
    from .routers.oauth import api_oauth_providers
    oauth_res = await api_oauth_providers(request)
    oauth_data = json.loads(oauth_res.body)
    oauth_configured = any(p.get("status") == "configured" for p in oauth_data.get("providers", []))

    resp = {
        "status": "ok" if gw_ready else "gateway_offline",
        "version": __version__,
        "agent_configured": gw_ready and gw.get("provider_ready", False),
        "oauth_configured": oauth_configured,
        "provider": cfg.agents.defaults.provider if cfg else None,
        "model": cfg.agents.defaults.model if cfg else None,
        "workspace": str(cfg.workspace_path) if cfg else None,
        "gateway": gw_ready,
    }
    print(f"DEBUG: api_status -> final_resp={resp}")
    return JSONResponse(resp)


async def api_context_get(request: Request):
    """Generate a context summary for the workspace and session.

    The 'system_prompt' section now reflects the real prompt assembled by
    ScentBuilder (identity, bootstrap files, memory, skills) — the same
    text that is sent to the LLM.  Token counts use tiktoken instead of
    the old ``len // 4`` heuristic.
    """
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)

    wp = agent_manager.config.workspace_path
    session_id = request.query_params.get("session_id", "")
    defaults = agent_manager.config.agents.defaults
    sections = []

    from shibaclaw.helpers.helpers import estimate_message_tokens

    # Resolve profile_id from session metadata
    profile_id = None
    if session_id:
        pm_ctx = PackManager(wp)
        sess_ctx = pm_ctx.get_or_create(session_id)
        profile_id = sess_ctx.metadata.get("profile_id") or None

    # ── Real system prompt (identity + bootstrap + memory + skills) ──
    system_prompt, prompt_tokens = _build_real_system_prompt(wp, defaults, profile_id=profile_id)
    total_tokens = prompt_tokens
    sections.append(
        f"## 🧠 System Prompt ({prompt_tokens} tokens)\n\n```markdown\n{system_prompt}\n```"
    )

    # -- Tool definitions token count (gateway-only, estimate 0 locally) --
    tools_tokens = 0
    total_tokens = prompt_tokens

    # ── Session messages ──
    msg_tokens = 0
    if session_id:
        pm = PackManager(wp)
        msg_tokens, msg_lines = _compute_session_tokens(session_id, wp, pm, estimate_message_tokens)
        if msg_lines:
            sections.append(
                f"## 💬 Session Messages ({len(msg_lines)} messages)\n\n"
                + "\n".join(msg_lines)
            )
    total_tokens += msg_tokens

    ctx_window = defaults.context_window_tokens or 0
    pct = min(100, round(total_tokens / ctx_window * 100)) if ctx_window > 0 else 0

    if request.query_params.get("summary", "").lower() in ("1", "true", "yes"):
        return JSONResponse(
            {
                "tokens": {
                    "system_prompt": prompt_tokens,
                    "tools": tools_tokens,
                    "messages": msg_tokens,
                    "total": total_tokens,
                    "context_window": ctx_window,
                    "usage_pct": pct,
                }
            }
        )

    context_md = (
        "\n\n---\n\n".join(sections) if sections else "_No context files or session data found._"
    )
    return JSONResponse(
        {
            "context": context_md,
            "tokens": {
                "system_prompt": prompt_tokens,
                "tools": tools_tokens,
                "messages": msg_tokens,
                "total": total_tokens,
                "context_window": ctx_window,
                "usage_pct": pct,
            },
        }
    )


# ── Re-exports (server.py imports everything from here) ──────────────
from .routers.auth import api_auth_status, api_auth_verify  # noqa: E402, F401
from .routers.cron import api_cron_list, api_cron_trigger  # noqa: E402, F401
from .routers.fs import api_file_get, api_file_save, api_fs_explore, api_upload  # noqa: E402, F401
from .routers.gateway import api_gateway_health, api_gateway_restart  # noqa: E402, F401
from .routers.heartbeat import api_heartbeat_status, api_heartbeat_trigger  # noqa: E402, F401
from .routers.oauth import (  # noqa: E402, F401
    api_oauth_code,
    api_oauth_job,
    api_oauth_login,
    api_oauth_openrouter_callback,
    api_oauth_providers,
)
from .routers.onboard import (  # noqa: E402, F401
    api_onboard_providers,
    api_onboard_submit,
    api_onboard_templates,
)
from .routers.profiles import (  # noqa: E402, F401
    api_profiles_create,
    api_profiles_delete,
    api_profiles_get,
    api_profiles_list,
    api_profiles_update,
)
from .routers.sessions import (  # noqa: E402, F401
    api_sessions_archive,
    api_sessions_delete,
    api_sessions_get,
    api_sessions_list,
    api_sessions_patch,
)
from .routers.settings import (  # noqa: E402, F401
    api_models_get,
    api_settings_get,
    api_settings_post,
)
from .routers.skills import (  # noqa: E402, F401
    api_skills_delete,
    api_skills_import,
    api_skills_list,
    api_skills_pin,
)
from .routers.system import (  # noqa: E402, F401
    api_restart_server,
    api_update_apply,
    api_update_check,
    api_update_manifest,
)


async def api_internal_session_notify(request: Request):
    """Receive background notifications from the gateway and emit to WebUI clients."""
    data = await request.json()
    session_key = data.get("session_key", "")
    content = data.get("content", "")
    source = data.get("source", "background")
    persist = data.get("persist", True)

    result = await agent_manager.deliver_background_notification(
        session_key,
        content,
        source=source,
        persist=persist,
    )
    return JSONResponse(result)
