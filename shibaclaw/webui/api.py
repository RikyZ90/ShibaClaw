"""Starlette API route handlers for the ShibaClaw WebUI."""

from __future__ import annotations

import os
import uuid
import json
import asyncio
import mimetypes
import urllib.parse
import urllib.request
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


def _load_workspace_context(wp: Path):
    """Load and format workspace context files into readable sections."""
    global _workspace_context_cache

    file_list = ["SOUL.md", "USER.md", "MEMORY.md", "AGENTS.md", "TOOLS.md"]
    current_state = {}
    for file in file_list:
        p = wp / file
        if p.exists():
            current_state[file] = p.stat().st_mtime
        else:
            current_state[file] = None

    if current_state == _workspace_context_cache["file_state"]:
        return _workspace_context_cache["file_tokens"], _workspace_context_cache["sections"]

    file_tokens = 0
    sections = []
    file_parts = []

    for file in file_list:
        p = wp / file
        if p.exists():
            content = p.read_text(encoding="utf-8")
            file_parts.append(f"#### 📄 {file}\n```markdown\n{content}\n```")
            file_tokens += len(content) // 4  # rough estimate

    if file_parts:
        sections.append(f"## 🧠 Workspace Context\n\n" + "\n\n".join(file_parts))

    _workspace_context_cache["file_state"] = current_state
    _workspace_context_cache["file_tokens"] = file_tokens
    _workspace_context_cache["sections"] = sections

    return file_tokens, sections


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
    return JSONResponse({
        "status": "ok",
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
    agent_manager.config.__dict__.update(new_cfg.__dict__)
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
    """Generate a context summary for the workspace and session."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)
    
    wp = agent_manager.config.workspace_path
    session_id = request.query_params.get("session_id", "")
    sections = []
    
    from shibaclaw.helpers.helpers import estimate_message_tokens
    total_tokens = 0

    file_tokens, workspace_sections = _load_workspace_context(wp)
    sections.extend(workspace_sections)
    total_tokens += file_tokens

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

    ctx_window = agent_manager.config.agents.defaults.context_window_tokens or 0
    pct = min(100, round(total_tokens / ctx_window * 100)) if ctx_window > 0 else 0

    if request.query_params.get("summary", "").lower() in ("1", "true", "yes"):
        return JSONResponse({
            "tokens": {
                "workspace": file_tokens,
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
            "workspace": file_tokens,
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
    hosts = ["shibaclaw-gateway", "127.0.0.1"]
    if gw.host not in ("0.0.0.0", "::", ""):
        hosts = [gw.host]

    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
            writer.write(b"GET /health HTTP/1.0\r\nHost: health\r\n\r\n")
            await writer.drain()
            data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            writer.close()
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


async def api_gateway_restart(request: Request):
    """Proxy restart command to the gateway."""
    if not agent_manager.config:
        return JSONResponse({"error": "No config"}, status_code=400)

    gw = agent_manager.config.gateway
    port = gw.port
    hosts = ["shibaclaw-gateway", "127.0.0.1"]
    if gw.host not in ("0.0.0.0", "::", ""):
        hosts = [gw.host]

    auth_token = get_auth_token()
    for host in hosts:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=2.0
            )
            auth_hdr = f"Authorization: Bearer {auth_token}\r\n" if auth_token else ""
            writer.write(f"POST /restart HTTP/1.0\r\nHost: gw\r\n{auth_hdr}\r\n".encode())
            await writer.drain()
            data = await asyncio.wait_for(reader.read(512), timeout=2.0)
            writer.close()
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
                "url": f"/api/file-get?path={urllib.parse.quote(str(target_path.absolute()))}&token={auth_token}"
            })
        
        return JSONResponse({"status": "success", "files": results})
    except Exception as e:
        logger.exception("Upload failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_file_get(request: Request):
    """Serve a file from the filesystem."""
    path_str = request.query_params.get("path")
    if not path_str:
        return JSONResponse({"error": "No path provided"}, status_code=400)
    
    path = Path(path_str)
    if not path.exists() or not path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    
    mime_type, _ = mimetypes.guess_type(path_str)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    headers = {}
    if mime_type.startswith("image/"):
        headers["Cache-Control"] = "public, max-age=3600"
    else:
        headers["Content-Disposition"] = f'attachment; filename="{path.name}"'
        
    return FileResponse(path, media_type=mime_type, headers=headers)


async def api_fs_explore(request: Request):
    """List files in a directory."""
    target_path_str = request.query_params.get("path")
    if not target_path_str:
        if not agent_manager.config:
            return JSONResponse({"error": "No config and no path provided"}, status_code=400)
        target_path = agent_manager.config.workspace_path
    else:
        target_path = Path(target_path_str)
        
    if not target_path.exists() or not target_path.is_dir():
        return JSONResponse({"error": "Directory not found"}, status_code=404)
    
    try:
        items = []
        with os.scandir(target_path) as it:
            for entry in it:
                try:
                    info = {
                        "name": entry.name,
                        "path": str(Path(entry.path).absolute()),
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
