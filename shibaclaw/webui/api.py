"""Starlette API route handlers for the ShibaClaw WebUI."""

from __future__ import annotations

import os
import uuid
import json
import asyncio
import mimetypes
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

from shibaclaw.brain.manager import PackManager

from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from loguru import logger

from .auth import get_auth_token, _auth_enabled
from .agent_manager import agent_manager
from .utils import (
    _build_real_system_prompt,
    _compute_session_tokens,
    _deep_merge,
    _redact_secrets,
    _redact_one,
    _resolve_gateway_hosts,
    _resolve_workspace_path,
    _gateway_request,
    _LOCAL_HOSTS,
    _workspace_context_cache,
    _session_context_cache,
    _system_prompt_cache,
)


async def api_status(request: Request):
    """Get general server and agent status."""
    await agent_manager.ensure_agent()
    cfg = agent_manager.config
    from shibaclaw import __version__
    return JSONResponse({
        "status": "ok",
        "version": __version__,
        "agent_configured": agent_manager.agent is not None,
        "provider": cfg.agents.defaults.provider if cfg else None,
        "model": cfg.agents.defaults.model if cfg else None,
        "workspace": str(cfg.workspace_path) if cfg else None,
    })


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

    from shibaclaw.helpers.helpers import estimate_message_tokens, estimate_prompt_tokens

    # ── Real system prompt (identity + bootstrap + memory + skills) ──
    system_prompt, prompt_tokens = _build_real_system_prompt(wp, defaults)
    total_tokens = prompt_tokens
    sections.append(f"## 🧠 System Prompt ({prompt_tokens} tokens)\n\n```markdown\n{system_prompt}\n```")

    # ── Tool definitions (sent alongside messages on every LLM call) ──
    tools_tokens = 0
    if agent_manager.agent and hasattr(agent_manager.agent, "tools"):
        tool_defs = agent_manager.agent.tools.get_definitions()
        if tool_defs:
            tools_tokens = estimate_prompt_tokens([], tool_defs)
            total_tokens += tools_tokens

    # ── Session messages ──
    msg_tokens = 0
    if session_id:
        pm = PackManager(wp)
        msg_tokens, msg_lines = _compute_session_tokens(session_id, wp, pm, estimate_message_tokens)
        if msg_lines:
            sections.append(
                f"## 💬 Session Messages ({len(pm.get_or_create(session_id).messages)} messages)\n\n"
                + "\n".join(msg_lines)
            )
    total_tokens += msg_tokens

    ctx_window = defaults.context_window_tokens or 0
    pct = min(100, round(total_tokens / ctx_window * 100)) if ctx_window > 0 else 0

    if request.query_params.get("summary", "").lower() in ("1", "true", "yes"):
        return JSONResponse({
            "tokens": {
                "system_prompt": prompt_tokens,
                "tools": tools_tokens,
                "messages": msg_tokens,
                "total": total_tokens,
                "context_window": ctx_window,
                "usage_pct": pct,
            }
        })

    context_md = "\n\n---\n\n".join(sections) if sections else "_No context files or session data found._"
    return JSONResponse({
        "context": context_md,
        "tokens": {
            "system_prompt": prompt_tokens,
            "tools": tools_tokens,
            "messages": msg_tokens,
            "total": total_tokens,
            "context_window": ctx_window,
            "usage_pct": pct,
        },
    })


# ── Re-exports (server.py imports everything from here) ──────────────
from .routers.auth import api_auth_verify, api_auth_status  # noqa: E402, F401
from .routers.sessions import api_sessions_list, api_sessions_get, api_sessions_patch, api_sessions_delete, api_sessions_archive  # noqa: E402, F401
from .routers.settings import api_settings_get, api_settings_post  # noqa: E402, F401
from .routers.fs import api_upload, api_file_get, api_file_save, api_fs_explore  # noqa: E402, F401
from .routers.gateway import api_gateway_health, api_gateway_restart  # noqa: E402, F401
from .routers.heartbeat import api_heartbeat_status, api_heartbeat_trigger  # noqa: E402, F401
from .routers.oauth import api_oauth_providers, api_oauth_login, api_oauth_job, api_oauth_code  # noqa: E402, F401
from .routers.cron import api_cron_list, api_cron_trigger  # noqa: E402, F401
from .routers.system import api_update_check, api_update_manifest, api_restart_server  # noqa: E402, F401
from .routers.onboard import api_onboard_providers, api_onboard_templates, api_onboard_submit  # noqa: E402, F401
