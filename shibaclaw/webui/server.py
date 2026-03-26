"""ShibaBridge — FastAPI + Socket.IO server for the ShibaClaw WebUI.

Usage (standalone):
    python -m shibaclaw.webui.server --port 3000

Or via CLI:
    shibaclaw web --port 3000
"""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from pathlib import Path
from typing import Any

import socketio
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from loguru import logger

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

# ── Token-based authentication ───────────────────────────────────
AUTH_TOKEN_DIR = Path.home() / ".shibaclaw"
AUTH_TOKEN_FILE = AUTH_TOKEN_DIR / "auth_token"


def _auth_enabled() -> bool:
    """Check if auth is enabled (default: True)."""
    return os.environ.get("SHIBACLAW_AUTH", "true").lower() not in ("false", "0", "no", "off")


def _load_or_generate_token() -> str:
    """Load token from env/file, or generate a new one."""
    # 1. Environment variable override
    env_token = os.environ.get("SHIBACLAW_AUTH_TOKEN", "").strip()
    if env_token:
        return env_token

    # 2. Load from file
    if AUTH_TOKEN_FILE.exists():
        saved = AUTH_TOKEN_FILE.read_text().strip()
        if saved:
            return saved

    # 3. Generate new token
    token = secrets.token_hex(16)
    AUTH_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_TOKEN_FILE.write_text(token)
    AUTH_TOKEN_FILE.chmod(0o600)
    return token


# Generate at module load so it's available to create_app and run_server
_AUTH_TOKEN: str = _load_or_generate_token() if _auth_enabled() else ""

# Cache for context token metrics and workspace context scanning.
_workspace_context_cache = {
    "file_state": {},  # filename -> mtime
    "file_tokens": 0,
    "sections": [],
}
_session_context_cache: dict[str, dict[str, Any]] = {}


def _check_token(request: Request) -> bool:
    """Validate the auth token from Authorization header or query param."""
    if not _auth_enabled() or not _AUTH_TOKEN:
        return True
    # Authorization: Bearer <token>
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:].strip() == _AUTH_TOKEN:
        return True
    # Query param: ?token=<token>
    if request.query_params.get("token") == _AUTH_TOKEN:
        return True
    return False


# Paths that don't require auth (static assets, auth endpoints, socket.io)
_PUBLIC_PATHS = ("/static/", "/api/auth/", "/socket.io")


class AuthMiddleware(BaseHTTPMiddleware):
    """Token-based auth middleware — blocks unauthenticated HTTP requests."""

    async def dispatch(self, request: Request, call_next):
        if not _auth_enabled():
            return await call_next(request)

        path = request.url.path

        # Allow public paths through
        if any(path.startswith(p) for p in _PUBLIC_PATHS):
            return await call_next(request)

        # Root page — serve index.html always (JS handles login screen)
        if path == "/":
            return await call_next(request)

        # All /api/* routes require valid token
        if not _check_token(request):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)


async def _archive_in_background(consolidator, messages):
    """Fire-and-forget LLM archive — logs errors but never blocks the caller."""
    try:
        await consolidator.archive_messages(messages)
    except Exception:
        logger.exception("Background archive failed (messages already deleted from session)")


def create_app(
    config: Any | None = None,
    provider: Any | None = None,
) -> tuple[Starlette, socketio.AsyncServer]:
    """Create the ASGI app with Socket.IO attached.

    Returns (app, sio) so the caller can start both together.
    """
    # ── Socket.IO server ──────────────────────────────────────────────
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    # In-memory state per session (sid → data)
    sessions: dict[str, dict] = {}

    # ── Agent setup (lazy — only when config is provided) ─────────────
    _config = config
    _provider = provider
    agent = None
    bus = None

    def _load_latest_config():
        nonlocal _config, _provider
        from shibaclaw.config.loader import load_config
        _config = load_config()
        # Build an actual Thinker (provider with chat_with_retry), not just ProviderConfig
        try:
            from shibaclaw.cli.commands import _make_provider
            _provider = _make_provider(_config, exit_on_error=False)
        except Exception:
            _provider = None

    async def _ensure_agent():
        nonlocal agent, bus, _config, _provider
        
        # If not configured, try to reload from disk (might have been onboarded)
        is_fully_configured = (
            _config is not None and 
            _config.agents.defaults.provider != "auto" and 
            _config.get_api_key() is not None
        )
        
        if not is_fully_configured:
            _load_latest_config()

        if agent is not None:
            return
            
        if _config is None or _provider is None:
            return

        from shibaclaw.agent.loop import ShibaBrain
        from shibaclaw.bus.queue import MessageBus
        from shibaclaw.brain.manager import PackManager
        from shibaclaw.config.paths import get_cron_dir
        from shibaclaw.cron.service import CronService

        bus = MessageBus()
        cron_store = get_cron_dir() / "jobs.json"
        cron = CronService(cron_store)

        agent = ShibaBrain(
            bus=bus,
            provider=_provider,
            workspace=_config.workspace_path,
            model=_config.agents.defaults.model,
            max_iterations=_config.agents.defaults.max_tool_iterations,
            context_window_tokens=_config.agents.defaults.context_window_tokens,
            web_search_config=_config.tools.web.search,
            web_proxy=_config.tools.web.proxy or None,
            exec_config=_config.tools.exec,
            cron_service=cron,
            restrict_to_workspace=_config.tools.restrict_to_workspace,
            mcp_servers=_config.tools.mcp_servers,
            channels_config=_config.channels,
        )
        await cron.start()

    # ── Socket.IO handlers ────────────────────────────────────────────
    @sio.event
    async def connect(sid, environ, auth=None):
        # Validate auth token for Socket.IO connections
        if _auth_enabled() and _AUTH_TOKEN:
            token = None
            if isinstance(auth, dict):
                token = auth.get("token")
            # Also check query params as fallback
            if not token:
                import urllib.parse
                query = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
                token = query.get("token", [None])[0]
            if token != _AUTH_TOKEN:
                logger.warning("🔒 Socket.IO connection rejected (invalid token) from {}", sid)
                raise socketio.exceptions.ConnectionRefusedError("Unauthorized")

        # Allow client to provide session_id via query params for persistence
        import urllib.parse
        query = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
        provided_id = query.get("session_id", [None])[0]
        
        session_id = provided_id if provided_id else f"webui:{sid[:8]}"
        sessions[sid] = {"session_key": session_id, "processing": False, "queue": []}
        logger.info("🌐 WebUI client connected: {} (Session: {})", sid, session_id)
        
        await sio.emit("connected", {
            "session_id": session_id,
            "message": "🐕 ShibaClaw WebUI connected!",
        }, room=sid)

    @sio.event
    async def disconnect(sid):
        sessions.pop(sid, None)
        logger.info("🌐 WebUI client disconnected: {}", sid)

    @sio.event
    async def user_message(sid, data):
        """Handle a message from the WebUI user. Messages are queued per-session so
        the UI can continue sending while the agent processes previous messages.
        """
        await _ensure_agent()
        if agent is None:
            await sio.emit("error", {
                "message": "Agent not configured. Run 'shibaclaw onboard' first.",
            }, room=sid)
            return

        content = data.get("content", "").strip()
        if not content:
            return

        # Ensure session structure exists
        session = sessions.setdefault(sid, {"session_key": f"webui:{sid[:8]}", "processing": False, "queue": []})
        session_key = session.get("session_key", f"webui:{sid[:8]}")

        msg = {"id": str(uuid.uuid4())[:8], "content": content}

        # If already processing, enqueue and notify client (ack + queued)
        if session.get("processing"):
            session.setdefault("queue", []).append(msg)
            await sio.emit("message_ack", {"id": msg["id"], "content": content}, room=sid)
            await sio.emit("message_queued", {
                "id": msg["id"],
                "position": len(session["queue"]),
            }, room=sid)
            logger.info("Queued message %s for %s (pos=%d)", msg["id"], sid, len(session["queue"]))
            return

        # Start processing immediate message
        session["processing"] = True
        await sio.emit("message_ack", {"id": msg["id"], "content": content}, room=sid)

        async def run_agent_job(message):
            # Progress callback scoped to this message
            async def on_progress(text: str, *, tool_hint: bool = False) -> None:
                event_type = "agent_tool" if tool_hint else "agent_thinking"
                await sio.emit(event_type, {
                    "id": message["id"],
                    "content": text,
                    "tool_hint": tool_hint,
                }, room=sid)

            try:
                response = await agent.process_direct(
                    content=message["content"],
                    session_key=session_key,
                    channel="webui",
                    chat_id=sid,
                    on_progress=on_progress,
                )

                await sio.emit("agent_response", {
                    "id": message["id"],
                    "content": response or "No response.",
                }, room=sid)
            except asyncio.CancelledError:
                await sio.emit("agent_response", {
                    "id": message["id"],
                    "content": "🐕 Hunt stopped.",
                }, room=sid)
            except Exception as e:
                logger.exception("WebUI processing error")
                await sio.emit("error", {"message": f"Error: {e}"}, room=sid)
            finally:
                # If there are queued messages, process the next one
                q = session.get("queue") or []
                if q:
                    next_msg = q.pop(0)
                    task = asyncio.create_task(run_agent_job(next_msg))
                    session["task"] = task
                else:
                    session["processing"] = False
                    session.pop("task", None)

        task = asyncio.create_task(run_agent_job(msg))
        session["task"] = task

    @sio.event
    async def stop_agent(sid, data=None):
        """Stop the current agent processing."""
        session = sessions.get(sid, {})
        if "task" in session:
            session["task"].cancel()
        # clear any queued messages as user explicitly requested stop
        session["queue"] = []
        session["processing"] = False
        await sio.emit("agent_response", {
            "id": "stop",
            "content": "🐕 Halted the hunt.",
        }, room=sid)

    @sio.event
    async def new_session(sid, data=None):
        """Start a new session."""
        new_key = f"webui:{uuid.uuid4().hex[:8]}"
        if sid in sessions:
            sessions[sid]["session_key"] = new_key
        await sio.emit("session_reset", {
            "session_id": new_key,
            "message": "New session started.",
        }, room=sid)

    # ── Helpers ──────────────────────────────────────────────────
    def _deep_merge(base: dict, patch: dict):
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                _deep_merge(base[k], v)
            else:
                base[k] = v

    # ── Starlette routes ──────────────────────────────────────────────
    async def index(request: Request):
        return FileResponse(STATIC_DIR / "index.html")

    async def api_auth_verify(request: Request):
        """Verify an auth token. Public endpoint (no middleware check)."""
        data = await request.json()
        token = data.get("token", "").strip()
        if not _auth_enabled():
            return JSONResponse({"valid": True, "auth_required": False})
        if token == _AUTH_TOKEN:
            return JSONResponse({"valid": True, "auth_required": True})
        return JSONResponse({"valid": False, "auth_required": True})

    async def api_auth_status(request: Request):
        """Check if auth is enabled (no token needed)."""
        return JSONResponse({"auth_required": _auth_enabled()})

    async def api_status(request: Request):
        await _ensure_agent()
        return JSONResponse({
            "status": "ok",
            "agent_configured": agent is not None,
            "provider": _config.agents.defaults.provider if _config else None,
            "model": _config.agents.defaults.model if _config else None,
            "workspace": str(_config.workspace_path) if _config else None,
        })

    async def api_settings_get(request: Request):
        if not _config:
            _load_latest_config()
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        data = _config.model_dump(mode="json", by_alias=True)
        return JSONResponse(data)

    async def api_settings_post(request: Request):
        nonlocal agent
        if not _config:
            _load_latest_config()
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        data = await request.json()

        # Deep-merge incoming JSON onto the current config
        from shibaclaw.config.schema import Config
        merged = _config.model_dump(mode="json", by_alias=True)
        _deep_merge(merged, data)
        try:
            new_cfg = Config.model_validate(merged)
        except Exception as e:
            return JSONResponse({"error": f"Invalid config: {e}"}, status_code=422)

        # Persist and swap
        from shibaclaw.config.loader import save_config
        save_config(new_cfg)
        _config.__dict__.update(new_cfg.__dict__)

        # Reset agent so it gets recreated with new settings on next message
        agent = None
        return JSONResponse({"status": "updated"})

    # ── OAuth helpers / endpoints ─────────────────────────────────
    import uuid as _uuid
    import os as _os

    async def api_oauth_providers(request: Request):
        """Lightweight status — checks cached tokens/files only, never triggers login."""
        providers = [
            {"name": "github_copilot", "label": "GitHub Copilot"},
            {"name": "openai_codex",   "label": "OpenAI Codex"},
        ]
        result = []
        for p in providers:
            status = "not_configured"
            msg = ""
            try:
                if p["name"] == "openai_codex":
                    try:
                        from oauth_cli_kit import get_token
                        token = get_token()
                        if token and getattr(token, "access", None):
                            status = "configured"
                            msg = f"Account: {getattr(token, 'account_id', 'unknown')}"
                        else:
                            status = "not_configured"
                    except ImportError:
                        status = "missing_dependency"
                        msg = "oauth-cli-kit not installed"
                    except Exception:
                        status = "not_configured"

                elif p["name"] == "github_copilot":
                    home = _os.path.expanduser("~")
                    token_paths = [
                        _os.path.join(home, ".config", "github-copilot", "hosts.json"),
                        _os.path.join(home, ".config", "github-copilot", "apps.json"),
                        _os.path.join(home, ".config", "litellm", "github_copilot", "access-token"),
                    ]
                    has_cached = any(_os.path.exists(tp) for tp in token_paths)
                    has_env = bool(_os.environ.get("GITHUB_TOKEN") or _os.environ.get("GITHUB_COPILOT_TOKEN"))
                    if has_cached or has_env:
                        status = "configured"
                        msg = "Cached credentials found"
                    else:
                        status = "not_configured"
                        msg = "No cached credentials"
            except Exception as e:
                status = "error"
                msg = str(e)
            result.append({**p, "status": status, "message": msg})
        return JSONResponse({"providers": result})

    async def api_oauth_login(request: Request):
        """Trigger OAuth device flow — returns device code + URL immediately."""
        data = await request.json()
        provider = data.get("provider", "").replace("-", "_")
        if provider not in ("github_copilot", "openai_codex"):
            return JSONResponse({"error": "Unknown provider"}, status_code=404)

        job_id = str(_uuid.uuid4())[:8]
        if "_oauth_jobs" not in globals():
            globals()["_oauth_jobs"] = {}
        jobs = globals()["_oauth_jobs"]
        jobs[job_id] = {"provider": provider, "status": "running", "logs": []}

        if provider == "github_copilot":
            import httpx
            GITHUB_CLIENT_ID = "Iv1.b507a08c87ecfe98"
            GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
            GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"

            # Step 1: Get device code directly from GitHub
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        GITHUB_DEVICE_CODE_URL,
                        headers={"Accept": "application/json"},
                        json={"client_id": GITHUB_CLIENT_ID, "scope": "read:user"},
                        timeout=10,
                    )
                    resp_json = resp.json()

                user_code = resp_json.get("user_code", "")
                verification_uri = resp_json.get("verification_uri", "https://github.com/login/device")
                device_code = resp_json.get("device_code", "")
                interval = resp_json.get("interval", 5)
                expires_in = resp_json.get("expires_in", 900)

                if not device_code or not user_code:
                    return JSONResponse({"error": "GitHub did not return a device code", "details": resp_json}, status_code=502)

                jobs[job_id]["logs"].append(f"Go to: {verification_uri}")
                jobs[job_id]["logs"].append(f"Enter code: {user_code}")
                jobs[job_id]["status"] = "awaiting_code"

                # Step 2: Poll for access token in background
                async def _poll_github_token():
                    import time
                    max_attempts = expires_in // interval
                    for attempt in range(max_attempts):
                        await asyncio.sleep(interval)
                        try:
                            async with httpx.AsyncClient() as c:
                                tr = await c.post(
                                    GITHUB_ACCESS_TOKEN_URL,
                                    headers={"Accept": "application/json"},
                                    json={
                                        "client_id": GITHUB_CLIENT_ID,
                                        "device_code": device_code,
                                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                    },
                                    timeout=10,
                                )
                                tj = tr.json()
                            error = tj.get("error")
                            if error == "authorization_pending":
                                continue
                            elif error == "slow_down":
                                await asyncio.sleep(5)
                                continue
                            elif error == "expired_token":
                                jobs[job_id]["status"] = "error"
                                jobs[job_id]["logs"].append("❌ Device code expired. Try again.")
                                return
                            elif error == "access_denied":
                                jobs[job_id]["status"] = "error"
                                jobs[job_id]["logs"].append("❌ Access denied by user.")
                                return
                            elif error:
                                jobs[job_id]["status"] = "error"
                                jobs[job_id]["logs"].append(f"❌ GitHub error: {error}")
                                return

                            access_token = tj.get("access_token")
                            if access_token:
                                # Save token for litellm as plain text in access-token
                                home = _os.path.expanduser("~")
                                token_dir = _os.path.join(home, ".config", "litellm", "github_copilot")
                                _os.makedirs(token_dir, exist_ok=True)
                                token_file = _os.path.join(token_dir, "access-token")
                                with open(token_file, "w") as f:
                                    f.write(access_token)

                                # Trigger gateway restart so it picks up the fresh token
                                try:
                                    import urllib.request
                                    if _config and getattr(_config, "gateway", None):
                                        gw_port = _config.gateway.port
                                        req = urllib.request.Request(f"http://127.0.0.1:{gw_port}/restart", method="POST", data=b"")
                                        urllib.request.urlopen(req, timeout=1)
                                except Exception:
                                    pass

                                jobs[job_id]["status"] = "done"
                                jobs[job_id]["logs"].append("✅ Authenticated with GitHub Copilot!")
                                return
                        except Exception as e:
                            jobs[job_id]["logs"].append(f"Poll error: {e}")
                            continue

                    jobs[job_id]["status"] = "error"
                    jobs[job_id]["logs"].append("❌ Timed out waiting for authorization.")

                asyncio.create_task(_poll_github_token())

                # Return device code + URL immediately
                return JSONResponse({
                    "job_id": job_id,
                    "user_code": user_code,
                    "verification_uri": verification_uri,
                })

            except Exception as e:
                return JSONResponse({"error": f"Failed to contact GitHub: {e}"}, status_code=502)

        elif provider == "openai_codex":
            try:
                from oauth_cli_kit import login_oauth_interactive, get_token
            except ImportError:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["logs"].append("❌ oauth-cli-kit not installed")
                jobs[job_id]["logs"].append("Run: pip install oauth-cli-kit")
                return JSONResponse({"job_id": job_id})

            import threading
            # Event + holder for the user to paste auth code via API
            code_event = threading.Event()
            code_holder = {"value": ""}
            jobs[job_id]["_code_event"] = code_event
            jobs[job_id]["_code_holder"] = code_holder
            auth_url_holder = {"url": ""}

            def _print(s):
                text = str(s)
                # Strip Rich markup tags
                import re
                clean = re.sub(r'\[/?[a-z]+\]', '', text)
                jobs[job_id]["logs"].append(clean)
                # Capture the auth URL
                if "auth.openai.com" in text or "authorize?" in text:
                    url = re.search(r'(https?://\S+)', text)
                    if url:
                        # Replace originator=nanobot with ShibaClaw
                        captured = url.group(1).replace("originator=nanobot", "originator=ShibaClaw")
                        auth_url_holder["url"] = captured
                        jobs[job_id]["auth_url"] = captured
                        jobs[job_id]["status"] = "awaiting_code"

            def _prompt(s):
                jobs[job_id]["logs"].append("⏳ Paste the authorization code or callback URL below")
                jobs[job_id]["status"] = "awaiting_code"
                # Wait for the user to submit the code via API (up to 120s)
                code_event.wait(timeout=120)
                return code_holder["value"]

            async def _run_codex_login():
                try:
                    token = await asyncio.to_thread(
                        login_oauth_interactive,
                        print_fn=_print,
                        prompt_fn=_prompt,
                        originator="ShibaClaw",
                    )
                    if token and getattr(token, "access", None):
                        jobs[job_id]["status"] = "done"
                        jobs[job_id]["logs"].append(f"✅ Authenticated: {getattr(token, 'account_id', '')}")
                    else:
                        jobs[job_id]["status"] = "error"
                        jobs[job_id]["logs"].append("❌ Authentication failed or cancelled")
                except Exception as e:
                    jobs[job_id]["status"] = "error"
                    jobs[job_id]["logs"].append(f"❌ {e}")

            asyncio.create_task(_run_codex_login())
            return JSONResponse({"job_id": job_id})

    async def api_oauth_job(request: Request):
        job_id = request.path_params.get("job_id")
        jobs = globals().get('_oauth_jobs', {})
        j = jobs.get(job_id)
        if not j:
            return JSONResponse({"error": "Job not found"}, status_code=404)
        # Return only serializable fields
        safe = {k: v for k, v in j.items() if not k.startswith("_")}
        return JSONResponse({"job": safe})

    async def api_oauth_code(request: Request):
        """Submit auth code for an awaiting OAuth job (OpenAI Codex)."""
        data = await request.json()
        job_id = data.get("job_id")
        code = data.get("code", "").strip()
        if not job_id or not code:
            return JSONResponse({"error": "Missing job_id or code"}, status_code=400)
        jobs = globals().get('_oauth_jobs', {})
        j = jobs.get(job_id)
        if not j:
            return JSONResponse({"error": "Job not found"}, status_code=404)
        event = j.get("_code_event")
        holder = j.get("_code_holder")
        if not event or not holder:
            return JSONResponse({"error": "Job does not accept code input"}, status_code=400)
        holder["value"] = code
        event.set()
        j["logs"].append("📋 Code received, exchanging for token...")
        return JSONResponse({"ok": True})

    # OAuth routes are registered in the routes list below (see create_app routes)

    async def api_sessions_list(request: Request):
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        from shibaclaw.brain.manager import PackManager
        pm = PackManager(_config.workspace_path)
        return JSONResponse({"sessions": pm.list_sessions()})

    async def api_sessions_get(request: Request):
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        session_id = request.path_params["session_id"]
        from shibaclaw.brain.manager import PackManager
        pm = PackManager(_config.workspace_path)
        session = pm.get_or_create(session_id)
        return JSONResponse({
            "messages": session.messages,
            "nickname": session.metadata.get("nickname")
        })

    async def api_sessions_patch(request: Request):
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        session_id = request.path_params["session_id"]
        data = await request.json()
        from shibaclaw.brain.manager import PackManager
        pm = PackManager(_config.workspace_path)
        session = pm.get_or_create(session_id)
        
        if "nickname" in data:
            session.metadata["nickname"] = data["nickname"]
            pm.save(session)
            return JSONResponse({"status": "updated"})
        return JSONResponse({"error": "Nothing to update"}, status_code=400)

    async def api_sessions_delete(request: Request):
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        session_id = request.path_params["session_id"]
        from shibaclaw.brain.manager import PackManager
        pm = PackManager(_config.workspace_path)
        
        path = pm._get_session_path(session_id)
        if path.exists():
            import os
            os.remove(path)
            pm.invalidate(session_id)
            return JSONResponse({"status": "deleted"})
        return JSONResponse({"error": "Session not found"}, status_code=404)

    async def api_sessions_archive(request: Request):
        await _ensure_agent()
        if not agent or not _config:
            return JSONResponse({"error": "Agent not configured"}, status_code=400)
        
        session_id = request.path_params["session_id"]
        from shibaclaw.brain.manager import PackManager
        pm = PackManager(_config.workspace_path)
        session = pm.get_or_create(session_id)
        
        # Grab messages before deleting
        snapshot = list(session.messages[session.last_consolidated:])
        
        # Delete session file immediately so UI stays consistent
        import os
        path = pm._get_session_path(session_id)
        if path.exists():
            os.remove(path)
        pm.invalidate(session_id)
        
        # Fire-and-forget: archive to HISTORY.md in background
        if snapshot and hasattr(agent, "memory_consolidator"):
            import asyncio
            asyncio.create_task(_archive_in_background(agent.memory_consolidator, snapshot))
        
        return JSONResponse({"status": "archived"})

    def _load_workspace_context(wp: Path):
        # Cached workspace context tokens to avoid repeated disk reads.
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

    async def api_gateway_health(request: Request):
        """Check if the gateway health endpoint is reachable via HTTP."""
        if not _config:
            return JSONResponse({"reachable": False, "reason": "no_config"})

        gw = _config.gateway
        port = gw.port
        # Try Docker service name first, then localhost
        hosts = ["shibaclaw-gateway", "127.0.0.1"]
        if gw.host not in ("0.0.0.0", "::", ""):
            hosts = [gw.host]

        for host in hosts:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=2.0
                )
                writer.write(b"GET /health HTTP/1.0\r\nHost: health\r\n\r\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.read(512), timeout=2.0)
                writer.close()
                if b"200" in data:
                    import json as _json
                    body_start = data.find(b"\r\n\r\n")
                    if body_start > 0:
                        try:
                            info = _json.loads(data[body_start + 4:])
                            return JSONResponse({"reachable": True, **info})
                        except Exception:
                            pass
                    return JSONResponse({"reachable": True})
            except Exception:
                continue
        return JSONResponse({"reachable": False, "reason": "unreachable"})

    async def api_context_get(request: Request):
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)
        
        wp = _config.workspace_path
        session_id = request.query_params.get("session_id", "")

        sections = []

        # ── Token estimate header ──────────────────────────────
        from shibaclaw.helpers.helpers import estimate_message_tokens
        total_tokens = 0

        # ── Workspace context files (cached) ───────────────────
        file_tokens, workspace_sections = _load_workspace_context(wp)
        sections.extend(workspace_sections)
        total_tokens += file_tokens

        # ── Session messages (cached by message count) ───────────
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

        if request.query_params.get("summary", "").lower() in ("1", "true", "yes"):
            ctx_window = _config.agents.defaults.context_window_tokens or 0
            pct = min(100, round(total_tokens / ctx_window * 100)) if ctx_window > 0 else 0
            return JSONResponse({
                "tokens": {
                    "workspace": file_tokens,
                    "messages": msg_tokens,
                    "total": total_tokens,
                    "context_window": ctx_window,
                    "usage_pct": pct,
                }
            })

        ctx_window = _config.agents.defaults.context_window_tokens or 0
        pct = min(100, round(total_tokens / ctx_window * 100)) if ctx_window > 0 else 0

        # Build markdown for the modal body (no token header — JS builds the card)
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

    async def api_gateway_restart(request: Request):
        """Send a restart command to the gateway's health endpoint."""
        if not _config:
            return JSONResponse({"error": "No config"}, status_code=400)

        gw = _config.gateway
        port = gw.port
        hosts = ["shibaclaw-gateway", "127.0.0.1"]
        if gw.host not in ("0.0.0.0", "::", ""):
            hosts = [gw.host]

        for host in hosts:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=2.0
                )
                writer.write(b"POST /restart HTTP/1.0\r\nHost: gw\r\n\r\n")
                await writer.drain()
                data = await asyncio.wait_for(reader.read(512), timeout=2.0)
                writer.close()
                if b"200" in data:
                    # Reset agent so it recreates on next message after restart
                    nonlocal agent
                    agent = None
                    return JSONResponse({"status": "restarting"})
            except Exception:
                continue
        return JSONResponse({"error": "Gateway unreachable"}, status_code=503)

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
        Route("/api/oauth/providers", api_oauth_providers, methods=["GET"]),
        Route("/api/oauth/login", api_oauth_login, methods=["POST"]),
        Route("/api/oauth/job/{job_id}", api_oauth_job, methods=["GET"]),
        Route("/api/oauth/code", api_oauth_code, methods=["POST"]),
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"),
    ]

    app = Starlette(routes=routes)

    # Add auth middleware
    if _auth_enabled():
        app.add_middleware(AuthMiddleware)

    # Wrap Starlette with Socket.IO ASGI app (no debug wrappers)
    combined = socketio.ASGIApp(sio, app)

    return combined, sio


async def run_server(port: int = 3000, config=None, provider=None):
    """Start the WebUI server."""
    app, sio = create_app(config=config, provider=provider)

    # Print auth info
    if _auth_enabled() and _AUTH_TOKEN:
        logger.info("🔒 Auth enabled — token: {}", _AUTH_TOKEN)
        logger.info("🔑 Direct URL: http://localhost:{}?token={}", port, _AUTH_TOKEN)
    else:
        logger.info("🔓 Auth disabled — open access")

    server_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(server_config)
    await server.serve()


def get_auth_token() -> str | None:
    """Return the current auth token (for CLI to display)."""
    if _auth_enabled() and _AUTH_TOKEN:
        return _AUTH_TOKEN
    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ShibaClaw WebUI Server")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()

    print(f"🐕 Starting ShibaClaw WebUI on http://localhost:{args.port}")
    asyncio.run(run_server(port=args.port))
