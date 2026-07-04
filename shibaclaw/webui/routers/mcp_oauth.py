"""MCP OAuth 2.1 Auto-Discovery routes for ShibaClaw WebUI.

Implements the MCP OAuth flow based on:
- RFC 9728: Protected Resource Metadata
- RFC 8414: Authorization Server Metadata
- RFC 7591: Dynamic Client Registration
- RFC 7636: PKCE
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.webui.routers.mcp_manager import _cfg_to_dict, _get_mcp_servers

# ── in-memory store ───────────────────────────────────────────────────────────
# state → {code_verifier, client_id, token_endpoint, redirect_uri, created_at, server_name}
_PENDING_OAUTH: dict[str, dict] = {}
_PENDING_TTL = 600  # 10 minutes
_executor = ThreadPoolExecutor(max_workers=4)


# ── helpers ───────────────────────────────────────────────────────────────────

def _generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge_b64url) using S256 method."""
    verifier = secrets.token_urlsafe(96)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _http_get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 8,
) -> dict:
    """Synchronous HTTP GET returning parsed JSON or raising."""
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_post_json(
    url: str,
    data: dict,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> dict:
    """Synchronous HTTP POST with JSON body returning parsed JSON."""
    payload = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=payload, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _build_redirect_uri(request: Request) -> str:
    """Build the absolute callback URL from the incoming request."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{scheme}://{host}/api/mcp/oauth/callback"


def _exchange_code_for_token(pending: dict, code: str) -> dict:
    """Exchange auth code + PKCE verifier for tokens (blocking, run in executor)."""
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": pending["redirect_uri"],
        "client_id": pending["client_id"],
        "code_verifier": pending["code_verifier"],
    }
    client_secret = pending.get("client_secret")
    if client_secret:
        payload["client_secret"] = client_secret
    return _http_post_json(pending["token_endpoint"], payload)


def _purge_expired() -> None:
    """Remove expired pending sessions."""
    now = time.time()
    expired = [s for s, d in _PENDING_OAUTH.items() if now - d["created_at"] > _PENDING_TTL]
    for s in expired:
        _PENDING_OAUTH.pop(s, None)


def _discover_oauth_metadata(server_url: str) -> dict[str, Any]:
    """Full RFC 9728 + RFC 8414 discovery. Returns metadata dict."""
    # Step 1: RFC 9728 – Protected Resource Metadata
    parsed = urllib.parse.urlparse(server_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    prm_url = f"{base}/.well-known/oauth-protected-resource"
    try:
        prm = _http_get_json(prm_url, timeout=6)
    except Exception:
        prm = {}

    # Step 2: RFC 8414 – Authorization Server Metadata
    as_urls: list[str] = []
    if prm.get("authorization_servers"):
        for as_url in prm["authorization_servers"]:
            as_urls.append(f"{as_url}/.well-known/oauth-authorization-server")
            as_urls.append(f"{as_url}/.well-known/openid-configuration")
    # Fallback: try on the same base
    as_urls += [
        f"{base}/.well-known/oauth-authorization-server",
        f"{base}/.well-known/openid-configuration",
    ]

    as_meta: dict = {}
    for url in as_urls:
        try:
            as_meta = _http_get_json(url, timeout=6)
            if as_meta.get("authorization_endpoint"):
                break
        except Exception:
            continue

    return {"prm": prm, "as": as_meta}


# ── route handlers ────────────────────────────────────────────────────────────

async def oauth_start(request: Request) -> JSONResponse:
    """POST /api/mcp/servers/{name}/oauth/start

    Full auto-discovery → dynamic registration → PKCE → returns auth_url.
    """
    import asyncio

    name = request.path_params["name"]
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config

    servers = _get_mcp_servers(cfg)
    if name not in servers:
        return JSONResponse({"error": f"Server '{name}' not found"}, status_code=404)

    sc = servers[name]
    sc_dict = dict(sc) if isinstance(sc, dict) else _cfg_to_dict(sc)
    server_url = sc_dict.get("url", "").rstrip("/")
    if not server_url:
        return JSONResponse({"error": "Server has no URL configured"}, status_code=400)

    _purge_expired()

    loop = asyncio.get_event_loop()

    try:
        # Discovery (blocking, off event loop)
        meta = await loop.run_in_executor(_executor, _discover_oauth_metadata, server_url)
    except Exception as exc:
        return JSONResponse({"error": f"Discovery failed: {exc}"}, status_code=502)

    as_meta = meta.get("as", {})
    authorization_endpoint = as_meta.get("authorization_endpoint", "")
    token_endpoint = as_meta.get("token_endpoint", "")
    registration_endpoint = as_meta.get("registration_endpoint", "")
    scopes_supported: list[str] = as_meta.get("scopes_supported") or []

    if not authorization_endpoint or not token_endpoint:
        return JSONResponse(
            {"error": "OAuth not supported by this server (no authorization/token endpoints found)"},
            status_code=422,
        )

    redirect_uri = _build_redirect_uri(request)
    verifier, challenge = _generate_pkce()
    state = secrets.token_urlsafe(32)

    client_id: str = ""
    client_secret: str = ""

    # Step 3: Dynamic Client Registration (RFC 7591)
    if registration_endpoint:
        try:
            reg_body = {
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "client_name": "ShibaClaw",
            }
            reg_resp = await loop.run_in_executor(
                _executor,
                lambda: _http_post_json(registration_endpoint, reg_body),
            )
            client_id = reg_resp.get("client_id", "")
            client_secret = reg_resp.get("client_secret", "")
        except Exception:
            pass

    # Fallback: check if server config already has client_id
    if not client_id:
        client_id = sc_dict.get("oauth", {}).get("client_id", "") or ""

    if not client_id:
        return JSONResponse(
            {"error": "Could not obtain client_id (no dynamic registration and no pre-configured client_id)"},
            status_code=422,
        )

    # Build auth URL
    scopes = scopes_supported[:8] if scopes_supported else []
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if scopes:
        params["scope"] = " ".join(scopes)

    auth_url = authorization_endpoint + "?" + urllib.parse.urlencode(params)

    _PENDING_OAUTH[state] = {
        "code_verifier": verifier,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_endpoint": token_endpoint,
        "redirect_uri": redirect_uri,
        "server_name": name,
        "created_at": time.time(),
    }

    return JSONResponse({"auth_url": auth_url, "state": state, "scopes": scopes})


async def oauth_callback(request: Request) -> RedirectResponse:
    """GET /api/mcp/oauth/callback?code=...&state=...

    Exchanges the auth code for tokens and persists them in the server config.
    """
    import asyncio

    params = dict(request.query_params)
    code = params.get("code", "")
    state = params.get("state", "")
    error = params.get("error", "")

    if error:
        return RedirectResponse(f"/?mcp_oauth_error={urllib.parse.quote(error)}")

    if not code or not state:
        return RedirectResponse("/?mcp_oauth_error=missing_params")

    pending = _PENDING_OAUTH.get(state)
    if not pending:
        return RedirectResponse("/?mcp_oauth_error=invalid_state")

    # Check TTL
    if time.time() - pending["created_at"] > _PENDING_TTL:
        _PENDING_OAUTH.pop(state, None)
        return RedirectResponse("/?mcp_oauth_error=session_expired")

    loop = asyncio.get_event_loop()
    try:
        token_resp = await loop.run_in_executor(
            _executor, _exchange_code_for_token, pending, code
        )
    except Exception as exc:
        _PENDING_OAUTH.pop(state, None)
        return RedirectResponse(f"/?mcp_oauth_error={urllib.parse.quote(str(exc))}")

    access_token = token_resp.get("access_token", "")
    if not access_token:
        _PENDING_OAUTH.pop(state, None)
        return RedirectResponse("/?mcp_oauth_error=no_access_token")

    # Persist token in server config
    cfg = agent_manager.config
    if not cfg:
        agent_manager.load_latest_config()
        cfg = agent_manager.config

    server_name = pending["server_name"]
    cfg_dict = _cfg_to_dict(cfg)
    servers = cfg_dict.get("tools", {}).get("mcpServers", {})

    if server_name in servers:
        srv = servers[server_name]
        if isinstance(srv, dict):
            oauth_data: dict = {"access_token": access_token}
            if token_resp.get("refresh_token"):
                oauth_data["refresh_token"] = token_resp["refresh_token"]
            expires_in = token_resp.get("expires_in")
            if expires_in:
                oauth_data["expires_at"] = time.time() + int(expires_in)
            oauth_data["client_id"] = pending["client_id"]
            srv["oauth"] = oauth_data
            cfg_dict.setdefault("tools", {})["mcpServers"] = servers
            try:
                agent_manager.save_config(cfg_dict)
            except Exception:
                pass

    # Remove from pending (consumed)
    _PENDING_OAUTH.pop(state, None)

    return RedirectResponse("/?mcp_oauth=done")


async def oauth_status(request: Request) -> JSONResponse:
    """GET /api/mcp/oauth/status?state=...

    Returns {completed: bool}. Used by the frontend for polling.
    """
    state = request.query_params.get("state", "")
    if not state:
        return JSONResponse({"error": "state param required"}, status_code=400)
    _purge_expired()
    if state in _PENDING_OAUTH:
        return JSONResponse({"completed": False})
    return JSONResponse({"completed": True})


# ── router registration ───────────────────────────────────────────────────────

routes = [
    Route("/api/mcp/servers/{name}/oauth/start", oauth_start, methods=["POST"]),
    Route("/api/mcp/oauth/callback", oauth_callback, methods=["GET"]),
    Route("/api/mcp/oauth/status", oauth_status, methods=["GET"]),
]
