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


async def api_oauth_providers(request: Request):
    providers = [
        {"name": "github_copilot", "label": "GitHub Copilot"},
        {"name": "openai_codex",   "label": "OpenAI Codex"},
    ]
    result = []
    for p in providers:
        status, msg = "not_configured", ""
        try:
            if p["name"] == "openai_codex":
                try:
                    from oauth_cli_kit import get_token
                    tk = get_token()
                    if tk and getattr(tk, "access", None):
                        status, msg = "configured", f"Account: {getattr(tk, 'account_id', 'unknown')}"
                except (ImportError, Exception):
                    status, msg = "not_configured", ""
            elif p["name"] == "github_copilot":
                home = os.path.expanduser("~")
                token_paths = [
                    os.path.join(home, ".config", "github-copilot", "hosts.json"),
                    os.path.join(home, ".config", "shibaclaw", "github_copilot", "access-token"),
                ]
                has_cached = any(os.path.exists(tp) for tp in token_paths)
                has_env = bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_COPILOT_TOKEN"))
                status = "configured" if (has_cached or has_env) else "not_configured"
                msg = "Cached credentials found" if status=="configured" else "No cached credentials"
        except Exception as e:
            status, msg = "error", str(e)
        result.append({**p, "status": status, "message": msg})
    return JSONResponse({"providers": result})


async def api_oauth_login(request: Request):
    data = await request.json()
    provider = data.get("provider", "").replace("-", "_")
    if provider not in ("github_copilot", "openai_codex"):
        return JSONResponse({"error": "Unknown provider"}, status_code=404)

    job_id = str(uuid.uuid4())[:8]
    jobs = agent_manager.oauth_jobs
    jobs[job_id] = {"provider": provider, "status": "running", "logs": []}

    if provider == "github_copilot":
        from ..oauth_github import start_github_oauth
        return await start_github_oauth(job_id, jobs)
    elif provider == "openai_codex":
        from ..oauth_github import start_codex_oauth
        return await start_codex_oauth(job_id, jobs)


async def api_oauth_job(request: Request):
    job_id = request.path_params.get("job_id")
    jobs = agent_manager.oauth_jobs
    j = jobs.get(job_id)
    if not j: return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse({"job": {k: v for k, v in j.items() if not k.startswith("_")}})


async def api_oauth_code(request: Request):
    data = await request.json()
    job_id, code = data.get("job_id"), data.get("code", "").strip()
    jobs = agent_manager.oauth_jobs
    j = jobs.get(job_id)
    if not j: return JSONResponse({"error": "Job not found"}, status_code=404)
    event, holder = j.get("_code_event"), j.get("_code_holder")
    if not event or not holder: return JSONResponse({"error": "Job does not accept code input"}, status_code=400)
    holder["value"] = code
    event.set()
    j["logs"].append("📋 Code received, exchanging for token...")
    return JSONResponse({"ok": True})
