"""Starlette API route handlers for the ShibaClaw WebUI."""

from __future__ import annotations

import os
import uuid
import json
import asyncio
import mimetypes
import urllib.parse
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from loguru import logger

from .auth import get_auth_token, _auth_enabled
from .agent_manager import agent_manager

# ── Helpers ──────────────────────────────────────────────────
def _deep_merge(base: dict, patch: dict):
    """Deep merge a dictionary patch onto base."""
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        elif isinstance(v, str) and isinstance(base.get(k), str):
            if v == _redact_one(base.get(k)):
                continue
            base[k] = v
        else:
            base[k] = v


def _redact_secrets(obj: Any, keys_to_redact: Optional[Set[str]] = None) -> Any:
    """Recursively redact sensitive fields in a config-like dict."""
    _keys = keys_to_redact or {
        "api_key", "apiKey", "access_token", "accessToken",
        "token", "secret", "password", "key", "auth_token"
    }
    if isinstance(obj, dict):
        return {
            k: (_redact_one(v) if k.lower() in _keys else _redact_secrets(v, _keys))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_secrets(item, _keys) for item in obj]
    return obj


def _redact_one(val: Any) -> Any:
    """Redact a single string value, keeping only the last 4 characters."""
    if not isinstance(val, str) or not val:
        return val
    if len(val) <= 4:
        return "****"
    return "*" * (len(val) - 4) + val[-4:]


# Global caches for context
_workspace_context_cache = {
    "file_state": {},  # filename -> mtime
    "file_tokens": 0,
    "sections": [],
}
_session_context_cache: Dict[str, Dict[str, Any]] = {}
_system_prompt_cache: Dict[str, Any] = {
    "prompt": "",
    "tokens": 0,
    "file_state": {},
    "settings": {},
}


def _build_real_system_prompt(wp: Path, defaults) -> tuple[str, int]:
    """Build the real system prompt via ScentBuilder and return (prompt, tokens).

    Uses a mtime-based cache to avoid re-reading disk on every poll.
    """
    from shibaclaw.agent.context import ScentBuilder
    from shibaclaw.helpers.helpers import estimate_prompt_tokens

    # Check mtime of all files that feed into the system prompt
    builder = ScentBuilder(wp)
    check_files = [wp / f for f in ScentBuilder.BOOTSTRAP_FILES] + [
        wp / "memory" / "MEMORY.md",
    ]
    current_state = {}
    for p in check_files:
        if p.exists():
            current_state[str(p)] = p.stat().st_mtime

    current_settings = {
        "memory_max_prompt_tokens": defaults.memory_max_prompt_tokens,
    }

    if (
        current_state == _system_prompt_cache["file_state"]
        and current_settings == _system_prompt_cache["settings"]
        and _system_prompt_cache["prompt"]
    ):
        return _system_prompt_cache["prompt"], _system_prompt_cache["tokens"]

    prompt = builder.build_system_prompt(
        memory_max_prompt_tokens=defaults.memory_max_prompt_tokens,
    )
    tokens = estimate_prompt_tokens([{"role": "system", "content": prompt}])

    _system_prompt_cache["prompt"] = prompt
    _system_prompt_cache["tokens"] = tokens
    _system_prompt_cache["file_state"] = current_state
    _system_prompt_cache["settings"] = current_settings

    return prompt, tokens


def _compute_session_tokens(session_id: str, wp: Path, pm, estimate_message_tokens):
    """Compute and cache message tokens for a session."""
    cache = _session_context_cache.get(session_id, {})
    session = pm.get_or_create(session_id)
    msgs = session.messages
    msg_count = len(msgs)

    if cache.get("msg_count") == msg_count and cache.get("workspace_path") == str(wp):
        return cache["msg_tokens"], cache["msg_lines"]

    msg_tokens = 0
    msg_lines = []

    for m in msgs:
        msg_tokens += estimate_message_tokens(m)
        role = m.get("role", "?").upper()
        ts = (m.get("timestamp") or "")[:16]
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        preview = (content or "")[:200]
        if len(content or "") > 200:
            preview += "…"
        tools = ""
        if m.get("tools_used"):
            tools = f" `[{', '.join(m['tools_used'])}]`"
        msg_lines.append(f"- **{role}** {ts}{tools}: {preview}")

    _session_context_cache[session_id] = {
        "msg_count": msg_count,
        "msg_tokens": msg_tokens,
        "msg_lines": msg_lines,
        "workspace_path": str(wp),
    }
    return msg_tokens, msg_lines


# ── Route Handlers ────────────────────────────────────────────────

async def api_auth_verify(request: Request):
    """Verify an auth token."""
    data = await request.json()
    token = data.get("token", "").strip()
    auth_req = _auth_enabled()
    if not auth_req:
        return JSONResponse({"valid": True, "auth_required": False})
    if token == get_auth_token():
        return JSONResponse({"valid": True, "auth_required": True})
    return JSONResponse({"valid": False, "auth_required": True})


async def api_auth_status(request: Request):
    """Check if auth is enabled."""
    return JSONResponse({"auth_required": _auth_enabled()})


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


async def api_settings_get(request: Request):
    """Get the current configuration (redacted)."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    data = agent_manager.config.model_dump(mode="json", by_alias=True)
    return JSONResponse(_redact_secrets(data))


async def api_settings_post(request: Request):
    """Update configuration and reset the agent."""
    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    
    data = await request.json()
    from shibaclaw.config.schema import Config
    merged = agent_manager.config.model_dump(mode="json", by_alias=True)
    _deep_merge(merged, data)
    
    try:
        new_cfg = Config.model_validate(merged)
    except Exception as e:
        return JSONResponse({"error": f"Invalid config: {e}"}, status_code=422)

    from shibaclaw.config.loader import save_config
    save_config(new_cfg)
    agent_manager.config = new_cfg
    # Rebuild provider so ensure_agent() picks up new API keys immediately
    try:
        from shibaclaw.cli.commands import _make_provider
        agent_manager.provider = _make_provider(new_cfg, exit_on_error=False)
    except Exception:
        agent_manager.provider = None
    agent_manager.reset_agent()
    
    return JSONResponse({"status": "updated"})


async def api_sessions_list(request: Request):
    """List all saved sessions."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    from shibaclaw.brain.manager import PackManager
    pm = PackManager(agent_manager.config.workspace_path)
    return JSONResponse({"sessions": pm.list_sessions()})


async def api_sessions_get(request: Request):
    """Get details for a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    from shibaclaw.brain.manager import PackManager
    pm = PackManager(agent_manager.config.workspace_path)
    session = pm.get_or_create(session_id)
    return JSONResponse({
        "messages": session.messages,
        "nickname": session.metadata.get("nickname")
    })


async def api_sessions_patch(request: Request):
    """Update session metadata (like nickname)."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    data = await request.json()
    from shibaclaw.brain.manager import PackManager
    pm = PackManager(agent_manager.config.workspace_path)
    session = pm.get_or_create(session_id)
    
    if "nickname" in data:
        session.metadata["nickname"] = data["nickname"]
        pm.save(session)
        return JSONResponse({"status": "updated"})
    return JSONResponse({"error": "Nothing to update"}, status_code=400)


async def api_sessions_delete(request: Request):
    """Delete a specific session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    session_id = request.path_params["session_id"]
    from shibaclaw.brain.manager import PackManager
    pm = PackManager(agent_manager.config.workspace_path)
    
    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
        pm.invalidate(session_id)
        return JSONResponse({"status": "deleted"})
    return JSONResponse({"error": "Session not found"}, status_code=404)


async def api_sessions_archive(request: Request):
    """Archive session messages to HISTORY.md."""
    await agent_manager.ensure_agent()
    if not agent_manager.agent or not agent_manager.config:
        return JSONResponse({"error": "Agent not configured"}, status_code=400)
    
    session_id = request.path_params["session_id"]
    from shibaclaw.brain.manager import PackManager
    pm = PackManager(agent_manager.config.workspace_path)
    session = pm.get_or_create(session_id)
    
    snapshot = list(session.messages[session.last_consolidated:])
    
    path = pm._get_session_path(session_id)
    if path.exists():
        os.remove(path)
    pm.invalidate(session_id)
    
    if snapshot:
        asyncio.create_task(agent_manager.archive_in_background(snapshot))
    
    return JSONResponse({"status": "archived"})


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
        from shibaclaw.brain.manager import PackManager
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


async def api_gateway_health(request: Request):
    """Proxy health check to the gateway."""
    if not agent_manager.config:
        return JSONResponse({"reachable": False, "reason": "no_config"})

    gw = agent_manager.config.gateway
    port = gw.port
    gateway_hostname = os.environ.get("SHIBACLAW_GATEWAY_HOST", "shibaclaw-gateway")
    if gw.host not in ("0.0.0.0", "::", "", "127.0.0.1"):
        # Custom host: try it first, then fall back to 127.0.0.1 in case of IP change
        hosts = [gw.host, "127.0.0.1"]
    else:
        hosts = [gateway_hostname, "127.0.0.1"]

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
            try:
                writer.write(b"GET /health HTTP/1.0\r\nHost: health\r\n\r\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    try:
                        info = json.loads(data[body_start + 4:])
                        return JSONResponse({"reachable": True, **info})
                    except Exception:
                        pass
                return JSONResponse({"reachable": True})
        except Exception:
            continue
    return JSONResponse({"reachable": False, "reason": "unreachable"})


async def api_internal_session_notify(request: Request):
    """Receive a background notification and route it to a persisted WebUI session."""
    data = await request.json()
    session_key = str(data.get("session_key", "")).strip()
    content = str(data.get("content", "")).strip()
    source = str(data.get("source", "background")).strip() or "background"
    raw_persist = data.get("persist", True)
    persist = raw_persist if isinstance(raw_persist, bool) else str(raw_persist).strip().lower() not in ("0", "false", "no", "off")

    if not session_key or not content:
        return JSONResponse({"error": "Missing session_key or content"}, status_code=400)

    result = await agent_manager.deliver_background_notification(
        session_key,
        content,
        source=source,
        persist=persist,
    )
    return JSONResponse({"status": "accepted", **result})


# ── Cron & Heartbeat ──────────────────────────────────────────

async def api_cron_list(request: Request):
    """List all scheduled jobs from the local CronService."""
    await agent_manager.ensure_agent()
    cron = getattr(agent_manager.agent, "cron_service", None) if agent_manager.agent else None
    if not cron:
        return JSONResponse({"jobs": []})

    jobs = cron.list_jobs(include_disabled=True)
    return JSONResponse({"jobs": [
        {
            "id": j.id,
            "name": j.name,
            "enabled": j.enabled,
            "schedule": {"kind": j.schedule.kind, "atMs": j.schedule.at_ms, "everyMs": j.schedule.every_ms, "expr": j.schedule.expr, "tz": j.schedule.tz},
            "payload": {"message": j.payload.message, "deliver": j.payload.deliver, "channel": j.payload.channel, "to": j.payload.to},
            "state": {
                "nextRunAtMs": j.state.next_run_at_ms,
                "lastRunAtMs": j.state.last_run_at_ms,
                "lastStatus": j.state.last_status,
                "lastError": j.state.last_error,
            },
            "deleteAfterRun": j.delete_after_run,
        }
        for j in jobs
    ]})


async def api_cron_trigger(request: Request):
    """Manually trigger a cron job by ID."""
    await agent_manager.ensure_agent()
    cron = getattr(agent_manager.agent, "cron_service", None) if agent_manager.agent else None
    if not cron:
        return JSONResponse({"error": "Cron not available"}, status_code=400)

    job_id = request.path_params["job_id"]
    ran = await cron.run_job(job_id, force=True)
    return JSONResponse({"triggered": ran})


async def _gateway_request(method: str, path: str) -> dict | None:
    """Send a raw HTTP request to the gateway and return parsed JSON or None."""
    if not agent_manager.config:
        return None
    gw = agent_manager.config.gateway
    port = gw.port
    gateway_hostname = os.environ.get("SHIBACLAW_GATEWAY_HOST", "shibaclaw-gateway")
    hosts = [gateway_hostname, "127.0.0.1"] if gw.host in ("0.0.0.0", "::", "", "127.0.0.1") else [gw.host, "127.0.0.1"]

    auth_token = get_auth_token()
    auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5.0)
            try:
                writer.write(f"{method} {path} HTTP/1.0\r\nHost: gw\r\n{auth_hdr}\r\n".encode())
                await writer.drain()
                data = await asyncio.wait_for(reader.read(8192), timeout=10.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                body_start = data.find(b"\r\n\r\n")
                if body_start > 0:
                    return json.loads(data[body_start + 4:])
        except Exception:
            continue
    return None


async def api_heartbeat_status(request: Request):
    """Proxy heartbeat status from the gateway."""
    result = await _gateway_request("GET", "/heartbeat/status")
    if result is None:
        return JSONResponse({"reachable": False})
    return JSONResponse({"reachable": True, **result})


async def api_heartbeat_trigger(request: Request):
    """Proxy heartbeat trigger to the gateway."""
    result = await _gateway_request("POST", "/heartbeat/trigger")
    if result is None:
        return JSONResponse({"error": "Gateway unreachable"}, status_code=503)
    return JSONResponse(result)


async def api_update_check(request: Request):
    """Check GitHub for the latest ShibaClaw release."""
    force = request.query_params.get("force", "").lower() in ("1", "true", "yes")
    try:
        from shibaclaw.updater.checker import check_for_update
        result = await asyncio.get_event_loop().run_in_executor(None, lambda: check_for_update(force=force))
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_update_manifest(request: Request):
    """Download and return the update manifest for a given manifest_url."""
    manifest_url = request.query_params.get("url", "").strip()
    if not manifest_url:
        return JSONResponse({"error": "Missing url parameter"}, status_code=400)

    parsed = urlparse(manifest_url)
    allowed_hosts = {"github.com", "raw.githubusercontent.com"}
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        return JSONResponse({"error": "Invalid manifest URL"}, status_code=400)

    try:
        from shibaclaw.updater.manifest import fetch_manifest, personal_files_in_manifest
        manifest = await asyncio.get_event_loop().run_in_executor(None, lambda: fetch_manifest(manifest_url))
        personal = personal_files_in_manifest(manifest)
        return JSONResponse({"manifest": manifest, "personal_files": personal})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_restart_server(request: Request):
    """Restart the ShibaClaw WebUI server process."""
    import sys

    async def _do_restart():
        await asyncio.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.create_task(_do_restart())
    return JSONResponse({"status": "restarting"})


async def api_gateway_restart(request: Request):
    """Proxy restart command to the gateway."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)

    gw = agent_manager.config.gateway
    port = gw.port
    gateway_hostname = os.environ.get("SHIBACLAW_GATEWAY_HOST", "shibaclaw-gateway")
    if gw.host not in ("0.0.0.0", "::", "", "127.0.0.1"):
        # Custom host: try it first, then fall back to 127.0.0.1 in case of IP change
        hosts = [gw.host, "127.0.0.1"]
    else:
        hosts = [gateway_hostname, "127.0.0.1"]

    auth_token = get_auth_token()
    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            try:
                auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""
                writer.write(f"POST /restart HTTP/1.0\r\nHost: gw\r\n{auth_hdr}\r\n".encode())
                await writer.drain()
                data = await asyncio.wait_for(reader.read(512), timeout=2.0)
            finally:
                writer.close()
                await writer.wait_closed()
            if b"200" in data:
                agent_manager.reset_agent()
                return JSONResponse({"status": "restarting"})
        except Exception:
            continue
    return JSONResponse({"error": "Gateway unreachable"}, status_code=503)


async def api_upload(request: Request):
    """Handle multi-file uploads into the workspace."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    
    try:
        form = await request.form()
        files = form.getlist("file")
        if not files:
            return JSONResponse({"error": "No files uploaded"}, status_code=400)
        
        upload_dir = agent_manager.config.workspace_path / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        auth_token = get_auth_token() or ""
        results = []
        for f in files:
            filename = f.filename
            safe_name = "".join([c for c in filename if c.isalnum() or c in "._- "]).strip()
            if not safe_name:
                safe_name = f"upload_{uuid.uuid4().hex[:8]}"
            
            target_path = upload_dir / safe_name
            counter = 1
            while target_path.exists():
                name_stem = Path(safe_name).stem
                suffix = Path(safe_name).suffix
                target_path = upload_dir / f"{name_stem}_{counter}{suffix}"
                counter += 1
            
            content = await f.read()
            target_path.write_bytes(content)
            results.append({
                "filename": target_path.name,
                "url": f"/api/file-get?path={urllib.parse.quote(str(target_path.absolute()))}"
            })
        
        return JSONResponse({"status": "success", "files": results})
    except Exception as e:
        logger.exception("Upload failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_file_get(request: Request):
    """Serve a file from the filesystem — restricted to the agent workspace."""
    path_str = request.query_params.get("path")
    if not path_str:
        return JSONResponse({"error": "No path provided"}, status_code=400)

    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=503)

    workspace = agent_manager.config.workspace_path.resolve()
    # Resolve relative paths against workspace, not process CWD
    raw = Path(path_str)
    resolved = (workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not resolved.is_relative_to(workspace):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if not resolved.exists() or not resolved.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    mime_type, _ = mimetypes.guess_type(path_str)
    if not mime_type:
        mime_type = "application/octet-stream"

    headers = {}
    if mime_type.startswith("image/"):
        headers["Cache-Control"] = "public, max-age=3600"
    else:
        headers["Cache-Control"] = "no-store"

    return FileResponse(resolved, media_type=mime_type, headers=headers)


async def api_file_save(request: Request):
    """Overwrite a workspace file with new text content."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    path_str = body.get("path")
    content = body.get("content")
    if not path_str or content is None:
        return JSONResponse({"error": "path and content are required"}, status_code=400)

    workspace = agent_manager.config.workspace_path.resolve()
    raw = Path(path_str)
    resolved = (workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not resolved.is_relative_to(workspace):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    if not resolved.exists() or not resolved.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)

    try:
        resolved.write_text(content, encoding="utf-8")
        written = resolved.stat().st_size
        logger.info("file-save: wrote {} bytes to {}", written, resolved)
        return JSONResponse({"status": "ok", "path": str(resolved), "bytes": written})
    except Exception as e:
        logger.exception("file-save failed for {}", resolved)
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_fs_explore(request: Request):
    """List files in a directory — restricted to the agent workspace."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=503)

    workspace = agent_manager.config.workspace_path.resolve()
    target_path_str = request.query_params.get("path")
    if not target_path_str:
        target_path = workspace
    else:
        raw = Path(target_path_str)
        # Resolve relative paths against the workspace root, not the process cwd
        target_path = (workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
        if not target_path.is_relative_to(workspace):
            return JSONResponse({"error": "Forbidden"}, status_code=403)

    if not target_path.exists() or not target_path.is_dir():
        return JSONResponse({"error": "Directory not found"}, status_code=404)
    
    try:
        items = []
        with os.scandir(target_path) as it:
            for entry in it:
                try:
                    info = {
                        "name": entry.name,
                        "path": Path(entry.path).relative_to(workspace).as_posix(),
                        "is_dir": entry.is_dir(),
                        "size": entry.stat().st_size if not entry.is_dir() else None,
                        "mtime": entry.stat().st_mtime
                    }
                    items.append(info)
                except (PermissionError, OSError):
                    continue
        
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        return JSONResponse({
            "current_path": str(target_path.absolute()),
            "parent_path": str(target_path.parent.absolute()) if target_path.parent != target_path else None,
            "items": items
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── OAuth ─ (Keeping mostly as is but in module) ──────────────────

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
    if "_oauth_jobs" not in globals():
        globals()["_oauth_jobs"] = {}
    jobs = globals()["_oauth_jobs"]
    jobs[job_id] = {"provider": provider, "status": "running", "logs": []}

    if provider == "github_copilot":
        from .oauth_github import start_github_oauth
        return await start_github_oauth(job_id, jobs)
    elif provider == "openai_codex":
        # Codex logic is complex, for now keep it simple here or move to helper
        return JSONResponse({"error": "Codex login not yet modularized"}, status_code=501)


async def api_oauth_job(request: Request):
    job_id = request.path_params.get("job_id")
    jobs = globals().get('_oauth_jobs', {})
    j = jobs.get(job_id)
    if not j: return JSONResponse({"error": "Job not found"}, status_code=404)
    return JSONResponse({"job": {k: v for k, v in j.items() if not k.startswith("_")}})


async def api_oauth_code(request: Request):
    data = await request.json()
    job_id, code = data.get("job_id"), data.get("code", "").strip()
    jobs = globals().get('_oauth_jobs', {})
    j = jobs.get(job_id)
    if not j: return JSONResponse({"error": "Job not found"}, status_code=404)
    event, holder = j.get("_code_event"), j.get("_code_holder")
    if not event or not holder: return JSONResponse({"error": "Job does not accept code input"}, status_code=400)
    holder["value"] = code
    event.set()
    j["logs"].append("📋 Code received, exchanging for token...")
    return JSONResponse({"ok": True})


# ── Onboard Wizard Endpoints ─────────────────────────────────

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

    (wp / "skills").mkdir(exist_ok=True)

    # Reset agent and reload from freshly saved config on disk.
    # This ensures the provider is correctly initialised from the new config
    # without depending on the in-memory object, which may be stale.
    agent_manager.reset_agent()
    agent_manager.load_latest_config()
    await agent_manager.ensure_agent()

    return JSONResponse({"status": "ok"})
